import time
import uuid
import json
import os
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    STALE = "stale"


@dataclass
class TaskRecord:
    task_id: str
    kind: str
    prompt: str
    status: TaskStatus = TaskStatus.PENDING
    result: str = ""
    error: str = ""
    turn_id: str | None = None
    tool_name: str = ""
    origin_call_id: str = ""
    lane: str = "slow_hermes"        # "local" | "fast_hermes" | "slow_hermes"
    session_id: str = ""             # ID de la sesion Live que originó la tarea
    priority: int = 50               # Menor = mayor prioridad en entrega
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class TaskLedger:
    """Registro ligero de tareas Hermes independiente de la sesion Live."""

    def __init__(self, max_tasks: int = 100, storage_path: str = "task_ledger.json"):
        self.max_tasks = max_tasks
        self.storage_path = Path(storage_path)
        self._tasks: list[TaskRecord] = []
        self._load_from_disk()

    def _load_from_disk(self):
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                loaded: list[TaskRecord] = []
                for t in data:
                    # Normalizar status string → enum (JSON no preserva tipos de Enum)
                    raw_status = t.get("status", "pending")
                    try:
                        t["status"] = TaskStatus(raw_status)
                    except ValueError:
                        t["status"] = TaskStatus.STALE
                    record = TaskRecord(**t)
                    # Tareas RUNNING al arrancar = proceso anterior crasheó; marcarlas STALE
                    if record.status == TaskStatus.RUNNING:
                        record.status = TaskStatus.STALE
                        record.error = "stale_on_restart"
                    loaded.append(record)
                self._tasks = loaded
            except Exception as e:
                print(f"Error loading task ledger: {e}")

    def _save_to_disk(self):
        try:
            with open(self.storage_path, "w") as f:
                json.dump([asdict(t) for t in self._tasks], f, indent=4)
        except Exception as e:
            print(f"Error saving task ledger: {e}")

    def create_task(
        self,
        kind: str,
        prompt: str,
        turn_id: str | None = None,
        tool_name: str = "",
        origin_call_id: str = "",
        lane: str = "slow_hermes",
        session_id: str = "",
        priority: int = 50,
    ) -> TaskRecord:
        task = TaskRecord(
            task_id=str(uuid.uuid4()),
            kind=kind,
            prompt=prompt,
            turn_id=turn_id,
            tool_name=tool_name,
            origin_call_id=origin_call_id,
            lane=lane,
            session_id=session_id,
            priority=priority,
        )
        self._tasks.append(task)
        if len(self._tasks) > self.max_tasks:
            self._tasks.pop(0)
        self._save_to_disk()
        print(f"[TaskLedger] create task={task.task_id} lane={task.lane} status=pending prompt_chars={len(task.prompt)}")
        return task

    def mark_running(self, task: TaskRecord | None, turn_id: str | None = None) -> None:
        self._update(task, TaskStatus.RUNNING, turn_id=turn_id)

    def mark_completed(self, task: TaskRecord | None, result: str = "") -> None:
        self._update(task, TaskStatus.COMPLETED, result=result)

    def mark_failed(self, task: TaskRecord | None, error: str = "") -> None:
        self._update(task, TaskStatus.FAILED, error=error)

    def mark_interrupted(self, task: TaskRecord | None, error: str = "") -> None:
        self._update(task, TaskStatus.INTERRUPTED, error=error)

    def mark_stale(self, task: TaskRecord | None, error: str = "") -> None:
        self._update(task, TaskStatus.STALE, error=error)

    def _update(
        self,
        task: TaskRecord | None,
        status: TaskStatus,
        result: str = "",
        error: str = "",
        turn_id: str | None = None,
    ) -> None:
        if not task:
            return
        task.status = status
        if result:
            task.result = result
        if error:
            task.error = error
        if turn_id:
            task.turn_id = turn_id
        task.updated_at = time.time()
        self._save_to_disk()

        if status == TaskStatus.RUNNING:
            print(f"[TaskLedger] running task={task.task_id} lane={task.lane}")
        elif status == TaskStatus.COMPLETED:
            print(f"[TaskLedger] completed task={task.task_id} lane={task.lane} text_chars={len(result)}")

    def active_tasks(self) -> list[TaskRecord]:
        return [
            task
            for task in self._tasks
            if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
        ]

    def pending_tasks(self, kind: str | None = None, lane: str | None = None) -> list[TaskRecord]:
        return [
            task
            for task in self._tasks
            if task.status == TaskStatus.PENDING
            and (kind is None or task.kind == kind)
            and (lane is None or task.lane == lane)
        ]

    def next_pending(self, kind: str | None = None, lane: str | None = None) -> TaskRecord | None:
        pending = self.pending_tasks(kind=kind, lane=lane)
        if not pending:
            return None
        return min(pending, key=lambda task: (task.priority, task.created_at))

    def recent_tasks(self, limit: int = 10) -> list[TaskRecord]:
        return self._tasks[-limit:]

    def running_tasks(self, kind: str | None = None, lane: str | None = None) -> list[TaskRecord]:
        return [
            task
            for task in self._tasks
            if task.status == TaskStatus.RUNNING
            and (kind is None or task.kind == kind)
            and (lane is None or task.lane == lane)
        ]

    def has_running_lane(self, lane: str) -> bool:
        """Verdadero si hay al menos una tarea RUNNING en el carril dado."""
        return any(
            task.status == TaskStatus.RUNNING and task.lane == lane
            for task in self._tasks
        )

    def next_pending_lane(self, lane: str) -> TaskRecord | None:
        """Próxima tarea pendiente en el carril dado, por prioridad y antigüedad."""
        return self.next_pending(lane=lane)
