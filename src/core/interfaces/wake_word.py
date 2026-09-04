from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import time


@dataclass
class WakeWordResult:
    """Resultado estructurado de inferencia del detector de Wake Word."""
    detected: bool = False
    model: str = ""
    score: float = 0.0
    timestamp: float = field(default_factory=time.time)
    processing_ms: float = 0.0
    frame_index: int = 0
    consecutive_hits: int = 0
    raw_scores: dict[str, float] = field(default_factory=dict)


class IWakeWordDetector(ABC):
    """Interfaz para detectores de palabras de activación (Wake Word)."""

    @abstractmethod
    def process_audio(self, pcm_bytes: bytes) -> WakeWordResult:
        """
        Procesa un chunk de audio PCM (16 kHz, 16-bit mono) y retorna
        un WakeWordResult estructurado.
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reinicia los buffers internos y el estado de histéresis."""
        pass

    @abstractmethod
    def is_ready(self) -> bool:
        """Indica si el modelo está cargado y listo para inferir."""
        pass

    @abstractmethod
    def available_models(self) -> list[str]:
        """Lista de modelos de wake word cargados en memoria."""
        pass

    @abstractmethod
    def get_metrics(self) -> dict:
        """Devuelve un diccionario con telemetría de rendimiento y detecciones."""
        pass
