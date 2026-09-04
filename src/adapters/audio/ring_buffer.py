"""
ring_buffer.py — Buffer circular de bytes thread-safe para audio PCM.

Almacena continuamente los últimos N milisegundos de audio capturado
para permitir la inyección de Pre-roll (audio previo al despertar) al
momento de detectar la palabra clave (Wake Word).
"""
from __future__ import annotations
import threading


class RingBuffer:
    """
    Buffer circular de bytes thread-safe de longitud fija.
    """

    def __init__(self, capacity_bytes: int = 64000):
        """
        :param capacity_bytes: Capacidad máxima en bytes.
                               (64000 bytes = 2 segundos de PCM 16kHz 16-bit mono).
        """
        self.capacity = max(2, capacity_bytes)
        self._buffer = bytearray(self.capacity)
        self._write_pos = 0
        self._size = 0
        self._lock = threading.Lock()

    def write(self, data: bytes) -> None:
        """Escribe un bloque de bytes en el buffer circular."""
        if not data:
            return

        data_len = len(data)
        with self._lock:
            if data_len >= self.capacity:
                # Si el dato entrante es mayor que la capacidad total, guardamos solo la cola
                tail = data[-self.capacity:]
                self._buffer[:] = tail
                self._write_pos = 0
                self._size = self.capacity
                return

            end_pos = self._write_pos + data_len
            if end_pos <= self.capacity:
                self._buffer[self._write_pos:end_pos] = data
            else:
                first_part = self.capacity - self._write_pos
                self._buffer[self._write_pos:self.capacity] = data[:first_part]
                second_part = data_len - first_part
                self._buffer[0:second_part] = data[first_part:]

            self._write_pos = (self._write_pos + data_len) % self.capacity
            self._size = min(self.capacity, self._size + data_len)

    def get_last_bytes(self, num_bytes: int) -> bytes:
        """
        Extrae los últimos `num_bytes` escritos en orden cronológico correcto.
        """
        with self._lock:
            if self._size == 0 or num_bytes <= 0:
                return b""

            to_read = min(self._size, num_bytes)
            # Aseguramos alineación de muestras a 16-bit (2 bytes por muestra)
            if to_read % 2 != 0:
                to_read -= 1

            start_pos = (self._write_pos - to_read) % self.capacity
            if start_pos + to_read <= self.capacity:
                return bytes(self._buffer[start_pos:start_pos + to_read])
            else:
                first_part = self.capacity - start_pos
                second_part = to_read - first_part
                return bytes(self._buffer[start_pos:self.capacity] + self._buffer[0:second_part])

    def get_last_ms(self, duration_ms: int, sample_rate: int = 16000) -> bytes:
        """
        Extrae los últimos `duration_ms` milisegundos de audio PCM 16-bit mono.
        """
        bytes_per_sample = 2  # 16-bit
        channels = 1
        bytes_per_second = sample_rate * bytes_per_sample * channels
        bytes_needed = int((duration_ms / 1000.0) * bytes_per_second)
        return self.get_last_bytes(bytes_needed)

    def clear(self) -> None:
        """Vacía el buffer circular."""
        with self._lock:
            self._write_pos = 0
            self._size = 0

    def __len__(self) -> int:
        with self._lock:
            return self._size
