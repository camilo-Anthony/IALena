"""
kernel_bridge.py — Puente seguro entre el JarvisKernel y la API local.

Este módulo mantiene una referencia global al kernel activo y expone
métodos de solo lectura para la API. Nunca devuelve objetos internos
del kernel directamente — solo dicts serializables.
"""
from __future__ import annotations
import time
from collections import deque
from threading import Lock
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.kernel.jarvis_kernel import JarvisKernel

# ── Referencia global al kernel (set desde main.py al arrancar) ────────────
_kernel: Optional["JarvisKernel"] = None
_start_time: float = time.time()

# ── Log buffer circular ────────────────────────────────────────────────────
_LOG_MAXLEN = 200
_log_buffer: deque[dict[str, Any]] = deque(maxlen=_LOG_MAXLEN)
_log_lock = Lock()


def append_log(level: str, message: str, source: str = "kernel") -> None:
    """Añade una entrada al buffer circular de logs en tiempo real."""
    entry = {
        "ts": time.time(),
        "level": level.upper(),
        "source": source,
        "message": message,
    }
    with _log_lock:
        _log_buffer.append(entry)


def get_logs(n: int = 100) -> list[dict[str, Any]]:
    """Retorna los últimos n logs del buffer (más recientes al final)."""
    with _log_lock:
        entries = list(_log_buffer)
    return entries[-n:]


def register_kernel(kernel: "JarvisKernel") -> None:
    """Registra el kernel activo. Llamar desde main.py después de crear JarvisKernel."""
    global _kernel
    _kernel = kernel


def get_kernel() -> Optional["JarvisKernel"]:
    return _kernel


# ── Estado del Orbe ────────────────────────────────────────────────────────

def get_orb_state() -> str:
    """
    Devuelve el estado actual del orbe como string.
    Mapea desde ActivationGate + TaskLedger + ActionRouter.
    """
    if _kernel is None:
        return "dormant"

    try:
        gate = _kernel.activation_gate
        router = _kernel.action_router
        ledger = _kernel.task_ledger
        playback = _kernel.audio_playback

        from src.kernel.activation_gate import ActivationState

        # Confirmación pendiente (prioridad máxima)
        if router.pending_confirmation:
            return "confirmation_pending"

        # Estado del gate
        state = gate.state
        if state == ActivationState.SILENT_RECONNECT:
            return "reconnecting"
        if state == ActivationState.DORMANT:
            return "dormant"
        if state == ActivationState.DELIVERING:
            return "delivery_waiting"

        # ACTIVE — determinar qué está haciendo
        if getattr(playback, "is_busy", False):
            return "speaking"

        running_slow = ledger.running_tasks(lane="slow_hermes")
        running_fast = ledger.running_tasks(lane="fast_hermes")
        pending = ledger.pending_tasks(lane="slow_hermes")

        if running_slow:
            return "working_slow"
        if running_fast:
            return "thinking_fast"
        if pending:
            return "delivery_waiting"

        return "listening"

    except Exception:
        return "error"


# ── Status completo ────────────────────────────────────────────────────────

def get_status() -> dict[str, Any]:
    """Estado completo del sistema para GET /status."""
    orb_state = get_orb_state()
    uptime = round(time.time() - _start_time, 1)

    if _kernel is None:
        return {
            "orb_state": orb_state,
            "uptime_seconds": uptime,
            "kernel_ready": False,
            "live_connected": False,
            "hermes_slow_ready": False,
            "hermes_fast_ready": False,
        }

    try:
        router = _kernel.action_router
        task_payload = router.task_status_payload()
        key_status = _get_key_rotator_status()

        return {
            "orb_state": orb_state,
            "uptime_seconds": uptime,
            "kernel_ready": True,
            "live_connected": _get_live_connected(),
            "hermes_slow_ready": _kernel.brain is not None and getattr(_kernel.brain, "hermes_agent", None) is not None,
            "hermes_fast_ready": _kernel.brain_fast is not None and getattr(_kernel.brain_fast, "hermes_agent", None) is not None,
            "activation_state": _kernel.activation_gate.state.value,
            "tasks": task_payload,
            "key_rotator": key_status,
            "delivery_queue": _get_delivery_queue_status(),
        }
    except Exception as exc:
        return {
            "orb_state": "error",
            "uptime_seconds": uptime,
            "kernel_ready": True,
            "error": str(exc),
        }


