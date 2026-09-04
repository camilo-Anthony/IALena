"""
openwakeword_detector.py — Adaptador de detección de Wake Word usando openWakeWord (ONNX).

Implementa IWakeWordDetector con:
  - Buffering de audio PCM (1280 muestras / 80 ms a 16 kHz).
  - Histéresis multi-frame para eliminar falsos positivos.
  - Periodo de enfriamiento (cooldown) tras activación.
  - Telemetría de latencia de inferencia y estadísticas.
"""
from __future__ import annotations
import os
import time
import numpy as np
# pyrefly: ignore [missing-import]
from src.core.interfaces.wake_word import IWakeWordDetector, WakeWordResult


CHUNK_SAMPLES = 1280  # openWakeWord opera en bloques de 1280 muestras (80ms a 16kHz)
CHUNK_BYTES = CHUNK_SAMPLES * 2  # 2560 bytes (16-bit)


class OpenWakeWordDetector(IWakeWordDetector):
    """Adaptador de detección de Wake Word local basado en openWakeWord con ONNX."""

    def __init__(
        self,
        model_name: str | None = None,
        threshold: float | None = None,
        consecutive_frames_required: int | None = None,
        cooldown_seconds: float | None = None,
        inference_framework: str = "onnx",
    ):
        self.model_name = model_name or os.getenv("WAKE_WORD_MODEL", "hey_jarvis")
        self.threshold = (
            threshold
            if threshold is not None
            else float(os.getenv("WAKE_WORD_THRESHOLD", "0.60"))
        )
        self.consecutive_frames_required = (
            consecutive_frames_required
            if consecutive_frames_required is not None
            else int(os.getenv("WAKE_WORD_CONSECUTIVE_FRAMES", "3"))
        )
        self.cooldown_seconds = (
            cooldown_seconds
            if cooldown_seconds is not None
            else float(os.getenv("WAKE_WORD_COOLDOWN_SECONDS", "2.0"))
        )
        self.inference_framework = inference_framework

        self._model = None
        self._ready = False
        self._pcm_buffer = bytearray()
        self._consecutive_hits: dict[str, int] = {}
        self._last_detection_time = 0.0
        self._last_detection_monotonic = 0.0
        self._frame_count = 0

        # Telemetría
        self._total_detections = 0
        self._total_inferences = 0
        self._total_inference_ms = 0.0
        self._score_sum = 0.0
        self._last_detected_model = ""
        self._last_detected_score = 0.0
        self._last_detected_at = 0.0

        self._init_model()

    def _init_model(self) -> None:
        """Inicializa el modelo de openWakeWord."""
        try:
            import openwakeword.utils
            from openwakeword.model import Model

            # Descargar modelos pre-entrenados si no existen localmente
            try:
                openwakeword.utils.download_models()
            except Exception as dl_exc:
                print(f"\033[93m[WakeWord]\033[0m Descarga de modelos omitida: {dl_exc}")

            # Lista de modelos a cargar (soporta coma si se pasan varios)
            raw_models = [m.strip() for m in self.model_name.split(",") if m.strip()]
            if not raw_models:
                raw_models = ["hey_jarvis"]

            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            models_dir = os.path.join(project_root, "models")

            models_to_load = []
            for m in raw_models:
                # 1. ¿Es una ruta existente directa?
                if os.path.exists(m):
                    models_to_load.append(os.path.abspath(m))
                # 2. ¿Existe en models/ con nombre exacto?
                elif os.path.exists(os.path.join(models_dir, m)):
                    models_to_load.append(os.path.abspath(os.path.join(models_dir, m)))
                # 3. ¿Existe en models/ agregando .onnx?
                elif os.path.exists(os.path.join(models_dir, f"{m}.onnx")):
                    models_to_load.append(os.path.abspath(os.path.join(models_dir, f"{m}.onnx")))
                # 4. ¿Existe en project_root agregando .onnx?
                elif os.path.exists(os.path.join(project_root, f"{m}.onnx")):
                    models_to_load.append(os.path.abspath(os.path.join(project_root, f"{m}.onnx")))
                else:
                    # Modelo estándar pre-entrenado de openWakeWord
                    models_to_load.append(m)

            self._model = Model(
                wakeword_models=models_to_load,
                inference_framework=self.inference_framework,
            )
            self._ready = True
            for m in self._model.models.keys():
                self._consecutive_hits[m] = 0

            print(
                f"\033[36m[WakeWord]\033[0m Motor openWakeWord inicializado con éxito. "
                f"Modelos: {list(self._model.models.keys())} (umbral={self.threshold}, "
                f"histéresis={self.consecutive_frames_required} frames)"
            )
        except Exception as exc:
            self._ready = False
            self._model = None
            print(f"\033[91m[WakeWord] Error inicializando openWakeWord: {exc}\033[0m")

    def process_audio(self, pcm_bytes: bytes) -> WakeWordResult:
        """
        Ingesta bytes PCM (16 kHz, 16-bit mono), acumula en el buffer interno
        y ejecuta inferencia cuando hay al menos 1280 muestras.
        """
        if not self._ready or self._model is None or not pcm_bytes:
            return WakeWordResult(detected=False)

        now_m = time.monotonic()
        if (now_m - self._last_detection_monotonic) < self.cooldown_seconds:
            self._pcm_buffer.clear()
            return WakeWordResult(detected=False)

        self._pcm_buffer.extend(pcm_bytes)

        # Si aún no tenemos suficientes muestras para 1 frame (80ms), retornamos sin detectar
        if len(self._pcm_buffer) < CHUNK_BYTES:
            return WakeWordResult(detected=False)

        # Extraer exactamente 1 frame de 1280 muestras (2560 bytes)
        frame_bytes = bytes(self._pcm_buffer[:CHUNK_BYTES])
        del self._pcm_buffer[:CHUNK_BYTES]

        audio_array = np.frombuffer(frame_bytes, dtype=np.int16)
        self._frame_count += 1

        t0 = time.perf_counter()
        try:
            raw_scores_np = self._model.predict(audio_array)
            raw_scores: dict[str, float] = {str(k): float(v) for k, v in raw_scores_np.items()}
        except Exception as exc:
            print(f"\033[91m[WakeWord] Error durante inferencia: {exc}\033[0m")
            return WakeWordResult(detected=False)
        t_elapsed_ms = (time.perf_counter() - t0) * 1000.0

        # Actualizar telemetría de inferencia
        self._total_inferences += 1
        self._total_inference_ms += t_elapsed_ms

        now = time.time()
        detected = False
        detected_model = ""
        max_score = 0.0

        for model_key, score in raw_scores.items():
            self._score_sum += score
            if score > max_score:
                max_score = score
                detected_model = model_key

            # Evaluación de histéresis
            if score >= self.threshold:
                current_hits = self._consecutive_hits.get(model_key, 0) + 1
                self._consecutive_hits[model_key] = current_hits

                if (
                    current_hits >= self.consecutive_frames_required
                    and (now_m - self._last_detection_monotonic) >= self.cooldown_seconds
                ):
                    detected = True
                    detected_model = model_key
                    self._last_detection_monotonic = now_m
                    self._last_detection_time = now
                    self._consecutive_hits[model_key] = 0
                    self._total_detections += 1
                    self._last_detected_model = model_key
                    self._last_detected_score = score
                    self._last_detected_at = now
                    self.reset()
                    break
            else:
                self._consecutive_hits[model_key] = 0

        # Debugging: imprimir el score más alto cada ~800ms (10 frames)
        if self._frame_count % 10 == 0:
            print(f"\033[90m[WakeWord Debug] Frame {self._frame_count} - Max Score para {detected_model}: {max_score:.4f} (Threshold: {self.threshold})\033[0m")

        return WakeWordResult(
            detected=detected,
            model=detected_model,
            score=max_score,
            timestamp=now,
            processing_ms=round(t_elapsed_ms, 2),
            frame_index=self._frame_count,
            consecutive_hits=self._consecutive_hits.get(detected_model, 0),
            raw_scores=raw_scores,
        )

    def reset(self) -> None:
        """Reinicia buffers internos e histéresis."""
        self._pcm_buffer.clear()
        for k in self._consecutive_hits:
            self._consecutive_hits[k] = 0
        if self._model is not None:
            try:
                self._model.reset()
            except Exception:
                pass

    def is_ready(self) -> bool:
        return self._ready and self._model is not None

    def available_models(self) -> list[str]:
        if self._model is not None and hasattr(self._model, "models"):
            return list(self._model.models.keys())
        return []

    def get_metrics(self) -> dict:
        avg_ms = (
            round(self._total_inference_ms / self._total_inferences, 2)
            if self._total_inferences > 0
            else 0.0
        )
        avg_score = (
            round(self._score_sum / self._total_inferences, 4)
            if self._total_inferences > 0
            else 0.0
        )
        return {
            "ready": self.is_ready(),
            "models": self.available_models(),
            "threshold": self.threshold,
            "consecutive_frames_required": self.consecutive_frames_required,
            "cooldown_seconds": self.cooldown_seconds,
            "total_detections": self._total_detections,
            "total_inferences": self._total_inferences,
            "avg_inference_ms": avg_ms,
            "avg_score": avg_score,
            "last_detected_model": self._last_detected_model,
            "last_detected_score": round(self._last_detected_score, 4),
            "last_detected_at": self._last_detected_at,
        }
