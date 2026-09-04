"""
audio_pipeline.py — Pipeline de audio desacoplado para JARVIS.

Coordina:
  1. Captura continua de micrófono (PyAudioCapture).
  2. RingBuffer circular para retención de Pre-roll (800ms).
  3. Detección local de Wake Word (OpenWakeWordDetector) en estado DORMANT.
  4. Inyección reactiva del Pre-roll + audio en vivo hacia Gemini Live en estado ACTIVE.
  5. Emisión de eventos desacoplados mediante Synapse.
"""
from __future__ import annotations
import asyncio
import os
import time
from typing import Any
# pyrefly: ignore [missing-import]
from src.core.interfaces.audio import IAudioCapture
# pyrefly: ignore [missing-import]
from src.core.interfaces.audio_pipeline import IAudioPipeline
# pyrefly: ignore [missing-import]
from src.core.interfaces.wake_word import IWakeWordDetector
# pyrefly: ignore [missing-import]
from src.adapters.audio.ring_buffer import RingBuffer
# pyrefly: ignore [missing-import]
from src.kernel.activation_gate import ActivationGate, ActivationState


class AudioPipeline(IAudioPipeline):
    """
    Pipeline de audio centralizado y desacoplado de JARVIS.
    """

    def __init__(
        self,
        raw_capture: IAudioCapture,
        wake_word_detector: IWakeWordDetector | None = None,
        activation_gate: ActivationGate | None = None,
        synapse: Any | None = None,
        pre_roll_ms: int | None = None,
        wake_word_enabled: bool | None = None,
    ):
        self.raw_capture = raw_capture
        self.wake_word_detector = wake_word_detector
        self.activation_gate = activation_gate
        self.synapse = synapse

        self.pre_roll_ms = (
            pre_roll_ms
            if pre_roll_ms is not None
            else int(os.getenv("WAKE_WORD_PRE_ROLL_MS", "800"))
        )
        self.wake_word_enabled = (
            wake_word_enabled
            if wake_word_enabled is not None
            else os.getenv("WAKE_WORD_ENABLED", "1").lower() not in {"0", "false", "no", "off"}
        )

        # Buffer circular para 2 segundos de PCM 16kHz mono (64000 bytes)
        self.ring_buffer = RingBuffer(capacity_bytes=64000)

        # Cola de salida activa para el consumidor (Gemini Live)
        self._active_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._running = False
        self._worker_task: asyncio.Task | None = None

        # Telemetría
        self._total_chunks_processed = 0
        self._pre_rolls_injected = 0
        self._last_wake_timestamp = 0.0

    @property
    def muted(self) -> bool:
        return bool(getattr(self.raw_capture, "muted", False))

    @muted.setter
    def muted(self, value: bool) -> None:
        if hasattr(self.raw_capture, "muted"):
            self.raw_capture.muted = value

    def has_recent_voice(self, window_seconds: float | None = None) -> bool:
        has_voice = getattr(self.raw_capture, "has_recent_voice", None)
        if callable(has_voice):
            return bool(has_voice(window_seconds))
        return True

    def reset_recent_voice(self) -> None:
        reset_fn = getattr(self.raw_capture, "reset_recent_voice", None)
        if callable(reset_fn):
            reset_fn()

    def start(self) -> None:
        """Inicia el hardware de captura y la tarea de procesamiento del pipeline."""
        if self._running:
            return
        self._running = True
        self.raw_capture.start()

        # Arrancar la tarea background del pipeline en el event loop actual
        try:
            loop = asyncio.get_running_loop()
            self._worker_task = loop.create_task(self._pipeline_loop())
        except RuntimeError:
            pass
        print(
            f"\033[36m[AudioPipeline]\033[0m Pipeline de audio activo "
            f"(WakeWord={'ON' if self.wake_word_enabled else 'OFF'}, "
            f"PreRoll={self.pre_roll_ms}ms)"
        )

    def stop(self) -> None:
        """Detiene el pipeline y la captura subyacente."""
        self._running = False
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            self._worker_task = None
        self.raw_capture.stop()
        if self.wake_word_detector:
            self.wake_word_detector.reset()
        print("[AudioPipeline] Pipeline detenido.")

    def terminate(self) -> None:
        """Libera todos los recursos de hardware y audio."""
        self.stop()
        self.raw_capture.terminate()

    async def read_chunk(self) -> bytes:
        """
        Devuelve el siguiente chunk de audio procesado.
        Si la tarea worker aún no estaba creada, la lanza de forma perezosa.
        """
        if self._worker_task is None and self._running:
            self._worker_task = asyncio.create_task(self._pipeline_loop())
        return await self._active_queue.get()

    async def _pipeline_loop(self) -> None:
        """
        Bucle continuo de procesamiento y enrutamiento de audio.
        """
        while self._running:
            try:
                chunk = await self.raw_capture.read_chunk()
                if not chunk:
                    continue

                self._total_chunks_processed += 1
                # 1. Siempre alimentar el RingBuffer para mantener el Pre-roll fresco
                self.ring_buffer.write(chunk)

                # 2. Consultar el estado actual de activación
                current_state = (
                    self.activation_gate.state
                    if self.activation_gate
                    else ActivationState.ACTIVE
                )

                # 3. Flujo en estado DORMANT (en reposo)
                if current_state == ActivationState.DORMANT:
                    if (
                        self.wake_word_enabled
                        and self.wake_word_detector is not None
                        and self.wake_word_detector.is_ready()
                    ):
                        result = self.wake_word_detector.process_audio(chunk)
                        if result.detected:
                            self._handle_wake_word_detected(result, current_chunk=chunk)
                    else:
                        # Wake Word desactivado o detector no disponible: pasar audio directo
                        await self._active_queue.put(chunk)

                # 4. Flujo en estado ACTIVO (o en entrega / reconexión)
                else:
                    # En ACTIVE: mantener viva la sesión mientras el usuario hable
                    if self.activation_gate and self.has_recent_voice(2.0):
                        self.activation_gate.touch_voice()
                    await self._active_queue.put(chunk)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                print(f"\033[91m[AudioPipeline] Error en bucle: {exc}\033[0m")
                await asyncio.sleep(0.05)

    def _handle_wake_word_detected(self, result, current_chunk: bytes) -> None:
        """
        Gestiona la activación cuando se detecta la palabra clave.
        """
        now = time.time()
        self._last_wake_timestamp = now
        model_name = result.model or "hey_jarvis"
        score = result.score
        latency = result.processing_ms

        print(
            f"\033[96m[AudioPipeline] [WakeWord] Detectado: '{model_name}' "
            f"(score={score:.2f}, inferencia={latency}ms, frame={result.frame_index})\033[0m"
        )

        # 1. Disparar evento a Synapse (cero polling)
        if self.synapse:
            try:
                self.synapse.emit(
                    "wake_word_detected",
                    {
                        "model": model_name,
                        "score": score,
                        "timestamp": now,
                        "latency_ms": latency,
                    },
                )
            except Exception as exc:
                print(f"[AudioPipeline] Error emitiendo evento a Synapse: {exc}")

        # 2. Activar ActivationGate (DORMANT -> ACTIVE)
        if self.activation_gate:
            self.activation_gate.mark_wake_word(model_name)

        # 3. Extraer Pre-roll del RingBuffer e inyectarlo inmediatamente
        if self.pre_roll_ms > 0:
            pre_roll_bytes = self.ring_buffer.get_last_ms(self.pre_roll_ms)
            if pre_roll_bytes:
                self._active_queue.put_nowait(pre_roll_bytes)
                self._pre_rolls_injected += 1

        # 4. Inyectar también el chunk actual
        self._active_queue.put_nowait(current_chunk)

        # 5. Reiniciar detector para purgar tensores residuales del modelo
        if self.wake_word_detector is not None:
            self.wake_word_detector.reset()

    def get_metrics(self) -> dict[str, Any]:
        """Retorna telemetría consolidada del pipeline y del detector."""
        detector_metrics = (
            self.wake_word_detector.get_metrics()
            if self.wake_word_detector
            else {}
        )
        return {
            "pipeline_running": self._running,
            "wake_word_enabled": self.wake_word_enabled,
            "pre_roll_ms": self.pre_roll_ms,
            "total_chunks_processed": self._total_chunks_processed,
            "pre_rolls_injected": self._pre_rolls_injected,
            "ring_buffer_bytes": len(self.ring_buffer),
            "last_wake_timestamp": self._last_wake_timestamp,
            "detector": detector_metrics,
        }
