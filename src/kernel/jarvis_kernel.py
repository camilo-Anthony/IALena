import asyncio
# pyrefly: ignore [missing-import]
from src.core.interfaces.audio import IAudioCapture, IAudioPlayback
# pyrefly: ignore [missing-import]
from src.core.interfaces.audio_pipeline import IAudioPipeline
# pyrefly: ignore [missing-import]
from src.core.interfaces.brain import IAgentBrain
# pyrefly: ignore [missing-import]
from src.core.interfaces.voice_llm import IVoiceAssistant
# pyrefly: ignore [missing-import]
from src.core.interfaces.wake_word import IWakeWordDetector
from src.adapters.audio.audio_pipeline import AudioPipeline
from src.adapters.audio.openwakeword_detector import OpenWakeWordDetector
# pyrefly: ignore [missing-import]
from src.kernel.context_manager import ContextManager
# pyrefly: ignore [missing-import]
from src.kernel.action_router import ActionRouter
from src.kernel.activation_gate import ActivationGate
from src.kernel.cognitive_policy import CognitivePolicy
from src.kernel.conversation_session import ConversationSessionManager, SessionMemoryConsolidator
from src.kernel.synapse import Synapse
from src.kernel.task_ledger import TaskLedger
from src.kernel.memory_consolidator import MemoryConsolidator
from src.kernel.hermes_scheduler_runner import HermesSchedulerRunner
from src.kernel.system_sentinel import SystemSentinel


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
        brain_fast: IAgentBrain | None = None,
        wake_word_detector: IWakeWordDetector | None = None,
        audio_pipeline: IAudioPipeline | None = None,
    ):
        self.audio_capture = audio_capture
        self.audio_playback = audio_playback
        self.brain = brain
        self.brain_fast = brain_fast
        self.context_manager = context_manager

        # Iniciar EventBus y Gates
        self.synapse = Synapse()
        self.activation_gate = ActivationGate()
        self.cognitive_policy = CognitivePolicy()
        self.task_ledger = TaskLedger()

        # Wake Word & Audio Pipeline
        if wake_word_detector is not None:
            self.wake_word_detector = wake_word_detector
        else:
            self.wake_word_detector = OpenWakeWordDetector()

        if audio_pipeline is not None:
            self.audio_pipeline = audio_pipeline
        elif isinstance(audio_capture, IAudioPipeline):
            self.audio_pipeline = audio_capture
        else:
            self.audio_pipeline = AudioPipeline(
                raw_capture=self.audio_capture,
                wake_word_detector=self.wake_word_detector,
                activation_gate=self.activation_gate,
                synapse=self.synapse,
            )

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
                self.audio_pipeline.has_recent_voice(window)
                if hasattr(self.audio_pipeline, "has_recent_voice")
                else False
            ),
            activation_gate=self.activation_gate,
            task_ledger=self.task_ledger,
            conversation_sessions=self.conversation_sessions,
            brain_fast=self.brain_fast,
        )

        self.memory_consolidator = MemoryConsolidator(
            synapse=self.synapse,
            get_hermes_home_fn=self.context_manager.get_hermes_home,
        )

        self.hermes_scheduler = HermesSchedulerRunner(
            synapse=self.synapse,
            activation_gate=self.activation_gate,
            action_router=self.action_router,
        )

        self.system_sentinel = SystemSentinel(
            synapse=self.synapse,
            activation_gate=self.activation_gate,
            action_router=self.action_router,
        )

        # Factory method para instanciar el adaptador LLM inyectando el AudioPipeline
        self.voice_assistant = voice_llm_factory(
            self.audio_pipeline,
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
            loop = asyncio.get_running_loop()
            self.synapse.attach_loop(loop)

            # Iniciar motor de auto-aprendizaje pasivo
            self.memory_consolidator.start(loop)

            # Iniciar scheduler nativo de Hermes
            self.hermes_scheduler.start(loop)

            # Iniciar centinela autónomo del sistema
            self.system_sentinel.start(loop)

            # Iniciar puente bidireccional de Telegram si está configurado
            try:
                from src.adapters.notifications.telegram_bridge import get_telegram_bridge
                self.telegram_bridge = get_telegram_bridge(
                    dispatch_fn=self.action_router.submit_external_prompt
                )
                if self.telegram_bridge.is_configured:
                    self.telegram_bridge.start()
            except Exception as bridge_err:
                print(f"[JARVIS Kernel] Error iniciando TelegramBridge: {bridge_err}")

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
        if hasattr(self, "telegram_bridge") and self.telegram_bridge:
            self.telegram_bridge.stop()
        if hasattr(self, "system_sentinel") and self.system_sentinel:
            self.system_sentinel.stop()
        if hasattr(self, "hermes_scheduler") and self.hermes_scheduler:
            self.hermes_scheduler.stop()
        if self.memory_consolidator:
            self.memory_consolidator.stop()
        if self.voice_assistant:
            self.voice_assistant.stop()
