"""
DeliveryQueue — Cola unificada de entrega de JARVIS.

Todos los resultados (LOCAL, FAST_HERMES, SLOW_HERMES) pasan por aquí
antes de ser inyectados a Gemini Live. La cola decide cuándo y en qué
orden hablar, sin que ningún módulo inyecte directamente al usuario.
"""
import asyncio
import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger("JARVIS.DeliveryQueue")


class DeliveryStatus(str, Enum):
    PENDING = "pending"
    DELIVERING = "delivering"
    DELIVERED = "delivered"
    DISCARDED = "discarded"


@dataclass
class DeliveryItem:
    """Unidad de entrega en la cola."""
    item_id: str
    task_id: str
    lane: str                       # "local" | "fast_hermes" | "slow_hermes"
    kind: str                       # "hermes_result" | "hermes_failure" | "local_response" | etc.
    text: str
    priority: int                   # Menor número = mayor prioridad
    source: str                     # Quien generó el item
    created_at: float = field(default_factory=time.monotonic)
    requires_active_session: bool = True
    discard_if_stale: bool = True   # Si True y hay item más nuevo del mismo task, se descarta
    turn_id: Optional[str] = None   # Turn de Synapse asociado
    status: DeliveryStatus = DeliveryStatus.PENDING

    def age_seconds(self) -> float:
        return time.monotonic() - self.created_at


