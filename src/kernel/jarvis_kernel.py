import asyncio
# pyrefly: ignore [missing-import]
from src.core.interfaces.audio import IAudioCapture, IAudioPlayback
# pyrefly: ignore [missing-import]
from src.core.interfaces.brain import IAgentBrain
# pyrefly: ignore [missing-import]
from src.core.interfaces.voice_llm import IVoiceAssistant
# pyrefly: ignore [missing-import]
from src.kernel.context_manager import ContextManager
# pyrefly: ignore [missing-import]
from src.kernel.action_router import ActionRouter

class JarvisKernel:
    """
    El núcleo (Kernel) del sistema JARVIS.
    Orquesta los componentes inyectados sin acoplarse a tecnologías concretas.
    """
    def __init__(
        self,
        audio_capture: IAudioCapture,
        audio_playback: IAudioPlayback,
        brain: IAgentBrain,
        voice_llm_factory,
        context_manager: ContextManager,
    ):
        self.audio_capture = audio_capture
        self.audio_playback = audio_playback
        self.brain = brain
        self.context_manager = context_manager
        
        # El router necesita referenciar a la sesión activa (closure), por lo que lo iniciamos aquí.
        # Guardaremos el voice_assistant una vez instanciado.
        self.voice_assistant: IVoiceAssistant | None = None
        
        self.action_router = ActionRouter(
            brain_adapter=self.brain,
            get_session_callback=lambda: getattr(self.voice_assistant, "session", None) if self.voice_assistant else None,
            is_busy_callback=lambda: getattr(self.audio_playback, "is_busy", False)
        )
        
        # Factory method para instanciar el adaptador LLM inyectando las dependencias base
        self.voice_assistant = voice_llm_factory(
            self.audio_capture,
            self.audio_playback,
            self.context_manager,
            self.action_router
        )
        
    async def boot(self):
        """Inicia todos los subsistemas y entra en el bucle principal."""
        print("[JARVIS Kernel] Inicializando subsistemas...")
        
        try:
            # En el futuro, el Event Bus se iniciaría aquí.
            
            # Arrancar la Voz (el carril rápido y principal por ahora)
            if self.voice_assistant:
                await self.voice_assistant.connect()
            else:
                print("[JARVIS Kernel] Error: Voice Assistant no instanciado.")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[JARVIS Kernel] Kernel Panic: {e}")
        finally:
            self.shutdown()
            
    def shutdown(self):
        """Apaga ordenadamente los subsistemas."""
        print("\n[JARVIS Kernel] Apagando de forma segura...")
        if self.voice_assistant:
            self.voice_assistant.stop()
