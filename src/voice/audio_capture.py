"""
Módulo de captura de micrófono para IALena S2S.
Captura audio PCM en tiempo real usando PyAudio y lo deposita
en una cola asyncio para consumo no-bloqueante.
"""
import pyaudio
import asyncio


FORMAT   = pyaudio.paInt16
CHANNELS = 1
CHUNK    = 1024


class AudioCapture:
    def __init__(self, rate: int = 16000):
        self.rate = rate
        self._pa = pyaudio.PyAudio()
        self._stream = None
        self._queue = asyncio.Queue()
        self._recording = False

    def start(self):
        """Abre el stream de entrada y comienza a capturar audio."""
        self._recording = True
        loop = asyncio.get_running_loop()

        def _callback(in_data, _frame_count, _time_info, _status):
            if self._recording:
                # --- NOISE GATE (Filtro de ruido) ---
                # Evita que el propio altavoz o el ruido de fondo interrumpan a la IA.
                try:
                    import audioop
                    rms = audioop.rms(in_data, 2)
                except ImportError:
                    # Fallback si usa Python >= 3.13 donde audioop no existe
                    import struct, math
                    count = len(in_data) // 2
                    shorts = struct.unpack(f"<{count}h", in_data)
                    rms = math.sqrt(sum(s*s for s in shorts) / count) if count > 0 else 0

                # Bajamos el umbral a 200 porque micrófonos de bajo volumen eran cortados.
                THRESHOLD = 200  
                if rms < THRESHOLD:
                    # Si el sonido es muy bajo, lo silenciamos por completo
                    in_data = b'\x00' * len(in_data)

                try:
                    loop.call_soon_threadsafe(self._queue.put_nowait, in_data)
                except Exception as e:
                    print(f"[Micrófono] Overflow/Error: {e}")
            return (in_data, pyaudio.paContinue)

        self._stream = self._pa.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=self.rate,
            input=True,
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