class DeliveryQueue:
    """
    Cola única y centralizada para todo lo que JARVIS debe decir al usuario.

    Garantiza:
    - Orden por prioridad
    - No hablar mientras el usuario habla o el altavoz está activo
    - Descarte automático de resultados obsoletos
    - Visibilidad clara de qué está esperando entrega
    """

    def __init__(
        self,
        is_playback_busy_fn: Optional[Callable[[], bool]] = None,
        has_recent_voice_fn: Optional[Callable[[float], bool]] = None,
        get_session_fn: Optional[Callable] = None,
        idle_wait_seconds: float | Callable[[], float] = 1.0,
        poll_seconds: float | Callable[[], float] = 0.2,
        max_wait_seconds: float | Callable[[], float] = 12.0,
        recent_voice_window: float | Callable[[], float] = 1.5,
        log_interval_seconds: float | Callable[[], float] = 5.0,
    ):
        self._items: list[DeliveryItem] = []
        self._lock = asyncio.Lock()
        self.is_playback_busy = is_playback_busy_fn
        self.has_recent_voice = has_recent_voice_fn
        self.get_session = get_session_fn
        self._idle_wait_seconds = idle_wait_seconds
        self._poll_seconds = poll_seconds
        self._max_wait_seconds = max_wait_seconds
        self._recent_voice_window = recent_voice_window
        self._log_interval_seconds = log_interval_seconds

    @property
    def idle_wait_seconds(self) -> float:
        if callable(self._idle_wait_seconds):
            return self._idle_wait_seconds()
        return self._idle_wait_seconds

    @property
    def poll_seconds(self) -> float:
        if callable(self._poll_seconds):
            return self._poll_seconds()
        return self._poll_seconds

    @property
    def max_wait_seconds(self) -> float:
        if callable(self._max_wait_seconds):
            return self._max_wait_seconds()
        return self._max_wait_seconds

    @property
    def recent_voice_window(self) -> float:
        if callable(self._recent_voice_window):
            return self._recent_voice_window()
        return self._recent_voice_window

    @property
    def log_interval_seconds(self) -> float:
        if callable(self._log_interval_seconds):
            return self._log_interval_seconds()
        return self._log_interval_seconds


    # ── Enqueue / Peek / Discard ──────────────────────────────────────────

    def enqueue(self, item: DeliveryItem) -> None:
        """Añade un item a la cola."""
        self._items.append(item)
        print(
            f"[DeliveryQueue] enqueue item={item.item_id} task={item.task_id} lane={item.lane} "
            f"kind={item.kind} priority={item.priority} queue={len(self._items)}"
        )

    def make_item(
        self,
        text: str,
        lane: str,
        kind: str,
        priority: int,
        source: str,
        task_id: str = "",
        turn_id: Optional[str] = None,
        requires_active_session: bool = True,
        discard_if_stale: bool = True,
    ) -> DeliveryItem:
        """Factory helper para crear un DeliveryItem."""
        return DeliveryItem(
            item_id=str(uuid.uuid4()),
            task_id=task_id or str(uuid.uuid4()),
            lane=lane,
            kind=kind,
            text=text,
            priority=priority,
            source=source,
            turn_id=turn_id,
            requires_active_session=requires_active_session,
            discard_if_stale=discard_if_stale,
        )

    def peek_next(self) -> Optional[DeliveryItem]:
        """Devuelve el item de mayor prioridad sin quitarlo."""
        pending = [i for i in self._items if i.status == DeliveryStatus.PENDING]
        if not pending:
            return None
        return min(pending, key=lambda i: (i.priority, i.created_at))

    def discard(self, item: DeliveryItem, reason: str = "") -> None:
        """Marca un item como descartado y lo elimina de la cola."""
        item.status = DeliveryStatus.DISCARDED
        self._items = [i for i in self._items if i is not item]
        print(f"[DeliveryQueue] discard item={item.item_id} reason={reason}")

    def mark_delivering(self, item: DeliveryItem) -> None:
        item.status = DeliveryStatus.DELIVERING
        print(f"[DeliveryQueue] deliver item={item.item_id} task={item.task_id} lane={item.lane} kind={item.kind}")

    def mark_delivered(self, item: DeliveryItem) -> None:
        item.status = DeliveryStatus.DELIVERED
        self._items = [i for i in self._items if i is not item]
        print(f"[DeliveryQueue] delivered item={item.item_id}")

    def pending_count(self) -> int:
        return sum(1 for i in self._items if i.status == DeliveryStatus.PENDING)

    def delivering_count(self) -> int:
        return sum(1 for i in self._items if i.status == DeliveryStatus.DELIVERING)

    # ── Condiciones de entrega ────────────────────────────────────────────

    def _is_playback_busy(self) -> bool:
        if not self.is_playback_busy:
            return False
        try:
            return self.is_playback_busy()
        except Exception:
            return False

    def _has_recent_user_voice(self) -> bool:
        if not self.has_recent_voice:
            return False
        try:
            return self.has_recent_voice(self.recent_voice_window)
        except Exception:
            return False

    def _has_session(self) -> bool:
        if not self.get_session:
            return False
        try:
            return self.get_session() is not None
        except Exception:
            return False

    # ── Espera de slot natural ────────────────────────────────────────────

    async def wait_for_slot(self, item: DeliveryItem) -> bool:
        """
        Espera hasta que sea un momento natural para entregar el item.
        Devuelve True si se puede entregar, False si debe descartarse.
        """
        idle_since: Optional[float] = None
        next_log_at = time.monotonic() + self.log_interval_seconds

        while True:
            if item.status == DeliveryStatus.DISCARDED:
                return False

            now = time.monotonic()
            waited = now - item.created_at
            output_busy = self._is_playback_busy()
            user_recent = self._has_recent_user_voice()
            has_session = not item.requires_active_session or self._has_session()
            is_next = self.peek_next() is item
            max_wait_reached = self.max_wait_seconds > 0 and waited >= self.max_wait_seconds

            # Forzar entrega si se agotó el tiempo de espera (voz persistente)
            if has_session and is_next and not output_busy and user_recent and max_wait_reached:
                logger.info(
                    f"[DeliveryQueue] Entrega forzada tras {waited:.1f}s (voz_reciente_persistente): "
                    f"id={item.item_id[:8]}"
                )
                return True

            # Sin sesión y tiempo agotado → abortar
            if not has_session and max_wait_reached:
                logger.info(
                    f"[DeliveryQueue] Entrega abortada: sin sesión tras {waited:.1f}s, "
                    f"id={item.item_id[:8]}"
                )
                return False

            # Slot listo: hay sesión, es el próximo, sin playback, sin voz reciente
            ready = has_session and is_next and not output_busy and not user_recent
            if ready:
                if idle_since is None:
                    idle_since = now
                if now - idle_since >= self.idle_wait_seconds:
                    logger.info(
                        f"[DeliveryQueue] Slot disponible tras {waited:.1f}s: "
                        f"id={item.item_id[:8]}, kind={item.kind}"
                    )
                    return True
            else:
                idle_since = None

            if now >= next_log_at:
                pb_str = "true" if output_busy else "false"
                vr_str = "true" if user_recent else "false"
                se_str = "true" if has_session else "false"
                nx_str = "true" if is_next else "false"
                print(
                    f"[DeliveryQueue] wait item={item.item_id} playback={pb_str} "
                    f"voice_recent={vr_str} session={se_str} next={nx_str}"
                )
                next_log_at = now + self.log_interval_seconds

            await asyncio.sleep(self.poll_seconds)