def _get_live_connected() -> bool:
    if _kernel is None:
        return False
    try:
        va = _kernel.voice_assistant
        if va is None:
            return False
        return getattr(va, "session", None) is not None
    except Exception:
        return False


def _get_key_rotator_status() -> dict[str, Any]:
    """Estado seguro del KeyRotator (sin keys completas)."""
    try:
        from src.adapters.brain.key_rotator import _RotatingProxy
        keys = _RotatingProxy._keys
        count = len(keys)
        call_count = _RotatingProxy._call_counter
        # Key activa enmascarada: mostrar primeros 8 y últimos 4 chars
        active_masked = "—"
        if keys and call_count > 0:
            active_idx = (call_count - 1) % count
            k = keys[active_idx]
            active_masked = f"{k[:8]}...{k[-4:]}" if len(k) > 12 else "****"
        return {
            "pool_size": count,
            "call_count": call_count,
            "active_key_masked": active_masked,
        }
    except Exception:
        return {"pool_size": 0, "call_count": 0, "active_key_masked": "—"}


def _get_delivery_queue_status() -> dict[str, Any]:
    if _kernel is None:
        return {"pending": 0, "delivering": 0}
    try:
        dq = _kernel.action_router.delivery_queue
        return {
            "pending": dq.pending_count(),
            "delivering": dq.delivering_count(),
        }
    except Exception:
        return {"pending": 0, "delivering": 0}


# ── Capabilities ───────────────────────────────────────────────────────────

def get_capabilities() -> dict[str, Any]:
    """CapabilityRegistry.snapshot_payload() + toolsets activos."""
    from src.kernel.capability_registry import capability_registry, TaskCapability
    snapshot = capability_registry.snapshot_payload()
    active_caps = [
        cap.value for cap in TaskCapability
        if capability_registry.has_capability("slow", cap)
    ]
    return {
        "registry": snapshot,
        "active_capabilities": active_caps,
    }


# ── Tasks ──────────────────────────────────────────────────────────────────

def get_tasks() -> dict[str, Any]:
    """Estado detallado de tareas."""
    if _kernel is None:
        return {"running": [], "pending": [], "recent": []}
    try:
        ledger = _kernel.task_ledger
        return {
            "running_slow": [_task_to_dict(t) for t in ledger.running_tasks("slow_hermes")],
            "running_fast": [_task_to_dict(t) for t in ledger.running_tasks("fast_hermes")],
            "pending_slow": [_task_to_dict(t) for t in ledger.pending_tasks("slow_hermes")],
            "recent": [_task_to_dict(t) for t in ledger.recent_tasks(10)],
        }
    except Exception as exc:
        return {"error": str(exc)}


def _task_to_dict(task: Any) -> dict[str, Any]:
    return {
        "task_id": getattr(task, "task_id", ""),
        "lane": getattr(task, "lane", ""),
        "prompt": getattr(task, "prompt", "")[:120],  # truncar para seguridad
        "state": getattr(task, "state", ""),
        "created_at": getattr(task, "created_at", 0),
    }


# ── Hermes config (read-only) ──────────────────────────────────────────────

def get_hermes_mcps() -> dict[str, Any]:
    """Lee MCP servers de ~/.hermes/config.yaml sin ejecutar nada."""
    try:
        import yaml
        from pathlib import Path
        config_path = Path.home() / ".hermes" / "config.yaml"
        if not config_path.exists():
            return {"mcps": [], "config_path": str(config_path), "found": False}
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        mcps_raw = data.get("mcp_servers", {})
        mcps = []
        for name, cfg in mcps_raw.items():
            mcps.append({
                "name": name,
                "command": cfg.get("command", ""),
                "args": cfg.get("args", []),
                "url": cfg.get("url", ""),
                "timeout": cfg.get("timeout", 300),
            })
        return {"mcps": mcps, "config_path": str(config_path), "found": True}
    except Exception as exc:
        return {"mcps": [], "error": str(exc)}


def get_hermes_toolsets() -> dict[str, Any]:
    """Toolsets habilitados y deshabilitados desde el adapter."""
    try:
        from src.adapters.brain.hermes_adapter import _read_runtime_config
        config = _read_runtime_config()
        return {
            "enabled": config.get("enabled_toolsets", []),
            "disabled": config.get("disabled_toolsets", []),
            "platform": config.get("platform", "cli"),
        }
    except Exception as exc:
        return {"enabled": [], "disabled": [], "error": str(exc)}
