import asyncio
import inspect
import logging
from enum import Enum
from typing import Dict, Any, Callable, List, Optional
import uuid
import time

logger = logging.getLogger("JARVIS.Synapse")

class TurnState(str, Enum):
    LISTENING = "listening"
    THINKING = "thinking"
    ACKNOWLEDGING = "acknowledging"
    BRAIN_RUNNING = "brain_running"
    CANCEL_REQUESTED = "cancel_requested"
    INJECTING_RESULT = "injecting_result"
    SPEAKING = "speaking"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    STALE = "stale"

class TurnRecord:
    """Registra la historia, el estado y el resultado de un turno conversacional."""
    def __init__(self, turn_id: str, user_prompt: str = ""):
        self.turn_id = turn_id
        self.user_prompt = user_prompt
        self.state: TurnState = TurnState.LISTENING
        self.ack_message = ""
        self.brain_task: Optional[asyncio.Task] = None
        self.brain_result = None  # BrainResult
        self.error: Optional[str] = None
        self.tool_calls: List[Dict[str, Any]] = []
        self.history: List[tuple[str, float]] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "user_prompt": self.user_prompt,
            "state": self.state.value,
            "ack_message": self.ack_message,
            "error": self.error,
            "tool_calls": self.tool_calls,
        }

class Synapse:
    """
    EventBus y Gestor de Estados pasivo de JARVIS
    Maneja el estado del turno conversacional y expone una cola de eventos
    para sincronizar los adaptadores de forma segura entre hilos.
    """
    def __init__(self):
        self._listeners: Dict[str, List[Callable[..., Any]]] = {}
        self.active_turn: Optional[TurnRecord] = None
        self.last_turn: Optional[TurnRecord] = None
        self._history_turns: List[TurnRecord] = []
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def attach_loop(self, loop: asyncio.AbstractEventLoop):
        """Asocia el event loop activo para el enrutamiento de eventos thread-safe."""
        self.loop = loop

    def subscribe(self, event_type: str, callback: Callable[..., Any]):
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def publish(self, event_type: str, *args, **kwargs):
        """
        Publica un evento a los suscriptores.
        Si se invoca desde otro hilo (ej. callbacks de Hermes), enruta al event loop principal.
        """
        callbacks = self._listeners.get(event_type, [])
        if not callbacks:
            return

        def _dispatch():
            for cb in callbacks:
                try:
                    if inspect.iscoroutinefunction(cb):
                        if self.loop and self.loop.is_running():
                            self.loop.create_task(cb(*args, **kwargs))
                    else:
                        cb(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error en callback de evento '{event_type}': {e}")

        # Thread-safe routing
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(_dispatch)
        else:
            # Si no hay loop (ej. modo testing síncrono), despachamos directo
            _dispatch()

    emit = publish
    on = subscribe

    def create_turn(self, user_prompt: str = "") -> TurnRecord:
        """Inicia un nuevo turno, generando un turn_id único."""
        # Nota: La orquestación de cancelación de tareas viejas
        # la maneja ActionRouter; Synapse es puramente pasivo en cuanto a ejecución.
        turn_id = str(uuid.uuid4())
        turn = TurnRecord(turn_id, user_prompt)

        self.active_turn = turn
        self._history_turns.append(turn)

        if len(self._history_turns) > 50:
            self._history_turns.pop(0)

        turn.history.append((TurnState.LISTENING.value, time.monotonic()))
        self.publish("turn_created", turn)
        return turn

    def change_state(self, state: TurnState, turn_id: Optional[str] = None):
        """Cambia el estado de un turno y publica el evento."""
        target_turn = self.active_turn

        if turn_id:
            if self.active_turn and self.active_turn.turn_id == turn_id:
                target_turn = self.active_turn
            else:
                target_turn = next((t for t in self._history_turns if t.turn_id == turn_id), None)

        if not target_turn:
            return

        old_state = target_turn.state
        if old_state == state:
            return

        target_turn.state = state
        ts = time.monotonic()
        target_turn.history.append((state.value, ts))

        if target_turn == self.active_turn:
            self.publish("turn_state_changed", target_turn, old_state, state)
            if state in (TurnState.COMPLETED, TurnState.FAILED, TurnState.INTERRUPTED, TurnState.STALE):
                self.last_turn = target_turn
                # Para STALE, mantenemos active_turn hasta que la brain_task drene,
                # para que has_unfinished_brain_task() funcione correctamente.
                if state != TurnState.STALE or (
                    target_turn.brain_task is None or target_turn.brain_task.done()
                ):
                    self.active_turn = None
