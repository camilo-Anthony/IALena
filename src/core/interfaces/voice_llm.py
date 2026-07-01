import abc

class IVoiceAssistant(abc.ABC):
    """Interfaz para el modelo LLM en tiempo real de voz (Gemini Live)."""
    
    @abc.abstractmethod
    async def connect(self):
        """Inicia el bucle de conexión asíncrona del asistente."""
        pass
        
    @abc.abstractmethod
    def stop(self):
        """Detiene el bucle y cierra la conexión."""
        pass
