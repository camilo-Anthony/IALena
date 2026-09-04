"""
Módulo de reproducción de audio para JARVIS S2S.
Reproduce audio PCM recibido del servidor de voz en los altavoces
de forma continua usando PyAudio con cola thread-safe.
"""
import os
import time
import pyaudio
import queue
# pyrefly: ignore [missing-import]
from src.core.interfaces.audio import IAudioPlayback


FORMAT   = pyaudio.paInt16
CHANNELS = 1
CHUNK    = 1024


class PyAudioPlayback(IAudioPlayback):
    def __init__(self, rate: int = 24000):
        self.rate = rate
        self._pa = pyaudio.PyAudio()
        self._stream = None
        self._queue = queue.Queue()
        self._buffer = bytearray()
        self._playing = False
        self._last_active_at = 0.0
        self._hangover_seconds = max(0.05, float(os.getenv("PLAYBACK_AEC_HANGOVER_SECONDS", "0.15")))

    @property
    def is_busy(self) -> bool:
        """Devuelve True si todavía hay audio reproduciéndose o en la cola, más cola de decaimiento acústico."""
        now = time.monotonic()
        has_audio = (not self._queue.empty()) or (len(self._buffer) > 0)
        if has_audio:
            self._last_active_at = now
            return True
        return (now - self._last_active_at) < self._hangover_seconds

    def touch(self):
        """Marca actividad reciente de reproducción para suprimir eco anticipado."""
        self._last_active_at = time.monotonic()

    def start(self):
        """Abre el stream de salida y comienza a reproducir."""
        self._playing = True

        def _callback(_in_data, frame_count, _time_info, _status):
            if not self._playing:
                return (b"\x00" * (frame_count * 2), pyaudio.paComplete)

            needed = frame_count * 2

            # Transferir de la cola al buffer interno
            while not self._queue.empty():
                try:
                    self._buffer.extend(self._queue.get_nowait())
                except queue.Empty:
                    break

            # Extraer exactamente la cantidad de bytes requerida
            if len(self._buffer) >= needed:
                data = bytes(self._buffer[:needed])
                del self._buffer[:needed]
            else:
                # Si falta audio, reproducimos lo que hay y rellenamos con silencio temporalmente
                data = bytes(self._buffer) + b"\x00" * (needed - len(self._buffer))
                self._buffer.clear()

            return (data, pyaudio.paContinue)

        self._stream = self._pa.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=self.rate,
            output=True,
            frames_per_buffer=CHUNK,
            stream_callback=_callback,
        )
        self._stream.start_stream()
        print(f"[Altavoz] Reproducción iniciada a {self.rate} Hz")

    def enqueue(self, data: bytes):
        """Agrega audio PCM a la cola de reproducción."""
        if not self._playing:
            return
        self._last_active_at = time.monotonic()
        self._queue.put(data)

    def flush(self):
        """Vacía la cola y el buffer (para interrupciones)."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        self._buffer.clear()
        self._last_active_at = 0.0

    def stop(self):
        """Detiene la reproducción."""
        self._playing = False
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        self.flush()
        print("[Altavoz] Reproducción detenida.")

    def terminate(self):
        """Libera todos los recursos de PyAudio."""
        self.stop()
        self._pa.terminate()
