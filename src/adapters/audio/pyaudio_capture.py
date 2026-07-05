"""
Módulo de captura de micrófono para JARVIS S2S.
Captura audio PCM en tiempo real usando PyAudio y lo deposita
en una cola asyncio para consumo no-bloqueante.
"""
import pyaudio
import asyncio
import os
import time
# pyrefly: ignore [missing-import]
from src.core.interfaces.audio import IAudioCapture


FORMAT   = pyaudio.paInt16
CHANNELS = 1
CHUNK    = 1024


class PyAudioCapture(IAudioCapture):
    def __init__(self, rate: int = 16000):
        self.rate = rate
        self._pa = pyaudio.PyAudio()
        self._stream = None
        self._queue = asyncio.Queue()
        self._recording = False
        self.noise_gate_enabled = os.getenv("MIC_NOISE_GATE_ENABLED", "1").lower() not in {"0", "false", "no", "off"}
        self._noise_gate_threshold_override = self._read_int_env("MIC_NOISE_GATE_THRESHOLD", 0)
        self._noise_gate_threshold = self._noise_gate_threshold_override
        self._noise_gate_min_threshold = self._read_int_env("MIC_NOISE_GATE_MIN_THRESHOLD", 180)
        self._noise_gate_padding = self._read_int_env("MIC_NOISE_GATE_PADDING", 80)
        self._noise_gate_calibration_chunks = self._read_int_env("MIC_NOISE_GATE_CALIBRATION_CHUNKS", 24)
        self._voice_hangover_chunks = self._read_int_env("MIC_VOICE_HANGOVER_CHUNKS", 24)
        self._noise_gate_multiplier = self._read_float_env("MIC_NOISE_GATE_MULTIPLIER", 3.0)
        self._recent_voice_window_seconds = self._read_float_env("MIC_RECENT_VOICE_WINDOW_SECONDS", 12.0)
        self._noise_gate_samples: list[int] = []
        self._noise_gate_ready = not self.noise_gate_enabled or self._noise_gate_threshold_override > 0
        self._voice_hangover_remaining = 0
        self._last_voice_monotonic = 0.0
        self._mic_debug_audio = os.getenv("MIC_DEBUG_AUDIO", "").lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _read_int_env(name: str, default: int) -> int:
        try:
            return max(0, int(os.getenv(name, str(default))))
        except ValueError:
            return default

    @staticmethod
    def _read_float_env(name: str, default: float) -> float:
        try:
            return max(0.1, float(os.getenv(name, str(default))))
        except ValueError:
            return default

    @staticmethod
    def _rms(in_data: bytes) -> int:
        try:
            import audioop
            return audioop.rms(in_data, 2)
        except ImportError:
            import struct
            count = len(in_data) // 2
            if count <= 0:
                return 0
            shorts = struct.unpack(f"<{count}h", in_data)
            return int((sum(s * s for s in shorts) / count) ** 0.5)

    def _apply_noise_gate(self, in_data: bytes) -> bytes:
        if not self.noise_gate_enabled:
            return in_data

        rms = self._rms(in_data)
        silence = b"\x00" * len(in_data)

        if not self._noise_gate_ready:
            self._noise_gate_samples.append(rms)
            if len(self._noise_gate_samples) >= self._noise_gate_calibration_chunks:
                sorted_samples = sorted(self._noise_gate_samples)
                noise_floor = sorted_samples[len(sorted_samples) // 2]
                self._noise_gate_threshold = max(
                    self._noise_gate_min_threshold,
                    int(noise_floor * self._noise_gate_multiplier) + self._noise_gate_padding,
                )
                self._noise_gate_ready = True
                print(
                    f"[Micrófono] Noise gate calibrado: floor={noise_floor}, "
                    f"threshold={self._noise_gate_threshold}"
                )
            return silence

        if rms >= self._noise_gate_threshold:
            self._last_voice_monotonic = time.monotonic()
            self._voice_hangover_remaining = self._voice_hangover_chunks
            if self._mic_debug_audio:
                print(f"[Micrófono] Voz detectada rms={rms} threshold={self._noise_gate_threshold}")
            return in_data

        if self._voice_hangover_remaining > 0:
            self._voice_hangover_remaining -= 1
            return in_data

        return silence

    def has_recent_voice(self, window_seconds: float | None = None) -> bool:
        if not self.noise_gate_enabled:
            return True
        window = self._recent_voice_window_seconds if window_seconds is None else window_seconds
        return (
            self._last_voice_monotonic > 0
            and time.monotonic() - self._last_voice_monotonic <= window
        )

    def reset_recent_voice(self) -> None:
        self._last_voice_monotonic = 0.0
        self._voice_hangover_remaining = 0

    def _find_input_device(self) -> int | None:
        """Busca un dispositivo de micrófono real evitando 'Mezcla estéreo'."""
        try:
            default_info = self._pa.get_default_input_device_info()
            idx = default_info.get('index')
            default_index = int(idx) if idx is not None else None
            default_name = str(default_info.get('name', '')).lower()

            # Si el por defecto no es mezcla estéreo ni stereo mix, lo usamos directamente
            if "mezcla" not in default_name and "stereo mix" not in default_name:
                print(f"[Micrófono] Usando dispositivo predeterminado: {default_info.get('name')} (Index {default_index})")
                return default_index

            # Si el predeterminado es Mezcla Estéreo, buscamos un micrófono real
            device_count = self._pa.get_device_count()
            for i in range(device_count):
                info = self._pa.get_device_info_by_index(i)
                max_channels_val = info.get('maxInputChannels')
                max_channels = int(max_channels_val) if max_channels_val is not None else 0
                if max_channels > 0:
                    name = str(info.get('name', '')).lower()
                    # Buscar micrófonos reales
                    if ("mic" in name or "microphone" in name or "array" in name or "microfono" in name) and "mezcla" not in name and "stereo mix" not in name:
                        print(f"[Micrófono] Detectada Mezcla Estéreo por defecto. Cambiando a micrófono real: {info.get('name')} (Index {i})")
                        return i

            print(f"[Micrófono] No se encontró un micrófono mejor. Usando por defecto: {default_info.get('name')} (Index {default_index})")
            return default_index
        except Exception as e:
            print(f"[Micrófono] Error buscando dispositivo de entrada: {e}")
            return None

    def start(self):
        """Abre el stream de entrada y comienza a capturar audio."""
        self._recording = True
        loop = asyncio.get_running_loop()

        def _callback(in_data, _frame_count, _time_info, _status):
            if self._recording:
                in_data = self._apply_noise_gate(in_data)

                try:
                    loop.call_soon_threadsafe(self._queue.put_nowait, in_data)
                except Exception as e:
                    print(f"[Micrófono] Overflow/Error: {e}")
            return (in_data, pyaudio.paContinue)

        device_index = self._find_input_device()
        self._stream = self._pa.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=self.rate,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=CHUNK,
            stream_callback=_callback,
        )
        self._stream.start_stream()
        print(f"[Micrófono] Captura iniciada a {self.rate} Hz")

    def stop(self):
        """Detiene la captura de audio."""
        self._recording = False
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        print("[Micrófono] Captura detenida.")

    async def read_chunk(self) -> bytes:
        """Devuelve el siguiente chunk de audio de forma asíncrona."""
        return await self._queue.get()

    def terminate(self):
        """Libera todos los recursos de PyAudio."""
        self.stop()
        self._pa.terminate()
