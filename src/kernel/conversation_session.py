import asyncio
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Any

from src.core.interfaces.brain import IAgentBrain, BrainResult


LEARNING_SIGNAL_TERMS = (
    "prefiero",
    "preferiria",
    "me gusta que",
    "no me gusta",
    "no hagas",
    "no digas",
    "no me digas",
    "siempre",
    "recuerda que",
    "acuerdate",
    "llamame",
    "mi nombre es",
    "me llamo",
    "quiero que",
    "corrige",
    "corrige eso",
    "asi no",
    "hazlo asi",
)


@dataclass
class ConversationEvent:
    role: str
    text: str
    kind: str = "speech"
    timestamp: float = field(default_factory=time.time)


@dataclass
class ConversationSession:
    session_id: str
    started_at: float
    session_epoch: int = 0
    events: list[ConversationEvent] = field(default_factory=list)
    ended_at: float | None = None
    close_reason: str = ""

    def add_event(self, role: str, text: str, kind: str = "speech") -> None:
        clean = (text or "").strip()
        if not clean:
            return
        self.events.append(ConversationEvent(role=role, text=clean, kind=kind))

    def transcript_text(self, max_chars: int = 6000) -> str:
        lines = []
        for event in self.events:
            label = event.role.upper()
            lines.append(f"{label}[{event.kind}]: {event.text}")
        text = "\n".join(lines)
        if len(text) > max_chars:
            return text[-max_chars:]
        return text

    def to_hermes_messages(self) -> list[dict]:
        messages: list[dict] = []
        role_map = {"assistant": "assistant", "user": "user", "system": "system"}
        for event in self.events:
            role = role_map.get(event.role, "user")
            content = event.text if event.role != "system" else f"[system event: {event.kind}] {event.text}"
            messages.append({"role": role, "content": content})
        return messages

    def has_learning_signal(self) -> bool:
        text = " ".join(
            event.text.lower()
            for event in self.events
            if event.role == "user"
        )
        return any(term in text for term in LEARNING_SIGNAL_TERMS)


class SessionMemoryConsolidator:
    """Envia sesiones cerradas a Hermes para extraer memoria persistente."""

    def __init__(
        self,
        brain: IAgentBrain,
        can_run_callback: Callable[[], bool] | None = None,
    ):
        self.brain = brain
        self.can_run = can_run_callback
        self.enabled = os.getenv("SESSION_MEMORY_CONSOLIDATION_ENABLED", "1").lower() not in {
            "0",
            "false",
            "no",
            "off",
        }
        self.min_chars = self._read_int_env("SESSION_MEMORY_MIN_CHARS", 40)
        self.defer_seconds = self._read_float_env("SESSION_MEMORY_DEFER_SECONDS", 1.0)
        self.max_wait_seconds = self._read_float_env("SESSION_MEMORY_MAX_WAIT_SECONDS", 30.0)
        self.skill_review_enabled = os.getenv("SESSION_SKILL_REVIEW_ENABLED", "1").lower() not in {
            "0",
            "false",
            "no",
            "off",
        }

    @staticmethod
    def _read_int_env(name: str, default: int) -> int:
        try:
            return max(0, int(os.getenv(name, str(default))))
        except ValueError:
            return default

    @staticmethod
    def _read_float_env(name: str, default: float) -> float:
        try:
            return max(0.0, float(os.getenv(name, str(default))))
        except ValueError:
            return default

    async def consolidate(self, session: ConversationSession) -> BrainResult | None:
        if not self.enabled:
            return None

        transcript = session.transcript_text()
        if len(transcript.strip()) < self.min_chars:
            print(f"[SessionMemory] SessionMemory skipped_too_short session={session.session_id} len={len(transcript)}")
            return None

        await asyncio.sleep(self.defer_seconds)
        deadline = time.monotonic() + self.max_wait_seconds
        while self.can_run and not self.can_run() and time.monotonic() < deadline:
            await asyncio.sleep(0.5)

        prompt = (
            "[CONSOLIDACION DE MEMORIA DE SESION DE VOZ]\n"
            "Analiza la sesion cerrada de JARVIS. Guarda memoria persistente SOLO si hay datos utiles y estables.\n"
            "Candidatos validos: nombre del usuario, preferencias, estilo de trato, datos personales que el usuario quiso compartir, "
            "hechos persistentes de proyectos, instrucciones futuras, o preferencias de personalidad del asistente.\n"
            "NO guardes preguntas pasajeras, comandos temporales, resultados tecnicos efimeros, ni suposiciones.\n"
            "Si no hay nada que guardar, responde exactamente: SIN_MEMORIA_NUEVA.\n"
            "Si guardas algo, usa las herramientas de memoria disponibles de Hermes y responde con un resumen breve de lo guardado.\n\n"
            f"ID_SESION: {session.session_id}\n"
            f"MOTIVO_CIERRE: {session.close_reason}\n"
            f"TRANSCRIPCION:\n{transcript}"
        )

        print(f"[SessionMemory] Consolidando sesion {session.session_id} con Hermes.")
        review_skills = self.skill_review_enabled and session.has_learning_signal()
        review_session_memory: Any = getattr(self.brain, "review_session_memory", None)
        if callable(review_session_memory):
            try:
                return await review_session_memory(  # type: ignore
                    session.to_hermes_messages(),
                    review_skills=review_skills,
                )
            except TypeError:
                return await review_session_memory(session.to_hermes_messages())  # type: ignore
        if review_skills:
            prompt += (
                "\n\n[REVISION DE APRENDIZAJE]\n"
                "La sesion contiene una senal de preferencia o correccion durable. "
                "Si corresponde, actualiza tambien habilidades o reglas de comportamiento de Hermes."
            )
        return await self.brain.run_task(prompt)


