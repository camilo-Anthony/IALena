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
from src.kernel.activation_gate import ActivationGate
from src.kernel.cognitive_policy import CognitivePolicy
from src.kernel.conversation_session import ConversationSessionManager, SessionMemoryConsolidator
from src.kernel.synapse import Synapse
from src.kernel.task_ledger import TaskLedger


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

        # Iniciar EventBus
        self.synapse = Synapse()
        self.activation_gate = ActivationGate()
        self.cognitive_policy = CognitivePolicy()
        self.task_ledger = TaskLedger()
        self.conversation_sessions = ConversationSessionManager(
            SessionMemoryConsolidator(
                self.brain,
                can_run_callback=lambda: not self.action_router.has_active_work()
                if hasattr(self, "action_router")
                else True,
            )
        )
        self.context_manager.set_active_session_context_provider(
            lambda: self.conversation_sessions.active_context_text()
        )

        self.voice_assistant: IVoiceAssistant | None = None

        self.action_router = ActionRouter(
            brain_adapter=self.brain,
            synapse=self.synapse,
            get_session_callback=lambda: getattr(self.voice_assistant, "session", None) if self.voice_assistant else None,
            is_busy_callback=lambda: getattr(self.audio_playback, "is_busy", False),
            has_recent_voice_callback=lambda window=None: (
                self.audio_capture.has_recent_voice(window)
                if hasattr(self.audio_capture, "has_recent_voice")
                else False
            ),
            activation_gate=self.activation_gate,
            task_ledger=self.task_ledger,
            conversation_sessions=self.conversation_sessions,
        )
        
        # Factory method para instanciar el adaptador LLM inyectando las dependencias base
        self.voice_assistant = voice_llm_factory(
            self.audio_capture,
            self.audio_playback,
            self.context_manager,
            self.action_router,
            self.activation_gate,
            self.conversation_sessions,
            self.cognitive_policy,
        )
        
    async def boot(self):
        """Inicia todos los subsistemas y entra en el bucle principal."""
        print("[JARVIS Kernel] Inicializando subsistemas...")
        
        try:
            # Asociar el loop actual a Synapse para callbacks asíncronos seguros
            self.synapse.attach_loop(asyncio.get_running_loop())
            
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
