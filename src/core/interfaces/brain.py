import abc
from typing import Callable, Optional

class BrainResult:
    """Contenedor de resultados del cerebro (Hermes)."""
    def __init__(
        self,
        text: str,
        raw_text: str = "",
        success: bool = True,
        error: Optional[str] = None,
        interrupted: bool = False,
        events: Optional[list] = None,
        started_at: float = 0.0,
        finished_at: float = 0.0
    ):
        self.text = text or ""
        self.raw_text = raw_text or self.text
        self.success = success
        self.error = error
        self.interrupted = interrupted
        self.events = events or []
        self.started_at = started_at
        self.finished_at = finished_at

class IAgentBrain(abc.ABC):
    """Interfaz para el agente de inteligencia asíncrona de JARVIS"""

    model_brain: str = "unknown"

    @abc.abstractmethod
    async def run_task(self, task: str, event_listener: Optional[Callable] = None) -> BrainResult:
        """Ejecuta una tarea compleja en el cerebro y devuelve un BrainResult."""
        pass

    async def think(self, prompt: str, event_listener: Optional[Callable] = None) -> BrainResult:
        """Alias conveniente para run_task."""
        return await self.run_task(prompt, event_listener=event_listener)

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Devuelve True si el cerebro está listo para procesar peticiones."""
        pass

    @abc.abstractmethod
    def interrupt(self, reason: str = "Usuario interrumpió la tarea.") -> None:
        """Pide al cerebro que cancele su ejecución actual cooperativamente."""
        pass
