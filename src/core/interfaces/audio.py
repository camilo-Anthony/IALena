import abc

class IAudioCapture(abc.ABC):
    """Interfaz para la captura de audio (Micrófono)."""

    @abc.abstractmethod
    def start(self):
        """Inicia la captura de audio."""
        pass

    @abc.abstractmethod
    def terminate(self):
        """Detiene y cierra los recursos de captura."""
        pass

    @abc.abstractmethod
    async def read_chunk(self) -> bytes:
        """Lee un bloque de audio de forma asíncrona."""
        pass


class IAudioPlayback(abc.ABC):
    """Interfaz para la reproducción de audio (Altavoz)."""

    @abc.abstractmethod
    def start(self):
        """Inicia el reproductor de audio."""
        pass

    @abc.abstractmethod
    def terminate(self):
        """Detiene y cierra los recursos del reproductor."""
        pass

    @abc.abstractmethod
    def enqueue(self, data: bytes):
        """Añade un fragmento de audio a la cola de reproducción."""
        pass

    @abc.abstractmethod
    def flush(self):
        """Limpia la cola de reproducción actual (ej. interrupciones)."""
        pass
