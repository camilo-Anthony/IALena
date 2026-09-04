from __future__ import annotations
from abc import ABC, abstractmethod
# pyrefly: ignore [missing-import]
from src.core.interfaces.audio import IAudioCapture


class IAudioPipeline(IAudioCapture, ABC):
    """
    Interfaz para el Pipeline de Audio desacoplado de JARVIS.
    Combina captura de micrófono, RingBuffer (pre-roll), detección Wake Word
    y enrutamiento reactivo hacia Gemini Live y subsistemas.
    """

    @abstractmethod
    def start(self) -> None:
        """Inicia los hilos y tareas del pipeline de audio."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Detiene el pipeline de audio."""
        pass

    @abstractmethod
    def terminate(self) -> None:
        """Libera todos los recursos de hardware y audio."""
        pass

    @abstractmethod
    def get_metrics(self) -> dict:
        """Retorna telemetría del pipeline, RingBuffer y Wake Word."""
        pass
