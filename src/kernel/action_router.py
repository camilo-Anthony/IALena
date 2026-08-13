import os
import sys
import time
import json
import random
import asyncio
import re
import unicodedata
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, List

from google.genai import types

try:
    import winsound as _winsound
except ImportError:
    _winsound = None

from src.core.interfaces.brain import IAgentBrain, BrainResult
from src.kernel.synapse import Synapse, TurnState
from src.kernel.task_lane import TaskLane, RiskLevel, LaneDecision, classify_tool_call
from src.kernel.delivery_queue import DeliveryQueue, DeliveryItem
from src.kernel.capability_registry import capability_registry, TaskCapability

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_LOCAL_YOUTUBE_SCRIPT = os.path.join(_PROJECT_ROOT, "src", "adapters", "llm", "play_yt.py")


@dataclass
class PendingConfirmation:
    call_id: str
    tool_name: str
    prompt: str
    challenge_phrase: str
    created_at: float = field(default_factory=time.time)


class ActionRouter:
    """Enruta peticiones complejas de la voz hacia el cerebro asíncrono, orquestando el Synapse y carriles."""
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
        brain_fast: IAgentBrain | None = None,
        delivery_queue: DeliveryQueue | None = None,
    ):
        self.brain = brain_adapter
        self.brain_fast = brain_fast
        self.synapse = synapse
        self.get_session = get_session_callback
        self.is_busy = is_busy_callback
        self.has_recent_voice = has_recent_voice_callback
        self.activation_gate = activation_gate
        self.task_ledger = task_ledger
        self.conversation_sessions = conversation_sessions
        self._tool_call_reserved = False
        self._queued_task_runner = None
        self.pending_confirmation = None

        self._fast_max_parallel = int(os.getenv("FAST_BRAIN_MAX_PARALLEL", "3"))
        self._fast_tasks_running = 0

        self._delivery_idle_seconds = self._read_float_env("RESULT_DELIVERY_IDLE_SECONDS", 1.0)
        self._delivery_poll_seconds = self._read_float_env("RESULT_DELIVERY_POLL_SECONDS", 0.2)
        self._delivery_recent_voice_seconds = self._read_float_env("RESULT_DELIVERY_RECENT_VOICE_SECONDS", 1.5)
        self._delivery_max_wait_seconds = self._read_float_env("RESULT_DELIVERY_MAX_WAIT_SECONDS", 12.0)
        self._delivery_log_seconds = self._read_float_env("RESULT_DELIVERY_LOG_SECONDS", 5.0)

        self.delivery_queue = delivery_queue or DeliveryQueue(
            is_playback_busy_fn=lambda: self.is_busy() if self.is_busy else False,
            has_recent_voice_fn=lambda win=None: (
                self.has_recent_voice(win) if self.has_recent_voice else False
            ),
            get_session_fn=lambda: self.get_session() if self.get_session else None,
            idle_wait_seconds=lambda: self._delivery_idle_seconds,
            poll_seconds=lambda: self._delivery_poll_seconds,
            max_wait_seconds=lambda: self._delivery_max_wait_seconds,
            recent_voice_window=lambda: self._delivery_recent_voice_seconds,
            log_interval_seconds=lambda: self._delivery_log_seconds,
        )

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

    def can_accept_lane(self, lane: TaskLane) -> bool:
        if lane == TaskLane.LOCAL:
            return True
        if lane == TaskLane.FAST_HERMES:
            if self.brain_fast and self.brain_fast.is_available():
                return self._fast_tasks_running < self._fast_max_parallel
            return self.can_accept_tool_call()
        return self.can_accept_tool_call()

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

    async def run_fast_hermes(self, call_id: str, tool_name: str, prompt: str) -> None:
        """
        Ejecuta una tarea de carril rápido de forma asíncrona.
        """
        has_fast_brain = bool(self.brain_fast and self.brain_fast.is_available())

        if not has_fast_brain:
            # Re-evaluar si la tarea amerita SLOW
            decision = classify_tool_call(tool_name, {"prompt": prompt})
            if decision.lane == TaskLane.SLOW_HERMES:
                print(f"[ActionRouter] FAST no tiene brain_fast. La tarea amerita SLOW. Encolando explícitamente.")
                await self.queue_hermes_tool_call(call_id, tool_name, prompt)
                return

            print(f"[ActionRouter] FAST rechazado: consulta rápida no disponible (sin brain_fast).")
            session = self.get_session()
            if session:
                try:
                    await session.send_tool_response(
                        function_responses=[types.FunctionResponse(
                            id=call_id,
                            name=tool_name,
                            response={
                                "status": "no_disponible",
                                "mensaje": "La consulta rápida no está disponible en este momento."
                            },
                        )]
                    )
                except Exception:
                    pass
            return

        brain = self.brain_fast
        lane_tag = "\033[96m[FAST]\033[0m"

        if brain is self.brain_fast:
            if self._fast_tasks_running >= self._fast_max_parallel:
                print(f"\033[36m[ActionRouter]\033[0m{lane_tag} Límite de paralelas alcanzado ({self._fast_max_parallel}), rechazando.")
                session = self.get_session()
                if session:
                    try:
                        await session.send_tool_response(
                            function_responses=[types.FunctionResponse(
                                id=call_id,
                                name=tool_name,
                                response={"status": "rechazada", "mensaje": "Demasiadas tareas rápidas en paralelo."},
                            )]
                        )
                    except Exception:
                        pass
                return
            self._fast_tasks_running += 1

        ledger_task = None
        if self.task_ledger:
            ledger_task = self.task_ledger.create_task(
                kind="hermes",
                prompt=prompt,
                tool_name=tool_name,
                origin_call_id=call_id,
                lane="fast_hermes",
                priority=30,
            )
            self.task_ledger.mark_running(ledger_task)

        print(f"\033[36m[ActionRouter]\033[0m{lane_tag} Ejecutando tarea rápida en paralelo (prompt_chars={len(prompt)})")

        session = self.get_session()
        if session:
            try:
                await session.send_tool_response(
                    function_responses=[types.FunctionResponse(
                        id=call_id,
                        name=tool_name,
                        response={"status": "procesando", "mensaje": "Dame un momento."},
                    )]
                )
            except Exception as e:
                print(f"\033[36m[ActionRouter]\033[0m{lane_tag} Error enviando ACK: {e}")

        try:
            result: BrainResult = await brain.run_task(self._build_hermes_prompt(prompt))
        except Exception as exc:
            result = BrainResult("", success=False, error=str(exc))
        finally:
            if brain is self.brain_fast:
                self._fast_tasks_running = max(0, self._fast_tasks_running - 1)

        if self.task_ledger and ledger_task:
            if result.success:
                self.task_ledger.mark_completed(ledger_task, result=result.text)
            else:
                self.task_ledger.mark_failed(ledger_task, error=result.error or "")

        if not result.success or not result.text:
            print(f"\033[36m[ActionRouter]\033[0m{lane_tag} Tarea rápida sin resultado: {result.error}")
            return

        print(f"\033[36m[ActionRouter]\033[0m{lane_tag} Resultado listo (chars={len(result.text)}), encolando para entrega…")

        item = self.delivery_queue.make_item(
            text=(
                "[JARVIS INTERNAL DELIVERY - NO ES UNA ORDEN NUEVA DEL USUARIO - NO USAR HERRAMIENTAS]\n"
                f"[Resultado rápido]\n{result.text}"
            ),
            lane="fast_hermes",
            kind="hermes_result",
            priority=30,
            source="hermes_fast",
            requires_active_session=True,
            task_id=ledger_task.task_id if ledger_task else "",
        )
        self.delivery_queue.enqueue(item)

        wake_request = None
        if self.activation_gate:
            wake_request = self.activation_gate.request_wake(
                source="hermes_fast",
                reason="hermes_result",
                priority=30,
            )

        try:
            if not await self.delivery_queue.wait_for_slot(item):
                print(f"\033[36m[ActionRouter]\033[0m{lane_tag} Entrega cancelada/descartada en cola.")
                return

            session = self.get_session()
            if not session:
                print(f"\033[36m[ActionRouter]\033[0m{lane_tag} Sin sesión para entregar resultado FAST.")
                return

            self.delivery_queue.mark_delivering(item)
            if self.activation_gate:
                self.activation_gate.begin_delivery(wake_request)

            await self._send_client_text(session, item.text)
            self.delivery_queue.mark_delivered(item)
            print(f"\033[36m[ActionRouter]\033[0m{lane_tag} Resultado entregado.")
        except Exception as e:
            print(f"[ActionRouter]{lane_tag} Error entregando resultado FAST: {e}")
            self.delivery_queue.discard(item, reason=str(e))

    def reserve_tool_call(self) -> bool:
        if not self.can_accept_tool_call():
            return False
        self._tool_call_reserved = True
        return True

    async def queue_hermes_tool_call(self, call_id: str, name: str, prompt: str) -> bool:
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

        try:
            loop = asyncio.get_running_loop()
            if not loop.is_running():
                return
        except RuntimeError:
            return

        self._tool_call_reserved = True
        task_name = task_record.tool_name or "ejecutar_hermes_core"
        print(
            f"[ActionRouter] Despachando tarea Hermes en cola: task={task_record.task_id}, "
            f"prompt_chars={len(task_record.prompt)}"
        )
        self._queued_task_runner = loop.create_task(
            self.run_hermes(
                "",
                task_name,
                task_record.prompt,
                task_record=task_record,
                send_ack=False,
            )
        )

    def task_status_payload(self) -> dict:
        if self.pending_confirmation:
            return {
                "status": "pending_confirmation",
                "active": True,
                "pending": 0,
                "running_slow_count": 0,
                "pending_slow_count": 0,
                "running_fast_count": 0,
                "message": f"Esperando confirmación verbal para: {self.pending_confirmation.prompt}. Por favor repite: {self.pending_confirmation.challenge_phrase}"
            }

        if not self.task_ledger:
            return {"status": "idle", "active": False, "pending": 0, "message": "No hay registro de tareas disponible."}

        running_slow = self.task_ledger.running_tasks(lane="slow_hermes")
        pending_slow = self.task_ledger.pending_tasks(lane="slow_hermes")
        running_fast = self.task_ledger.running_tasks(lane="fast_hermes")

        active = bool(running_slow or running_fast)
        status = "idle"
        if running_slow or running_fast:
            status = "running"
        elif pending_slow:
            status = "queued"

        message = ""
        if running_slow:
            message = "Sigo trabajando en una tarea compleja."
            if pending_slow:
                message += f" Tengo {len(pending_slow)} tarea(s) en cola."
            if running_fast:
                message += " Y tengo una consulta rápida activa en este momento."
        elif running_fast:
            message = "Tengo una consulta rápida activa en este momento."
        else:
            if pending_slow:
                message = f"Tengo {len(pending_slow)} tarea(s) en cola."
            else:
                message = "Todos los carriles están disponibles. No hay tareas en ejecución."

        payload = {
            "status": status,
            "active": bool(running_slow or running_fast),
            "pending": len(pending_slow),
            "running_slow_count": len(running_slow),
            "pending_slow_count": len(pending_slow),
            "running_fast_count": len(running_fast),
            "message": message,
            "capabilities": capability_registry.snapshot_payload(),
        }
        if running_slow:
            payload["active_task_id"] = running_slow[-1].task_id
        return payload

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
        except Exception:
            pass

        return {
            "status": "ok",
            "date": today_iso,
            "agenda_configured": agenda_configured,
            "agenda_items": agenda_items,
            "task_status": task_status,
            "memory_summary": "\n".join(parts) if parts else "No hay memoria operativa de Hermes disponible en este momento."
        }

    async def send_today_summary_tool_call(self, call_id: str, name: str):
        session = self.get_session()
        if not session:
            return
        payload = self.today_summary_payload()
        print(f"[ActionRouter] Resumen de hoy solicitado: date={payload['date']}, agenda_items={len(payload['agenda_items'])}")
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
            print(f"[ActionRouter] Error respondiendo tool call de resumen de hoy: {exc}")

    async def send_task_status_tool_call(self, call_id: str, name: str):
        session = self.get_session()
        if not session:
            return
        payload = self.task_status_payload()
        print(f"[ActionRouter] Estado de tareas solicitado: status={payload['status']}, pending={payload['pending']}")
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
            print(f"[ActionRouter] Error respondiendo tool call de estado de tareas: {exc}")

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

    async def cancel_active_tool_call(self, call_id: str, name: str):
        """Cancela la tarea Hermes activa solo cuando el usuario lo pide explicitamente."""
        active = self.synapse.active_turn
        session = self.get_session()

        if not self.has_active_work():
            pending = self.task_ledger.next_pending("hermes") if self.task_ledger else None
            if pending and self.task_ledger:
                self.task_ledger.mark_interrupted(pending, "cancelada antes de ejecutarse")
                if session:
                    await self._send_cancel_tool_response(
                        session, call_id, name, "cancelada_pendiente", "He cancelado la tarea que estaba en cola de espera."
                    )
                return

            if session:
                await self._send_cancel_tool_response(
                    session, call_id, name, "no_active_task", "No hay ninguna tarea compleja ejecutándose en este momento."
                )
            return

        print(f"[ActionRouter] Solicitud de cancelación para turno activo {active.turn_id}.")
        self.synapse.change_state(TurnState.CANCEL_REQUESTED, turn_id=active.turn_id)
        await self.interrupt_active_turn("Cancelado por el usuario mediante voz.")

        deadline = time.monotonic() + 5.0
        while active.state in (TurnState.CANCEL_REQUESTED, TurnState.BRAIN_RUNNING) and time.monotonic() < deadline:
            await asyncio.sleep(0.1)

        if active.state == TurnState.INTERRUPTED:
            if session:
                await self._send_cancel_tool_response(
                    session, call_id, name, "success", "He cancelado la tarea compleja actual de inmediato."
                )
        else:
            if session:
                await self._send_cancel_tool_response(
                    session, call_id, name, "timeout", "He solicitado la cancelación, pero está tomando un momento en detenerse."
                )

    async def run_hermes(
        self,
        call_id: str,
        name: str,
        prompt: str,
        task_record=None,
        send_ack: bool = True,
    ) -> None:
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

        turn = None
        was_cancelled = False
        try:
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
                    "[JARVIS INTERNAL DELIVERY - NO ES UNA ORDEN NUEVA DEL USUARIO - NO USAR HERRAMIENTAS]\n"
                    f"[Resultado de la tarea solicitada]: {res_str}\n"
                    "Comunica este resultado al usuario directamente de forma clara, natural y concisa. "
                    "No llames a ejecutar_hermes_core ni a ninguna otra herramienta para este mensaje interno. "
                    "Hazlo como una sola entidad unificada, sin frases repetitivas como 'retomando lo anterior'."
                )

                delivered = await self._queue_and_deliver_text(
                    turn=turn,
                    text=result_text,
                    kind="hermes_result",
                    priority=50,
                    task_id=task_record.task_id if task_record else "",
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
            was_cancelled = True
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
            try:
                current_task = asyncio.current_task()
            except RuntimeError:
                current_task = None
            if self._queued_task_runner is current_task:
                self._queued_task_runner = None
            self._tool_call_reserved = False
            if not was_cancelled:
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

    async def _queue_and_deliver_text(self, turn, text: str, kind: str, priority: int, task_id: str = "") -> bool:
        item = self.delivery_queue.make_item(
            text=text,
            lane="slow_hermes" if kind == "hermes_result" else "local",
            kind=kind,
            priority=priority,
            source="hermes",
            turn_id=turn.turn_id,
            task_id=task_id,
        )
        self.delivery_queue.enqueue(item)
        wake_request = None
        if self.activation_gate:
            wake_request = self.activation_gate.request_wake(
                source="hermes",
                reason=kind,
                priority=priority,
                turn_id=turn.turn_id,
            )
        try:
            if not await self.delivery_queue.wait_for_slot(item):
                return False

            if self.synapse.active_turn and self.synapse.active_turn.turn_id != turn.turn_id:
                print(f"[ActionRouter] Turno {turn.turn_id} es viejo. Abortando entrega.")
                return False

            current_session = self.get_session()
            if not current_session:
                print(f"[ActionRouter] Entrega pospuesta sin sesión activa: turno={turn.turn_id}")
                return False

            self.delivery_queue.mark_delivering(item)
            if self.activation_gate:
                self.activation_gate.begin_delivery(wake_request)

            await self._send_client_text(current_session, item.text)
            self.delivery_queue.mark_delivered(item)
            print(f"[ActionRouter] Entrega enviada: turno={turn.turn_id}, kind={kind}")
            return True
        finally:
            # Eliminar si sigue presente por descarte asíncrono
            if item in self.delivery_queue._items:
                self.delivery_queue._items.remove(item)

    async def _inject_brain_failure(self, turn, reason: str):
        if self.synapse.active_turn and self.synapse.active_turn.turn_id != turn.turn_id:
            print(f"[ActionRouter] Fallo tardío descartado para turno {turn.turn_id}: {reason}")
            return

        failure_text = (
            "[JARVIS INTERNAL DELIVERY - NO ES UNA ORDEN NUEVA DEL USUARIO - NO USAR HERRAMIENTAS]\n"
            f"[Fallo de tarea interna]: No pude completar esa tarea ahora. Motivo técnico breve: {reason}. "
            "Díselo al usuario de forma natural y breve, sin mencionar Hermes. "
            "No llames a ejecutar_hermes_core ni a ninguna otra herramienta para este mensaje interno."
        )
        try:
            await self._queue_and_deliver_text(turn, failure_text, kind="hermes_failure", priority=10)
        except Exception as exc:
            print(f"[ActionRouter] Error inyectando fallo de cerebro: {exc}")

    def _computing_sound(self):
        if _winsound:
            try:
                _winsound.Beep(2000, 80)
            except Exception:
                pass

    @classmethod
    def _normalize_intent(cls, text: str) -> str:
        text = unicodedata.normalize("NFKD", text or "")
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = re.sub(r"[^a-zA-Z0-9\s']", " ", text.lower())
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def _contains_any(cls, normalized_text: str, terms: tuple) -> bool:
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

        res = (
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

        if self.conversation_sessions:
            ctx = self.conversation_sessions.active_context_text()
            if ctx:
                res = (
                    "[TRANSCRIPCION_VOZ_RECIENTE_ESTA_SESION]\n"
                    f"{ctx}\n"
                    "-------------------------------------------\n"
                    f"{res}"
                )
        return res

    async def submit_tool_call(
        self,
        tool_name: str,
        args: dict,
        session,
        call_id: str,
        transcript_context: str | None = None,
    ) -> None:
        """
        Punto de entrada unificado para todas las tool calls.
        Clasifica, valida seguridad/capacidades y despacha la tarea.
        """
        prompt = args.get("prompt", "")
        prompt_chars = len(prompt)

        # 1. Interceptar si hay una confirmación verbal pendiente
        if self.pending_confirmation:
            user_response = self._normalize_intent(prompt)
            challenge = self._normalize_intent(self.pending_confirmation.challenge_phrase)

            orig_conf = self.pending_confirmation
            self.pending_confirmation = None  # Consumir confirmación de inmediato

            # Afirmaciones comunes simples no son suficientes
            if user_response in ("si", "ok", "dale", "proceder", "adelante", "okey", "vale", "listo", "yes", "go"):
                print(f"[LaneRouter] Afirmacion simple no es suficiente para confirmar call={orig_conf.call_id}")
                if session:
                    try:
                        await session.send_tool_response(
                            function_responses=[types.FunctionResponse(
                                id=call_id,
                                name=tool_name,
                                response={
                                    "status": "rechazada",
                                    "mensaje": f"Confirmación insuficiente. Para proceder con esta acción de alto riesgo, debes repetir exactamente la frase: '{orig_conf.challenge_phrase}'."
                                },
                            )]
                        )
                    except Exception:
                        pass
                return

            if challenge in user_response:
                # Confirmación exitosa! Procedemos a ejecutar la tarea original.
                print(f"[LaneRouter] Confirmacion exitosa para call={orig_conf.call_id} challenge='{orig_conf.challenge_phrase}'")

                # Enviar respuesta de confirmación procesada a la tool call actual
                if session:
                    try:
                        await session.send_tool_response(
                            function_responses=[types.FunctionResponse(
                                id=call_id,
                                name=tool_name,
                                response={
                                    "status": "confirmada",
                                    "mensaje": "Confirmación recibida. Procediendo con la tarea."
                                },
                            )]
                        )
                    except Exception:
                        pass

                # Ejecutar la tarea original
                orig_decision = classify_tool_call(orig_conf.tool_name, {"prompt": orig_conf.prompt})
                if orig_decision.lane == TaskLane.FAST_HERMES:
                    asyncio.create_task(self.run_fast_hermes(orig_conf.call_id, orig_conf.tool_name, orig_conf.prompt))
                else:
                    if not self.can_accept_lane(TaskLane.SLOW_HERMES) or not self.reserve_tool_call():
                        await self.queue_hermes_tool_call(orig_conf.call_id, orig_conf.tool_name, orig_conf.prompt)
                    else:
                        asyncio.create_task(self.run_hermes(orig_conf.call_id, orig_conf.tool_name, orig_conf.prompt, send_ack=False))
                return
            elif any(term in user_response for term in ("cancela", "cancelar", "no", "abortar")):
                print(f"[LaneRouter] Confirmacion cancelada por el usuario para call={orig_conf.call_id}")
                if session:
                    try:
                        await session.send_tool_response(
                            function_responses=[types.FunctionResponse(
                                id=call_id,
                                name=tool_name,
                                response={
                                    "status": "cancelada",
                                    "mensaje": "Operación de riesgo cancelada por el usuario."
                                },
                            )]
                        )
                    except Exception:
                        pass
                return
            else:
                print(f"[LaneRouter] Confirmacion incorrecta para call={orig_conf.call_id}. Recibido: '{prompt}'")
                if session:
                    try:
                        await session.send_tool_response(
                            function_responses=[types.FunctionResponse(
                                id=call_id,
                                name=tool_name,
                                response={
                                    "status": "rechazada",
                                    "mensaje": f"Confirmación incorrecta. Esperaba exactamente '{orig_conf.challenge_phrase}'. Tarea cancelada por seguridad."
                                },
                            )]
                        )
                    except Exception:
                        pass
                return

        decision: LaneDecision = classify_tool_call(tool_name, args)
        lane = decision.lane

        lane_str = "local"
        if lane == TaskLane.FAST_HERMES:
            lane_str = "fast_hermes"
        elif lane == TaskLane.SLOW_HERMES:
            lane_str = "slow_hermes"

        reason_str = "local_tool_execution"
        if lane == TaskLane.FAST_HERMES:
            reason_str = "fast_brain_execution"
        elif lane == TaskLane.SLOW_HERMES:
            reason_str = "slow_brain_execution"

        print(f"[LaneRouter] call={call_id} tool={tool_name} lane={lane_str} reason={reason_str} prompt_chars={prompt_chars}")

        # 2. Validación de capacidades para carriles de Hermes
        if lane != TaskLane.LOCAL:
            missing_caps = []
            registry_lane = "slow" if lane == TaskLane.SLOW_HERMES else "fast"
            for cap in decision.required_capabilities:
                if not capability_registry.has_capability(registry_lane, cap):
                    missing_caps.append(cap.value)
            if missing_caps:
                missing_str = "/".join(missing_caps)
                print(f"[LaneRouter] reject call={call_id} lane={lane_str} reason=missing_capabilities_{missing_str}")
                if session:
                    try:
                        await session.send_tool_response(
                            function_responses=[types.FunctionResponse(
                                id=call_id,
                                name=tool_name,
                                response={
                                    "status": "error",
                                    "mensaje": f"No tengo activo el acceso de {missing_str} para crear eso."
                                },
                            )]
                        )
                    except Exception:
                        pass
                return

            # 3. Flujo de Riesgo Medio Ambiguo (Fase C.2)
            if decision.risk == RiskLevel.MEDIUM and decision.is_ambiguous:
                print(f"[LaneRouter] reject call={call_id} lane={lane_str} reason=medium_risk_ambiguous")
                if session:
                    try:
                        await session.send_tool_response(
                            function_responses=[types.FunctionResponse(
                                id=call_id,
                                name=tool_name,
                                response={
                                    "status": "aclaracion_requerida",
                                    "mensaje": "Por favor, sé más específico sobre qué archivo o cambio deseas realizar."
                                },
                            )]
                        )
                    except Exception:
                        pass
                return

            # 4. Flujo de Alto Riesgo con Desafío Verbal (Fase C.3)
            if decision.risk == RiskLevel.HIGH:
                # Generar una frase de desafío simple y relevante
                normalized = self._normalize_intent(prompt)
                verbo = "proceder"
                if "borra" in normalized or "elimina" in normalized or "destruye" in normalized:
                    verbo = "confirmar eliminacion"
                elif "sobrescribe" in normalized or "modifica" in normalized or "edita" in normalized:
                    verbo = "autorizar cambio"
                else:
                    verbo = "confirmar accion peligrosa"

                challenge_phrase = verbo
                self.pending_confirmation = PendingConfirmation(
                    call_id=call_id,
                    tool_name=tool_name,
                    prompt=prompt,
                    challenge_phrase=challenge_phrase
                )
                print(f"[LaneRouter] Pending confirmation for call={call_id} lane={lane_str} risk=HIGH challenge='{challenge_phrase}'")

                if session:
                    try:
                        await session.send_tool_response(
                            function_responses=[types.FunctionResponse(
                                id=call_id,
                                name=tool_name,
                                response={
                                    "status": "confirmacion_pendiente",
                                    "challenge_phrase": challenge_phrase,
                                    "mensaje": f"Esta acción es de alto riesgo. Para proceder, por favor repite exactamente la frase: {challenge_phrase}"
                                },
                            )]
                        )
                    except Exception:
                        pass
                return

        if lane == TaskLane.LOCAL:
            print(f"[LaneRouter] accept call={call_id} lane={lane_str}")
            await self.run_local_tool(tool_name, args, session, call_id)
        elif lane == TaskLane.FAST_HERMES:
            if not self.can_accept_lane(TaskLane.FAST_HERMES):
                print(f"[LaneRouter] reject call={call_id} lane={lane_str} reason=fast_lane_busy_or_saturated")
                if session:
                    try:
                        await session.send_tool_response(
                            function_responses=[types.FunctionResponse(
                                id=call_id,
                                name=tool_name,
                                response={
                                    "status": "ocupado",
                                    "mensaje": "El sistema está ocupado procesando otra tarea en este momento."
                                },
                            )]
                        )
                    except Exception as e:
                        print(f"\033[36m[ActionRouter]\033[0m Error respondiendo ocupado para FAST: {e}")
                return

            print(f"[LaneRouter] accept call={call_id} lane={lane_str}")
            asyncio.create_task(self.run_fast_hermes(call_id, tool_name, prompt))
        else: # SLOW_HERMES
            if not self.can_accept_lane(TaskLane.SLOW_HERMES):
                print(f"[LaneRouter] reject call={call_id} lane={lane_str} reason=slow_lane_busy_queued")
                await self.queue_hermes_tool_call(call_id, tool_name, prompt)
            else:
                if not self.reserve_tool_call():
                    print(f"[LaneRouter] reject call={call_id} lane={lane_str} reason=slow_lane_busy_queued")
                    await self.queue_hermes_tool_call(call_id, tool_name, prompt)
                else:
                    print(f"[LaneRouter] accept call={call_id} lane={lane_str}")
                    asyncio.create_task(self.run_hermes(call_id, tool_name, prompt, send_ack=True))

    async def run_local_tool(
        self,
        tool_name: str,
        args: dict,
        session,
        call_id: str,
    ) -> None:
        """Ejecuta una herramienta local de forma inmediata."""
        if tool_name == "cancelar_tarea_hermes":
            await self.cancel_active_tool_call(call_id, tool_name)
        elif tool_name == "consultar_estado_tareas":
            await self.send_task_status_tool_call(call_id, tool_name)
        elif tool_name == "consultar_resumen_hoy":
            await self.send_today_summary_tool_call(call_id, tool_name)
        elif tool_name == "reproducir_musica_youtube":
            cancion = args.get("cancion", "")
            print(f"[ActionRouter] Reproduciendo en YouTube localmente: {cancion}")
            try:
                await session.send_tool_response(
                    function_responses=[
                        types.FunctionResponse(
                            name="reproducir_musica_youtube",
                            id=call_id,
                            response={"result": f"Reproduciendo '{cancion}' en YouTube."}
                        )
                    ]
                )
            except Exception as e:
                print(f"[ActionRouter] Error tool response música: {e}")

            import subprocess
            subprocess.Popen([sys.executable, _LOCAL_YOUTUBE_SCRIPT, cancion])
        else:
            print(f"[ActionRouter] Herramienta local desconocida rechazada: name={tool_name}, args={args}")
            if session:
                try:
                    await session.send_tool_response(
                        function_responses=[
                            types.FunctionResponse(
                                name=tool_name,
                                id=call_id,
                                response={"status": "rechazada", "mensaje": "No reconozco esa herramienta local."},
                            )
                        ]
                    )
                except Exception as e:
                    print(f"\033[36m[ActionRouter]\033[0m Error respondiendo tool desconocida: {e}")

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
