import os
import time
from dataclasses import dataclass
from enum import Enum


class ActivationState(str, Enum):
    DORMANT = "dormant"
    ACTIVE = "active"
    SILENT_RECONNECT = "silent_reconnect"
    DELIVERING = "delivering"


@dataclass
class WakeRequest:
    source: str
    reason: str
    priority: int = 50
    turn_id: str | None = None
    created_at: float = 0.0


class ActivationGate:
    """
    Decide cuando la voz puede hablar o usar herramientas.

    Hermes puede pedir despertar al asistente, pero no controla directamente
    el microfono ni la sesion Live.
    """

    def __init__(self, idle_sleep_seconds: float | None = None):
        self.idle_sleep_seconds = (
            self._read_float_env("ACTIVATION_IDLE_SLEEP_SECONDS", 45.0)
            if idle_sleep_seconds is None
            else max(0.0, idle_sleep_seconds)
        )
        self.state = ActivationState.DORMANT
        self.session_epoch = 0
        self.last_user_voice_at = 0.0
        self.last_state_change_at = time.monotonic()
        self.pending_wake_requests: list[WakeRequest] = []

    @staticmethod
    def _read_float_env(name: str, default: float) -> float:
        try:
            return max(0.0, float(os.getenv(name, str(default))))
        except ValueError:
            return default

    def _set_state(self, state: ActivationState, reason: str = "") -> None:
        if self.state == state:
            return
        old_state = self.state
        self.state = state
        self.last_state_change_at = time.monotonic()
        suffix = f": {reason}" if reason else ""
        print(f"[ActivationGate] {old_state.value} -> {state.value}{suffix}")

    def start_live_session(self, reason: str = "live_session_started") -> int:
        self.session_epoch += 1
        self._set_state(ActivationState.SILENT_RECONNECT, reason)
        return self.session_epoch

    def mark_user_voice(self, reason: str = "user_voice") -> None:
        self.last_user_voice_at = time.monotonic()
        if self.state in (
            ActivationState.DORMANT,
            ActivationState.SILENT_RECONNECT,
            ActivationState.DELIVERING,
        ):
            self._set_state(ActivationState.ACTIVE, reason)

    def mark_wake_word(self, phrase: str = "") -> None:
        reason = f"wake_word:{phrase}" if phrase else "wake_word"
        self.mark_user_voice(reason)

    def sleep_if_idle(self) -> bool:
        if self.state not in (
            ActivationState.ACTIVE,
            ActivationState.DELIVERING,
            ActivationState.SILENT_RECONNECT,
        ):
            return False
        if self.idle_sleep_seconds <= 0:
            return False
        if self.state == ActivationState.DELIVERING:
            reference = self.last_state_change_at
        elif self.state == ActivationState.SILENT_RECONNECT:
            reference = self.last_user_voice_at or self.last_state_change_at
        else:
            reference = self.last_user_voice_at or self.last_state_change_at
        if time.monotonic() - reference < self.idle_sleep_seconds:
            return False
        self._set_state(ActivationState.DORMANT, "idle_timeout")
        return True

    def request_wake(
        self,
        source: str,
        reason: str,
        priority: int = 50,
        turn_id: str | None = None,
    ) -> WakeRequest:
        request = WakeRequest(
            source=source,
            reason=reason,
            priority=priority,
            turn_id=turn_id,
            created_at=time.monotonic(),
        )
        self.pending_wake_requests.append(request)
        print(
            f"[ActivationGate] Wake request: source={source}, reason={reason}, "
            f"priority={priority}, turn={turn_id or 'none'}"
        )
        return request

    def begin_delivery(self, request: WakeRequest | None = None) -> None:
        if request and request in self.pending_wake_requests:
            self.pending_wake_requests.remove(request)
        self._set_state(ActivationState.DELIVERING, "delivery")

    def finish_delivery(self) -> None:
        if self.state == ActivationState.DELIVERING:
            self._set_state(ActivationState.ACTIVE, "delivery_finished")

    def force_sleep(self, reason: str = "forced_sleep") -> None:
        self._set_state(ActivationState.DORMANT, reason)

    def allows_model_output(self) -> bool:
        return self.state in (ActivationState.ACTIVE, ActivationState.DELIVERING)

    def allows_user_tool_call(self) -> bool:
        return self.state == ActivationState.ACTIVE
