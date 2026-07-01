import abc

class IAgentBrain(abc.ABC):
    """Interfaz para el agente de inteligencia asíncrona de J.A.R.V.I.S."""

    @abc.abstractmethod
    def chat(self, prompt: str) -> str:
        """Envía una instrucción compleja al cerebro y devuelve el resultado."""
        pass
        
    @abc.abstractmethod
    def is_available(self) -> bool:
        """Devuelve True si el cerebro está listo para procesar peticiones."""
        pass
