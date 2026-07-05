import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


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
    created_at: float = field(default_factory=time.monotonic)
    updated_at: float = field(default_factory=time.monotonic)


class TaskLedger:
    """Registro ligero de tareas Hermes independiente de la sesion Live."""

    def __init__(self, max_tasks: int = 100):
        self.max_tasks = max_tasks
        self._tasks: list[TaskRecord] = []

    def create_task(
        self,
        kind: str,
        prompt: str,
        turn_id: str | None = None,
        tool_name: str = "",
        origin_call_id: str = "",
    ) -> TaskRecord:
        task = TaskRecord(
            task_id=str(uuid.uuid4()),
            kind=kind,
            prompt=prompt,
            turn_id=turn_id,
            tool_name=tool_name,
            origin_call_id=origin_call_id,
        )
        self._tasks.append(task)
        if len(self._tasks) > self.max_tasks:
            self._tasks.pop(0)
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
        task.updated_at = time.monotonic()

    def active_tasks(self) -> list[TaskRecord]:
        return [
            task
            for task in self._tasks
            if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
        ]

    def pending_tasks(self, kind: str | None = None) -> list[TaskRecord]:
        return [
            task
            for task in self._tasks
            if task.status == TaskStatus.PENDING and (kind is None or task.kind == kind)
        ]

    def next_pending(self, kind: str | None = None) -> TaskRecord | None:
        pending = self.pending_tasks(kind)
        if not pending:
            return None
        return min(pending, key=lambda task: task.created_at)

    def recent_tasks(self, limit: int = 10) -> list[TaskRecord]:
        return self._tasks[-limit:]

    def running_tasks(self, kind: str | None = None) -> list[TaskRecord]:
        return [
            task
            for task in self._tasks
            if task.status == TaskStatus.RUNNING and (kind is None or task.kind == kind)
        ]