class ConversationSessionManager:
    """Mantiene sesiones de voz separadas de las reconexiones Gemini Live."""

    def __init__(self, consolidator: SessionMemoryConsolidator | None = None):
        self.consolidator = consolidator
        self.active_session: ConversationSession | None = None
        self.closed_sessions: list[ConversationSession] = []
        self._consolidation_tasks: set[asyncio.Task] = set()

    def ensure_active_session(self, session_epoch: int = 0) -> ConversationSession:
        if self.active_session and self.active_session.ended_at is None:
            return self.active_session
        session = ConversationSession(
            session_id=str(uuid.uuid4()),
            started_at=time.time(),
            session_epoch=session_epoch,
        )
        self.active_session = session
        print(f"[ConversationSession] Sesion iniciada: {session.session_id} epoch={session_epoch}")
        return session

    def record_user(self, text: str, kind: str = "speech", session_epoch: int = 0) -> None:
        session = self.ensure_active_session(session_epoch)
        session.add_event("user", text, kind)

    def record_assistant(self, text: str, kind: str = "speech", session_epoch: int = 0) -> None:
        session = self.ensure_active_session(session_epoch)
        session.add_event("assistant", text, kind)

    def record_system(self, text: str, kind: str = "event", session_epoch: int = 0) -> None:
        session = self.ensure_active_session(session_epoch)
        session.add_event("system", text, kind)

    def active_context_text(self, max_chars: int = 2000) -> str:
        session = self.active_session
        if not session or session.ended_at is not None or not session.events:
            return ""
        return session.transcript_text(max_chars=max_chars)

    def close_active_session(self, reason: str) -> ConversationSession | None:
        session = self.active_session
        if not session or session.ended_at is not None:
            return None
        session.ended_at = time.time()
        session.close_reason = reason
        self.closed_sessions.append(session)
        self.active_session = None
        print(
            f"[ConversationSession] Sesion cerrada: {session.session_id} "
            f"reason={reason}, events={len(session.events)}"
        )
        self._schedule_consolidation(session)
        return session

    def _schedule_consolidation(self, session: ConversationSession) -> None:
        if not self.consolidator:
            return
        if not session.events:
            print(f"[SessionMemory] SessionMemory skipped_empty session={session.session_id}")
            return

        transcript = session.transcript_text()
        if len(transcript.strip()) < self.consolidator.min_chars:
            print(f"[SessionMemory] SessionMemory skipped_too_short session={session.session_id} len={len(transcript)}")
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        print(f"[SessionMemory] SessionMemory review_started session={session.session_id}")
        task = loop.create_task(self.consolidator.consolidate(session))
        self._consolidation_tasks.add(task)
        task.add_done_callback(lambda completed: self._on_consolidation_done(session, completed))

    def _on_consolidation_done(self, session: ConversationSession, task: asyncio.Task) -> None:
        self._consolidation_tasks.discard(task)
        try:
            result = task.result()
        except asyncio.CancelledError:
            print(f"[SessionMemory] SessionMemory review_failed reason=cancelled session={session.session_id}")
            return
        except Exception as exc:
            print(f"[SessionMemory] SessionMemory review_failed reason={exc} session={session.session_id}")
            return

        if result is None:
            print(f"[SessionMemory] SessionMemory review_completed session={session.session_id}")
            return
        if result.success:
            print(f"[SessionMemory] SessionMemory review_completed session={session.session_id}")
        else:
            print(
                f"[SessionMemory] SessionMemory review_failed reason={result.error or 'sin detalle'} "
                f"session={session.session_id}"
            )
