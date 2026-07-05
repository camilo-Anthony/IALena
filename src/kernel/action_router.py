import os
import sys
import time
import json
import random
import asyncio
import unicodedata
from datetime import datetime
from dataclasses import dataclass, field
from google.genai import types

# pyrefly: ignore [missing-import]
from src.core.interfaces.brain import IAgentBrain
from src.kernel.synapse import Synapse, TurnState


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_LOCAL_YOUTUBE_SCRIPT = os.path.join(_PROJECT_ROOT, "src", "adapters", "llm", "play_yt.py")


@dataclass
class PendingDelivery:
    priority: int
    sequence: int
    turn_id: str
    text: str
    kind: str
    created_at: float = field(default_factory=time.monotonic)


class ActionRouter:
    """Enruta peticiones complejas de la voz hacia el cerebro asíncrono, orquestando el Synapse."""
    _MUSIC_TERMS = (
        "youtube",
        "musica",
        "cancion",
        "canciones",
        "video",
        "reproduce",
        "reproducir",
        "pon",
        "ponme",
        "escuchar",
        "play",
    )
    _MUSIC_NEGATIVE_TERMS = (
        "no pongas",
        "no reproduzcas",
        "no quiero escuchar",
        "no abras youtube",
    )
    _ACTIVE_STATES = {
        TurnState.THINKING,
        TurnState.ACKNOWLEDGING,
        TurnState.BRAIN_RUNNING,
        TurnState.CANCEL_REQUESTED,
        TurnState.INJECTING_RESULT,
        TurnState.SPEAKING,
    }
    
    def __init__(
        self,
        brain_adapter: IAgentBrain,
        synapse: Synapse,
        get_session_callback,
        is_busy_callback=None,
        has_recent_voice_callback=None,
        activation_gate=None,
        task_ledger=None,
        conversation_sessions=None,
    ):
        self.brain = brain_adapter
        self.synapse = synapse
        self.get_session = get_session_callback
        self.is_busy = is_busy_callback
        self.has_recent_voice = has_recent_voice_callback
        self.activation_gate = activation_gate
        self.task_ledger = task_ledger
        self.conversation_sessions = conversation_sessions
        self._tool_call_reserved = False
        self._queued_task_runner = None
        self._pending_deliveries: list[PendingDelivery] = []
        self._delivery_sequence = 0
        self._delivery_idle_seconds = self._read_float_env("RESULT_DELIVERY_IDLE_SECONDS", 1.0)
        self._delivery_poll_seconds = self._read_float_env("RESULT_DELIVERY_POLL_SECONDS", 0.2)
        self._delivery_recent_voice_seconds = self._read_float_env("RESULT_DELIVERY_RECENT_VOICE_SECONDS", 1.5)
        self._delivery_max_wait_seconds = self._read_float_env("RESULT_DELIVERY_MAX_WAIT_SECONDS", 12.0)
        self._delivery_log_seconds = self._read_float_env("RESULT_DELIVERY_LOG_SECONDS", 5.0)
        
        self._ACKS = [
            "Entendido, dame un momento para revisarlo.",
            "Claro, estoy en ello. Un segundo...",
            "Perfecto, lo estoy buscando. Regreso en un segundo.",
            "De acuerdo, trabajando en eso. Un momento."
        ]

    @staticmethod
    def _read_float_env(name: str, default: float) -> float:
        try:
            return max(0.0, float(os.getenv(name, str(default))))
        except ValueError:
            return default

    def is_turn_active(self) -> bool:
        active = self.synapse.active_turn
        return bool(active and active.state in self._ACTIVE_STATES)

    def has_unfinished_brain_task(self) -> bool:
        active = self.synapse.active_turn
        return bool(active and active.brain_task and not active.brain_task.done())

    def can_accept_tool_call(self) -> bool:
        return (
            not self._tool_call_reserved
            and not self.is_turn_active()
            and not self.has_unfinished_brain_task()
        )

    def has_active_work(self) -> bool:
        return self.is_turn_active() or self.has_unfinished_brain_task()

    def _is_playback_busy(self) -> bool:
        if not self.is_busy:
            return False
        try:
            return bool(self.is_busy())
        except Exception as exc:
            print(f"[ActionRouter] Error consultando estado de altavoz: {exc}")
            return False

    def _has_recent_user_voice(self) -> bool:
        if not self.has_recent_voice:
            return False
        try:
            return bool(self.has_recent_voice(self._delivery_recent_voice_seconds))
        except TypeError:
            return bool(self.has_recent_voice())
        except Exception as exc:
            print(f"[ActionRouter] Error consultando voz reciente: {exc}")
            return False

    def _enqueue_delivery(self, turn_id: str, text: str, kind: str, priority: int) -> PendingDelivery:
        self._delivery_sequence += 1
        delivery = PendingDelivery(
            priority=priority,
            sequence=self._delivery_sequence,
            turn_id=turn_id,
            text=text,
            kind=kind,
        )
        self._pending_deliveries.append(delivery)
        print(
            f"[ActionRouter] Resultado en cola para turno {turn_id}: "
            f"kind={kind}, priority={priority}, queue={len(self._pending_deliveries)}"
        )
        return delivery

    def _remove_delivery(self, delivery: PendingDelivery):
        self._pending_deliveries = [item for item in self._pending_deliveries if item is not delivery]

    def _next_delivery(self) -> PendingDelivery | None:
        if not self._pending_deliveries:
            return None
        return min(self._pending_deliveries, key=lambda item: (item.priority, item.sequence))

    async def _wait_for_delivery_slot(self, turn, delivery: PendingDelivery) -> bool:
        idle_since = None
        next_log_at = time.monotonic() + self._delivery_log_seconds

        while True:
            if turn.state in (TurnState.CANCEL_REQUESTED, TurnState.STALE):
                print(f"[ActionRouter] Entrega cancelada para turno {turn.turn_id}: estado={turn.state.value}")
                return False

            active = self.synapse.active_turn
            if active and active.turn_id != turn.turn_id:
                print(f"[ActionRouter] Entrega descartada: turno {turn.turn_id} ya no es activo.")
                return False

            output_busy = self._is_playback_busy()
            user_recent = self._has_recent_user_voice()
            has_session = self.get_session() is not None
            is_next = self._next_delivery() is delivery
            now = time.monotonic()
            waited = now - delivery.created_at
            max_wait_reached = (
                self._delivery_max_wait_seconds > 0
                and waited >= self._delivery_max_wait_seconds
            )
            force_after_wait = has_session and is_next and not output_busy and user_recent and max_wait_reached
            ready_now = has_session and is_next and not output_busy and not user_recent

            if force_after_wait:
                print(
                    f"[ActionRouter] Entrega forzada para turno {turn.turn_id} tras {waited:.1f}s: "
                    "voz_reciente seguia activa."
                )
                return True

            if ready_now:
                if idle_since is None:
                    idle_since = now
                if now - idle_since >= self._delivery_idle_seconds:
                    print(f"[ActionRouter] Entrega habilitada para turno {turn.turn_id} tras {waited:.1f}s.")
                    return True
            else:
                idle_since = None

            if now >= next_log_at:
                print(
                    f"[ActionRouter] Entrega esperando momento natural: "
                    f"turno={turn.turn_id}, playback_busy={output_busy}, "
                    f"voz_reciente={user_recent}, sesion={has_session}, prioridad_lista={is_next}"
                )
                next_log_at = now + self._delivery_log_seconds

            await asyncio.sleep(self._delivery_poll_seconds)

    def reserve_tool_call(self) -> bool:
        if not self.can_accept_tool_call():
            return False
        self._tool_call_reserved = True
        return True

    async def queue_hermes_tool_call(self, call_id: str, name: str, prompt: str) -> bool:
        """Registra una tarea Hermes pendiente sin iniciar otra ejecucion concurrente."""
        if not self.task_ledger:
            return False

        task_record = self.task_ledger.create_task(
            "hermes",
            prompt,
            tool_name=name,
            origin_call_id=call_id,
        )
        queue_position = len(self.task_ledger.pending_tasks("hermes"))
        print(
            f"[ActionRouter] Tarea Hermes en cola: task={task_record.task_id}, "
            f"posicion={queue_position}, prompt_chars={len(prompt)}"
        )
        if self.conversation_sessions:
            self.conversation_sessions.record_user(
                f"Tarea compleja en cola: {prompt}",
                kind="hermes_task_queued",
            )

        session = self.get_session()
        if session:
            await self._send_queued_tool_response(session, call_id, name, queue_position)

        self._schedule_next_queued_task()
        return True

    def _schedule_next_queued_task(self) -> None:
        if not self.task_ledger:
            return
        if self._queued_task_runner and not self._queued_task_runner.done():
            return
        if self._tool_call_reserved or self.has_active_work():
            return
        task_record = self.task_ledger.next_pending("hermes")
        if not task_record:
            return

        self._tool_call_reserved = True
        task_name = task_record.tool_name or "ejecutar_hermes_core"
        print(
            f"[ActionRouter] Despachando tarea Hermes en cola: task={task_record.task_id}, "
            f"prompt_chars={len(task_record.prompt)}"
        )
        self._queued_task_runner = asyncio.create_task(
            self.run_hermes(
                "",
                task_name,
                task_record.prompt,
                task_record=task_record,
                send_ack=False,
            )
        )

    def task_status_payload(self) -> dict:
        if not self.task_ledger:
            active = self.synapse.active_turn
            active_desc = active.state.value if active else "sin_registro"
            return {
                "status": active_desc,
                "active": bool(active and active.state in self._ACTIVE_STATES),
                "pending": 0,
                "message": "No tengo un registro local de tareas disponible ahora.",
            }

        running = self.task_ledger.running_tasks("hermes")
        pending = self.task_ledger.pending_tasks("hermes")
        recent = self.task_ledger.recent_tasks(5)
        last_done = next(
            (
                task for task in reversed(recent)
                if task.status.value in {"completed", "failed", "interrupted", "stale"}
            ),
            None,
        )

        if running:
            message = "Sigo trabajando en una tarea compleja."
            if pending:
                message += f" Tengo {len(pending)} tarea pendiente en cola."
            else:
                message += " No hay más tareas en cola."
            return {
                "status": "running",
                "active": True,
                "pending": len(pending),
                "active_task_id": running[-1].task_id,
                "message": message,
            }

        if pending:
            return {
                "status": "queued",
                "active": False,
                "pending": len(pending),
                "message": f"Tengo {len(pending)} tarea pendiente en cola. La ejecutaré cuando el sistema quede libre.",
            }

        if last_done:
            if last_done.status.value == "completed":
                message = "La última tarea compleja ya terminó."
            elif last_done.status.value == "failed":
                message = "La última tarea compleja falló."
            elif last_done.status.value == "interrupted":
                message = "La última tarea compleja fue interrumpida."
            else:
                message = "La última tarea compleja quedó descartada por quedar vieja."
            return {
                "status": last_done.status.value,
                "active": False,
                "pending": 0,
                "last_task_id": last_done.task_id,
                "message": message,
            }

        return {
            "status": "idle",
            "active": False,
            "pending": 0,
            "message": "No tengo tareas complejas activas ni pendientes.",
        }

    @staticmethod
    def _today_iso() -> str:
        return datetime.now().date().isoformat()

    @staticmethod
    def _read_agenda_items_for_today(today_iso: str) -> list[str]:
        agenda_file = os.getenv("JARVIS_AGENDA_FILE", "").strip()
        if not agenda_file:
            return []
        agenda_file = os.path.expanduser(agenda_file)
        if not os.path.exists(agenda_file):
            print(f"[ActionRouter] Agenda local no encontrada: {agenda_file}")
            return []

        try:
            with open(agenda_file, "r", encoding="utf-8") as handle:
                if agenda_file.lower().endswith(".json"):
                    data = json.load(handle)
                else:
                    return [
                        line.strip()
                        for line in handle
                        if line.strip() and today_iso in line
                    ][:10]
        except Exception as exc:
            print(f"[ActionRouter] Error leyendo agenda local: {exc}")
            return []

        if isinstance(data, dict):
            raw_items = data.get(today_iso, [])
            if isinstance(raw_items, str):
                raw_items = [raw_items]
            if isinstance(raw_items, list):
                return [str(item).strip() for item in raw_items if str(item).strip()][:10]
            return []

        if isinstance(data, list):
            items = []
            for item in data:
                if isinstance(item, dict):
                    item_date = str(item.get("date") or item.get("fecha") or "").strip()
                    if item_date != today_iso:
                        continue
                    text = item.get("title") or item.get("titulo") or item.get("text") or item.get("descripcion")
                    if text:
                        items.append(str(text).strip())
                elif isinstance(item, str) and today_iso in item:
                    items.append(item.strip())
            return items[:10]

        return []

    def today_summary_payload(self) -> dict:
        today_iso = self._today_iso()
        task_status = self.task_status_payload()
        agenda_items = self._read_agenda_items_for_today(today_iso)
        agenda_configured = bool(os.getenv("JARVIS_AGENDA_FILE", "").strip())

        parts = []
        
        try:
            from hermes_constants import get_hermes_home
            home = get_hermes_home()
            if home:
                memory_path = os.path.join(str(home), "memories", "MEMORY.md")
                if os.path.exists(memory_path):
                    with open(memory_path, "r", encoding="utf-8") as f:
                        mem_content = f.read().strip()
                        if mem_content:
                            parts.append(f"Resumen de mi memoria reciente operativa:\n{mem_content[-1500:]}")
        except Exception as e:
            print(f"[ActionRouter] Error leyendo MEMORY.md para el resumen: {e}")

        if task_status.get("active") or task_status.get("pending"):
            parts.append(str(task_status.get("message", "")).strip())
        else:
            parts.append("No tengo tareas complejas activas ni pendientes en este instante.")

        if agenda_items:
            parts.append("Agenda local de hoy: " + "; ".join(agenda_items[:3]))
        elif agenda_configured:
            parts.append("No encontre eventos locales para hoy en la agenda configurada.")

        return {
            "status": "ok",
            "date": today_iso,
            "task_status": task_status,
            "agenda_configured": agenda_configured,
            "agenda_items": agenda_items,
            "message": "\n\n".join(part for part in parts if part),
        }

    async def send_task_status_tool_call(self, call_id: str, name: str):
        payload = self.task_status_payload()
        session = self.get_session()
        print(
            f"[ActionRouter] Estado de tareas solicitado: "
            f"status={payload.get('status')}, pending={payload.get('pending')}"
        )
        if not session:
            return
        try:
            await session.send_tool_response(
                function_responses=[
                    types.FunctionResponse(
                        id=call_id,
                        name=name,
                        response=payload,
                    )
                ]
            )
        except Exception as exc:
            print(f"[ActionRouter] Error respondiendo estado de tareas: {exc}")

    async def send_today_summary_tool_call(self, call_id: str, name: str):
        payload = self.today_summary_payload()
        session = self.get_session()
        print(
            f"[ActionRouter] Resumen de hoy solicitado: "
            f"date={payload.get('date')}, agenda_items={len(payload.get('agenda_items', []))}"
        )
        if not session:
            return
        try:
            await session.send_tool_response(
                function_responses=[
                    types.FunctionResponse(
                        id=call_id,
                        name=name,
                        response=payload,
                    )
                ]
            )
        except Exception as exc:
            print(f"[ActionRouter] Error respondiendo resumen de hoy: {exc}")

    async def reject_busy_tool_call(self, call_id: str, name: str):
        """Cierra una tool call extra sin arrancar otra tarea Hermes."""
        active = self.synapse.active_turn
        active_desc = f"{active.turn_id} ({active.state.value})" if active else "ninguno"
        if active and self.has_unfinished_brain_task():
            active_desc += ", brain_task=running"
        print(f"[ActionRouter] Tool call rechazada porque hay un turno activo: {active_desc}")

        session = self.get_session()
        if session:
            await self._send_busy_tool_response(session, call_id, name)

    async def cancel_active_tool_call(self, call_id: str, name: str):
        """Cancela la tarea Hermes activa solo cuando el usuario lo pide explicitamente."""
        active = self.synapse.active_turn
        session = self.get_session()

        if not self.has_active_work():
            pending = self.task_ledger.next_pending("hermes") if self.task_ledger else None
            if pending and self.task_ledger:
                self.task_ledger.mark_interrupted(pending, "cancelada antes de ejecutarse")
                print(f"[ActionRouter] Tarea pendiente cancelada: task={pending.task_id}")
                if session:
                    await self._send_cancel_tool_response(
                        session,
                        call_id,
                        name,
                        "cancelada_pendiente",
                        "Cancelé la siguiente tarea compleja que estaba en cola.",
                    )
                self._schedule_next_queued_task()
                return

            print("[ActionRouter] Cancelacion solicitada, pero no hay tarea Hermes activa.")
            if session:
                await self._send_cancel_tool_response(
                    session,
                    call_id,
                    name,
                    "sin_tarea",
                    "No hay una tarea compleja activa para cancelar.",
                )
            return

        active_desc = f"{active.turn_id} ({active.state.value})" if active else "desconocido"
        print(f"[ActionRouter] Cancelacion explicita de turno activo: {active_desc}")
        if session:
            await self._send_cancel_tool_response(
                session,
                call_id,
                name,
                "cancelando",
                "Estoy cancelando la tarea compleja que estaba en curso.",
            )
        await self.interrupt_active_turn("Usuario pidio cancelar la tarea activa.")

    def _computing_sound(self):
        """Efecto de sonido JARVIS sin interrumpir la voz."""
        try:
            import winsound
            wav_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "voice", "assets", "jarvis_processing.wav")
            if os.path.exists(wav_path):
                winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception:
            pass

    @staticmethod
    def _normalize_intent(text: str) -> str:
        text = unicodedata.normalize("NFKD", text or "")
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = text.lower().replace(".", " ").replace(",", " ")
        return " ".join(text.split())

    @classmethod
    def _contains_any(cls, normalized_text: str, terms: tuple[str, ...]) -> bool:
        tokens = set(normalized_text.split())
        for term in terms:
            normalized_term = cls._normalize_intent(term)
            if " " in normalized_term:
                if normalized_term in normalized_text:
                    return True
            elif normalized_term in tokens:
                return True
        return False

    @classmethod
    def _is_music_or_youtube_request(cls, prompt: str) -> bool:
        normalized = cls._normalize_intent(prompt)
        if not normalized:
            return False
        if cls._contains_any(normalized, cls._MUSIC_NEGATIVE_TERMS):
            return False
        return cls._contains_any(normalized, cls._MUSIC_TERMS)

    @staticmethod
    def _cmd_quote(value: str) -> str:
        return '"' + value.replace('"', '\\"') + '"'

    def _local_youtube_instruction(self, prompt: str) -> str:
        if not self._is_music_or_youtube_request(prompt):
            return ""
        python_exe = self._cmd_quote(sys.executable)
        script_path = self._cmd_quote(_LOCAL_YOUTUBE_SCRIPT)
        return (
            "\n[CAPACIDAD LOCAL - MUSICA/YOUTUBE]\n"
            "La herramienta directa de YouTube de Live esta desactivada. "
            "Para cumplir tareas de reproducir musica, canciones, videos o YouTube, usa la herramienta terminal.\n"
            f"Ejecuta este formato, reemplazando <busqueda> por la cancion o video solicitado: {python_exe} {script_path} \"<busqueda>\"\n"
            "No uses memory, todo ni session_search para reproducir musica. No respondas solo texto si el usuario pidio reproducir. "
            "Despues de ejecutar el comando, responde breve: Listo, lo abri en YouTube.\n"
        )

    def _build_hermes_prompt(self, prompt: str) -> str:
        bot_name = os.getenv("ASSISTANT_NAME", "JARVIS")
        user_name = os.getenv("USER_NAME", "Señor")

        return (
            f"[IDENTIDAD CRÍTICA]\n"
            f"Eres el núcleo lógico e investigativo del asistente '{bot_name}'. "
            f"El usuario '{user_name}' te ha pedido algo mediante la interfaz de voz.\n\n"
            f"[CONTEXTO DEL SISTEMA - Windows 11]\n"
            "IMPORTANTE: Estás operando en Windows 11. Usa tus herramientas para cumplir la orden.\n"
            f"{self._local_youtube_instruction(prompt)}\n"
            f"TAREA DEL USUARIO: {prompt}\n\n"
            "[INSTRUCCIÓN INTERNA]: Resuelve la tarea. Devuelve SOLO los datos o el resultado final. "
            "NUNCA redactes un saludo."
        )

    async def interrupt_active_turn(self, reason: str = "Cancelacion explicita."):
        """Cancela cooperativamente Hermes; no se debe llamar por un barge-in de voz normal."""
        active = self.synapse.active_turn
        if not active:
            print(f"[ActionRouter] Interrupción ignorada: no hay turno activo ({reason}).")
            return

        if active.state not in self._ACTIVE_STATES:
            if self.has_unfinished_brain_task():
                print(
                    f"[ActionRouter] Interrupcion recibida con turno {active.turn_id} "
                    f"en {active.state.value}; brain_task sigue drenando: {reason}"
                )
                self.brain.interrupt(reason)
                return
            print(f"[ActionRouter] Interrupción ignorada: turno {active.turn_id} ya está en {active.state.value}.")
            return

        print(f"[ActionRouter] Interrumpiendo turno {active.turn_id} ({active.state.value}): {reason}")
        if active.state != TurnState.CANCEL_REQUESTED:
            self.synapse.change_state(TurnState.CANCEL_REQUESTED, turn_id=active.turn_id)
        self.brain.interrupt(reason)
        
        # Esperar a que la tarea termine cooperativamente
        if active.brain_task and not active.brain_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(active.brain_task), timeout=5.0)
            except asyncio.TimeoutError:
                print(f"[ActionRouter] Timeout esperando interrupción. Turno {active.turn_id} marcado como STALE.")
                self.synapse.change_state(TurnState.STALE, turn_id=active.turn_id)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f"[ActionRouter] Error durante interrupción de {active.turn_id}: {e}")
        elif active.state == TurnState.CANCEL_REQUESTED:
            self.synapse.change_state(TurnState.INTERRUPTED, turn_id=active.turn_id)

    async def run_hermes(
        self,
        call_id: str,
        name: str,
        prompt: str,
        task_record=None,
        send_ack: bool = True,
    ):
        """Orquesta un nuevo turno de pensamiento con el Cerebro."""
        turn = None
        try:
            # 1. No iniciar otra tarea compleja encima de una activa.
            if self.has_active_work():
                active = self.synapse.active_turn
                active_desc = f"{active.turn_id} ({active.state.value})" if active else "desconocido"
                print(
                    f"[ActionRouter] Nuevo request no iniciado; ya hay trabajo Hermes activo: {active_desc}"
                )
                session = self.get_session()
                if session:
                    await self._send_busy_tool_response(session, call_id, name)
                return

            # 2. Crear el nuevo turno
            turn = self.synapse.create_turn(prompt)
            if self.task_ledger and task_record is None:
                task_record = self.task_ledger.create_task(
                    "hermes",
                    prompt,
                    turn_id=turn.turn_id,
                    tool_name=name,
                    origin_call_id=call_id,
                )
            if self.conversation_sessions:
                self.conversation_sessions.record_user(
                    f"Tarea compleja solicitada: {prompt}",
                    kind="hermes_task_request",
                )
            self.synapse.change_state(TurnState.THINKING, turn_id=turn.turn_id)
            print(f"[ActionRouter] Turno Hermes aceptado: {turn.turn_id} (prompt_chars={len(prompt)})")

            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, self._computing_sound)

            # ── FASE 1: ACK inmediato ──────────────────────────────────────────
            self.synapse.change_state(TurnState.ACKNOWLEDGING, turn_id=turn.turn_id)
            session = self.get_session()
            if session and send_ack:
                try:
                    ack_msg = random.choice(self._ACKS)
                    turn.ack_message = ack_msg
                    await session.send_tool_response(
                        function_responses=[
                            types.FunctionResponse(
                                id=call_id,
                                name=name,
                                response={"status": "procesando", "mensaje": ack_msg}
                            )
                        ]
                    )
                except Exception as exc:
                    print(f"[ActionRouter] Error enviando ACK: {exc}")

            if turn.state in (TurnState.CANCEL_REQUESTED, TurnState.STALE):
                self.synapse.change_state(TurnState.INTERRUPTED, turn_id=turn.turn_id)
                return

            # ── FASE 2: Ejecutar Hermes en segundo plano ───────────────────────
            self.synapse.change_state(TurnState.BRAIN_RUNNING, turn_id=turn.turn_id)
            if self.task_ledger:
                self.task_ledger.mark_running(task_record, turn_id=turn.turn_id)
            print(f"[ActionRouter] Ejecutando Hermes en turno {turn.turn_id}.")

            prompt_enriquecido = self._build_hermes_prompt(prompt)

            def _event_listener(evt_type, *args, **kwargs):
                if self.synapse.active_turn and self.synapse.active_turn.turn_id == turn.turn_id:
                    self.synapse.publish("brain_event", turn.turn_id, evt_type, *args, **kwargs)

            # Envolvemos run_task en un Task explícito para poder hacerle shield en interrupt
            turn.brain_task = asyncio.create_task(self.brain.run_task(prompt_enriquecido, _event_listener))
            brain_res = await turn.brain_task
            turn.brain_result = brain_res
            print(
                f"[ActionRouter] Hermes termino turno {turn.turn_id}: "
                f"success={brain_res.success}, interrupted={brain_res.interrupted}, "
                f"text_chars={len(brain_res.text or '')}"
            )

            if self.synapse.active_turn and self.synapse.active_turn.turn_id != turn.turn_id:
                print(f"[ActionRouter] Resultado tardío descartado para turno {turn.turn_id}.")
                self.synapse.change_state(TurnState.STALE, turn_id=turn.turn_id)
                if self.task_ledger:
                    self.task_ledger.mark_stale(task_record, "resultado tardio descartado")
                return

            if brain_res.interrupted or turn.state in (TurnState.CANCEL_REQUESTED, TurnState.STALE):
                if turn.state != TurnState.STALE:
                    self.synapse.change_state(TurnState.INTERRUPTED, turn_id=turn.turn_id)
                    if self.task_ledger:
                        self.task_ledger.mark_interrupted(task_record, "interrumpida")
                elif self.task_ledger:
                    self.task_ledger.mark_stale(task_record, "turno stale")
                return

            if not brain_res.success:
                reason = brain_res.error or "sin resultado útil"
                print(f"[ActionRouter] Cerebro falló en turno {turn.turn_id}: {reason}")
                self.synapse.change_state(TurnState.FAILED, turn_id=turn.turn_id)
                if self.task_ledger:
                    self.task_ledger.mark_failed(task_record, reason)
                if self.conversation_sessions:
                    self.conversation_sessions.record_system(
                        f"Tarea Hermes fallida: {reason}",
                        kind="hermes_task_failed",
                    )
                await self._inject_brain_failure(turn, reason)
                return

            # ── FASE 3: Inyectar resultado ─────────────────────────────────────
            self.synapse.change_state(TurnState.INJECTING_RESULT, turn_id=turn.turn_id)

            try:
                res_str = brain_res.text or ""
                if len(res_str) > 800:
                    res_str = res_str[:800] + "... [truncado]"

                result_text = (
                    f"[Resultado pendiente de tarea interna]: {res_str}. "
                    "Preséntalo de forma natural y breve. "
                    "Si el usuario estaba en otro tema, usa una transición suave como 'por cierto' o "
                    "'retomando lo anterior'. NUNCA menciones a 'Hermes'."
                )

                delivered = await self._queue_and_deliver_text(
                    turn=turn,
                    text=result_text,
                    kind="hermes_result",
                    priority=50,
                )
                if delivered:
                    self.synapse.change_state(TurnState.COMPLETED, turn_id=turn.turn_id)
                    if self.task_ledger:
                        self.task_ledger.mark_completed(task_record, res_str)
                    if self.conversation_sessions:
                        self.conversation_sessions.record_system(
                            f"Tarea Hermes completada: {res_str}",
                            kind="hermes_task_completed",
                        )

            except Exception as exc:
                print(f"[ActionRouter] Error inyectando resultado: {exc}")
                self.synapse.change_state(TurnState.FAILED, turn_id=turn.turn_id)
                if self.task_ledger:
                    self.task_ledger.mark_failed(task_record, str(exc))

        except asyncio.CancelledError:
            if turn:
                print(f"[ActionRouter] Tarea {turn.turn_id} cancelada localmente.")
                self.synapse.change_state(TurnState.INTERRUPTED, turn_id=turn.turn_id)
                if self.task_ledger:
                    self.task_ledger.mark_interrupted(task_record, "cancelada localmente")
            raise
        except Exception as exc:
            import traceback
            print(f"[ActionRouter] Fallo crítico en run_hermes: {exc}")
            traceback.print_exc()
            if turn:
                self.synapse.change_state(TurnState.FAILED, turn_id=turn.turn_id)
                if self.task_ledger:
                    self.task_ledger.mark_failed(task_record, str(exc))
        finally:
            current_task = asyncio.current_task()
            if self._queued_task_runner is current_task:
                self._queued_task_runner = None
            self._tool_call_reserved = False
            self._schedule_next_queued_task()

    async def _send_client_text(self, session, text: str):
        await session.send_client_content(
            turns=[
                types.Content(
                    role="user",
                    parts=[types.Part(text=text)],
                )
            ],
            turn_complete=True,
        )

    async def _queue_and_deliver_text(self, turn, text: str, kind: str, priority: int) -> bool:
        delivery = self._enqueue_delivery(turn.turn_id, text, kind=kind, priority=priority)
        wake_request = None
        if self.activation_gate:
            wake_request = self.activation_gate.request_wake(
                source="hermes",
                reason=kind,
                priority=priority,
                turn_id=turn.turn_id,
            )
        try:
            if not await self._wait_for_delivery_slot(turn, delivery):
                return False

            if self.synapse.active_turn and self.synapse.active_turn.turn_id != turn.turn_id:
                print(f"[ActionRouter] Turno {turn.turn_id} es viejo. Abortando entrega.")
                return False

            current_session = self.get_session()
            if not current_session:
                print(f"[ActionRouter] Entrega pospuesta sin sesión activa: turno={turn.turn_id}")
                return False

            if self.activation_gate:
                self.activation_gate.begin_delivery(wake_request)
            await self._send_client_text(current_session, delivery.text)
            print(f"[ActionRouter] Entrega enviada: turno={turn.turn_id}, kind={kind}")
            return True
        finally:
            self._remove_delivery(delivery)

    async def _send_busy_tool_response(self, session, call_id: str, name: str):
        try:
            await session.send_tool_response(
                function_responses=[
                    types.FunctionResponse(
                        id=call_id,
                        name=name,
                        response={
                            "status": "ocupado",
                            "mensaje": (
                                "Sigo trabajando en la tarea compleja anterior. "
                                "Puedo atender cosas simples mientras tanto; "
                                "si quieres detener la tarea de fondo, dime que la cancele."
                            ),
                        },
                    )
                ]
            )
        except Exception as exc:
            print(f"[ActionRouter] Error respondiendo tool call ocupada: {exc}")

    async def _send_queued_tool_response(self, session, call_id: str, name: str, queue_position: int):
        try:
            await session.send_tool_response(
                function_responses=[
                    types.FunctionResponse(
                        id=call_id,
                        name=name,
                        response={
                            "status": "en_cola",
                            "posicion": queue_position,
                            "mensaje": (
                                "Lo dejo en cola y lo hago cuando termine la tarea compleja actual. "
                                "Puedes seguir hablando mientras tanto."
                            ),
                        },
                    )
                ]
            )
        except Exception as exc:
            print(f"[ActionRouter] Error respondiendo tool call en cola: {exc}")

    async def _send_cancel_tool_response(self, session, call_id: str, name: str, status: str, message: str):
        try:
            await session.send_tool_response(
                function_responses=[
                    types.FunctionResponse(
                        id=call_id,
                        name=name,
                        response={"status": status, "mensaje": message},
                    )
                ]
            )
        except Exception as exc:
            print(f"[ActionRouter] Error respondiendo cancelacion de tarea: {exc}")

    async def _inject_brain_failure(self, turn, reason: str):
        if self.synapse.active_turn and self.synapse.active_turn.turn_id != turn.turn_id:
            print(f"[ActionRouter] Fallo tardío descartado para turno {turn.turn_id}: {reason}")
            return

        failure_text = (
            f"[Fallo de tarea interna]: No pude completar esa tarea ahora. Motivo técnico breve: {reason}. "
            "Díselo al usuario de forma natural y breve, sin mencionar Hermes."
        )
        try:
            await self._queue_and_deliver_text(turn, failure_text, kind="hermes_failure", priority=10)
        except Exception as exc:
            print(f"[ActionRouter] Error inyectando fallo de cerebro: {exc}")
