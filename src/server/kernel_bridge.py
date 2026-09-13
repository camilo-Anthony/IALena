"""
kernel_bridge.py — Puente seguro entre el JarvisKernel y la API local.

Este módulo mantiene una referencia global al kernel activo y expone
métodos de solo lectura para la API. Nunca devuelve objetos internos
del kernel directamente — solo dicts serializables.
"""
from __future__ import annotations
import time
import sys
from collections import deque
from pathlib import Path
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


def _sanitize_json_obj(obj: Any) -> Any:
    """Sanitiza recursivamente cualquier objeto para garantizar compatibilidad con JSON/FastAPI."""
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        return obj
    # Soporte para tipos numpy o escalares con .item() o .tolist()
    if hasattr(obj, "item") and callable(obj.item):
        try:
            return _sanitize_json_obj(obj.item())
        except Exception:
            pass
    if hasattr(obj, "tolist") and callable(obj.tolist):
        try:
            return _sanitize_json_obj(obj.tolist())
        except Exception:
            pass
    if isinstance(obj, dict):
        return {str(k): _sanitize_json_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, deque)):
        return [_sanitize_json_obj(item) for item in obj]
    try:
        if isinstance(obj, (int, float)):
            return float(obj)
    except Exception:
        pass
    return str(obj)


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
    return _sanitize_json_obj(entries[-n:])


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
        return _sanitize_json_obj({
            "orb_state": orb_state,
            "uptime_seconds": uptime,
            "kernel_ready": False,
            "live_connected": False,
            "hermes_slow_ready": False,
            "hermes_fast_ready": False,
        })

    try:
        router = _kernel.action_router
        task_payload = router.task_status_payload()
        key_status = _get_key_rotator_status()

        return _sanitize_json_obj({
            "orb_state": orb_state,
            "uptime_seconds": uptime,
            "kernel_ready": True,
            "live_connected": _get_live_connected(),
            # SLOW runs in an isolated worker, so ``hermes_agent`` intentionally
            # remains None in this process. The adapter's availability contract is
            # the only truthful readiness signal for both execution lanes.
            "hermes_slow_ready": _brain_is_available(getattr(_kernel, "brain", None)),
            "hermes_fast_ready": _brain_is_available(getattr(_kernel, "brain_fast", None)),
            "activation_state": _kernel.activation_gate.state.value,
            "tasks": task_payload,
            "key_rotator": key_status,
            "delivery_queue": _get_delivery_queue_status(),
            "wake_word": _get_wake_word_status(),
        })
    except Exception as exc:
        return _sanitize_json_obj({
            "orb_state": "error",
            "uptime_seconds": uptime,
            "kernel_ready": True,
            "error": str(exc),
        })


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


def _brain_is_available(brain: Any) -> bool:
    if brain is None:
        return False
    try:
        return bool(brain.is_available())
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


def _get_wake_word_status() -> dict[str, Any]:
    if _kernel is None:
        return {"enabled": False, "ready": False}
    try:
        pipeline = getattr(_kernel, "audio_pipeline", None)
        if pipeline and hasattr(pipeline, "get_metrics"):
            return pipeline.get_metrics()
        detector = getattr(_kernel, "wake_word_detector", None)
        if detector and hasattr(detector, "get_metrics"):
            return detector.get_metrics()
        return {"enabled": False, "ready": False}
    except Exception:
        return {"enabled": False, "ready": False}


# ── Capabilities ───────────────────────────────────────────────────────────

def get_capabilities() -> dict[str, Any]:
    """CapabilityRegistry.snapshot_payload() + toolsets activos."""
    from src.kernel.capability_registry import capability_registry, TaskCapability
    snapshot = capability_registry.snapshot_payload()
    active_caps = [
        cap.value for cap in TaskCapability
        if capability_registry.has_capability("slow", cap)
    ]
    return _sanitize_json_obj({
        "registry": snapshot,
        "active_capabilities": active_caps,
    })


# ── Tasks ──────────────────────────────────────────────────────────────────

def get_tasks() -> dict[str, Any]:
    """Estado detallado de tareas."""
    if _kernel is None:
        return {"running": [], "pending": [], "recent": []}
    try:
        ledger = _kernel.task_ledger
        return _sanitize_json_obj({
            "running_slow": [_task_to_dict(t) for t in ledger.running_tasks("slow_hermes")],
            "running_fast": [_task_to_dict(t) for t in ledger.running_tasks("fast_hermes")],
            "pending_slow": [_task_to_dict(t) for t in ledger.pending_tasks("slow_hermes")],
            "recent": [_task_to_dict(t) for t in ledger.recent_tasks(10)],
        })
    except Exception as exc:
        return {"error": str(exc)}


def _task_to_dict(task: Any) -> dict[str, Any]:
    created_at = getattr(task, "created_at", 0)
    completed_at = getattr(task, "completed_at", 0)
    duration = round(completed_at - created_at, 1) if (completed_at and created_at) else None
    return {
        "task_id": getattr(task, "task_id", ""),
        "lane": getattr(task, "lane", ""),
        "prompt": getattr(task, "prompt", ""),
        "state": getattr(task, "state", ""),
        "result": getattr(task, "result_text", "") or getattr(task, "result", "") or "",
        "error": getattr(task, "error", "") or "",
        "created_at": created_at,
        "completed_at": completed_at,
        "duration": duration,
    }


async def dispatch_hermes_task(prompt: str, lane: str = "slow") -> dict[str, Any]:
    """Despacha una tarea a Hermes desde la API."""
    if _kernel is None or not hasattr(_kernel, "action_router"):
        return {"status": "error", "message": "Kernel no inicializado"}
    return await _kernel.action_router.dispatch_direct_task(prompt, lane=lane)


def get_scheduler_and_sentinel_status() -> dict[str, Any]:
    """Estado de los subsistemas autónomos (Hermes Cron y Sentinel)."""
    if _kernel is None:
        return {"scheduler": None, "sentinel": None}
    sched = getattr(_kernel, "hermes_scheduler", None)
    sent = getattr(_kernel, "system_sentinel", None)
    return _sanitize_json_obj({
        "scheduler": sched.get_status() if sched and hasattr(sched, "get_status") else None,
        "sentinel": sent.get_status() if sent and hasattr(sent, "get_status") else None,
    })


# ── Hermes config (read-only) ──────────────────────────────────────────────

def get_hermes_mcps() -> dict[str, Any]:
    """Lee MCP servers de ~/.hermes/config.yaml sin ejecutar nada."""
    try:
        import yaml
        config_path = _get_hermes_home_path() / "config.yaml"
        if not config_path.exists():
            return _sanitize_json_obj({"mcps": [], "config_path": str(config_path), "found": False})
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        mcps_raw = data.get("mcp_servers", {})
        mcps = []
        for name, cfg in mcps_raw.items():
            enabled = cfg.get("enabled", True)
            if isinstance(enabled, str):
                enabled = enabled.lower() not in {"false", "0", "off"}
            mcps.append({
                "name": name,
                "command": cfg.get("command", ""),
                "args": cfg.get("args", []),
                "url": cfg.get("url", ""),
                "timeout": cfg.get("timeout", 300),
                "enabled": enabled,
                "env": cfg.get("env", {}),
            })
        return _sanitize_json_obj({"mcps": mcps, "config_path": str(config_path), "found": True})
    except Exception as exc:
        return _sanitize_json_obj({"mcps": [], "error": str(exc)})


def save_hermes_mcp(name: str, mcp_config: dict[str, Any]) -> dict[str, Any]:
    """Agrega o actualiza un servidor MCP en ~/.hermes/config.yaml."""
    try:
        import yaml
        config_dir = _get_hermes_home_path()
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "config.yaml"
        data = {}
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        servers = data.setdefault("mcp_servers", {})
        entry: dict[str, Any] = {}
        if mcp_config.get("url"):
            entry["url"] = str(mcp_config["url"]).strip()
        if mcp_config.get("command"):
            entry["command"] = str(mcp_config["command"]).strip()
        if mcp_config.get("args"):
            args = mcp_config["args"]
            if isinstance(args, str):
                args = [a.strip() for a in args.split() if a.strip()]
            entry["args"] = args
        if mcp_config.get("env") and isinstance(mcp_config["env"], dict):
            entry["env"] = mcp_config["env"]
        entry["enabled"] = bool(mcp_config.get("enabled", True))
        servers[name] = entry
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
        return {"success": True, "name": name}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def remove_hermes_mcp(name: str) -> dict[str, Any]:
    """Elimina un servidor MCP de ~/.hermes/config.yaml."""
    try:
        import yaml
        config_path = _get_hermes_home_path() / "config.yaml"
        if not config_path.exists():
            return {"success": False, "error": "config.yaml not found"}
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        servers = data.get("mcp_servers", {})
        if name in servers:
            del servers[name]
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
            return {"success": True, "removed": name}
        return {"success": False, "error": f"Servidor '{name}' no encontrado"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def toggle_hermes_mcp(name: str) -> dict[str, Any]:
    """Alterna el estado enabled de un servidor MCP en ~/.hermes/config.yaml."""
    try:
        import yaml
        config_path = _get_hermes_home_path() / "config.yaml"
        if not config_path.exists():
            return {"success": False, "error": "config.yaml not found"}
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        servers = data.get("mcp_servers", {})
        if name in servers:
            current = servers[name].get("enabled", True)
            servers[name]["enabled"] = not current
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
            return {"success": True, "enabled": not current}
        return {"success": False, "error": f"Servidor '{name}' no encontrado"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def get_hermes_toolsets() -> dict[str, Any]:
    """Toolsets habilitados y deshabilitados desde el adapter."""
    try:
        from src.adapters.brain.hermes_adapter import _read_runtime_config
        config = _read_runtime_config()
        return _sanitize_json_obj({
            "enabled": config.get("enabled_toolsets", []),
            "disabled": config.get("disabled_toolsets", []),
            "platform": config.get("platform", "cli"),
        })
    except Exception as exc:
        return _sanitize_json_obj({"enabled": [], "disabled": [], "error": str(exc)})


def get_hermes_skills() -> dict[str, Any]:
    """Descubre las skills activas de Hermes desde todas sus raíces reales."""
    _ensure_hermes_import_path()
    project_root = Path(__file__).resolve().parents[2]
    bundled_root = project_root / "Hermes-Agent" / "skills"
    user_root = _get_hermes_home_path() / "skills"
    try:
        from agent.skill_utils import get_all_skills_dirs, is_excluded_skill_path, parse_frontmatter

        roots = [bundled_root, *get_all_skills_dirs()]
    except Exception:
        roots = [bundled_root, user_root]

        def is_excluded_skill_path(_: Path) -> bool:
            return False

        def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
            return {}, content

    records: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for root in roots:
        root_path = Path(root)
        if not root_path.exists():
            continue
        try:
            skill_paths = root_path.rglob("SKILL.md")
            for skill_path in skill_paths:
                if is_excluded_skill_path(skill_path):
                    continue
                resolved = str(skill_path.parent.resolve())
                if resolved in seen_paths:
                    continue
                seen_paths.add(resolved)
                try:
                    content = skill_path.read_text(encoding="utf-8")
                    metadata, _ = parse_frontmatter(content)
                    description = str(metadata.get("description") or "").strip()
                    if not description:
                        for line in content.splitlines():
                            if line.startswith("# "):
                                description = line[2:].strip()
                                break
                except Exception:
                    description = ""

                try:
                    if skill_path.is_relative_to(user_root):
                        source = "perfil"
                        writable = True
                    elif skill_path.is_relative_to(bundled_root):
                        source = "integrada"
                        writable = False
                    else:
                        source = "externa"
                        writable = False
                except ValueError:
                    source = "externa"
                    writable = False

                records.append({
                    "name": skill_path.parent.name,
                    "description": description or "Skill de Hermes sin descripción declarada.",
                    "source": source,
                    "writable": writable,
                    "path": str(skill_path.parent),
                })
        except OSError:
            continue
    return _sanitize_json_obj({"skills": sorted(records, key=lambda item: (item["name"].lower(), item["source"]))})


def _ensure_hermes_import_path() -> None:
    project_root = Path(__file__).resolve().parents[2]
    hermes_dir = str(project_root / "Hermes-Agent")
    if hermes_dir not in sys.path:
        sys.path.insert(0, hermes_dir)


def _get_hermes_home_path() -> Path:
    _ensure_hermes_import_path()
    try:
        from hermes_constants import get_hermes_home
        return Path(get_hermes_home())
    except Exception:
        return Path.home() / ".hermes"


def _read_context_document(path: Path, max_chars: int = 12000) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "content": "", "updated_at": None}
    try:
        content = path.read_text(encoding="utf-8")
        if len(content) > max_chars:
            content = content[-max_chars:]
        return {
            "exists": True,
            "content": content,
            "updated_at": path.stat().st_mtime,
        }
    except Exception as exc:
        return {"exists": True, "content": "", "updated_at": None, "error": str(exc)}


def get_hermes_memory() -> dict[str, Any]:
    """Expone contexto persistente para revisión; la escritura sigue siendo autoridad de Hermes."""
    home = _get_hermes_home_path()
    return _sanitize_json_obj({
        "home_ready": home.exists(),
        "identity": _read_context_document(home / "SOUL.md"),
        "user_memory": _read_context_document(home / "memories" / "USER.md"),
        "agent_memory": _read_context_document(home / "memories" / "MEMORY.md"),
    })


def get_hermes_cron_jobs() -> dict[str, Any]:
    """Lee los cron jobs nativos de Hermes sin usar la UI Electron."""
    try:
        _ensure_hermes_import_path()
        from cron.jobs import list_jobs
        return _sanitize_json_obj({"jobs": list_jobs(include_disabled=True)})
    except Exception as exc:
        return _sanitize_json_obj({"jobs": [], "error": str(exc)})


def create_hermes_cron_job(prompt: str, schedule: str, name: str = "") -> dict[str, Any]:
    try:
        _ensure_hermes_import_path()
        from cron.jobs import create_job
        job = create_job(prompt=prompt, schedule=schedule, name=name or None, deliver="local")
        return _sanitize_json_obj({"success": True, "job": job})
    except Exception as exc:
        return _sanitize_json_obj({"success": False, "error": str(exc)})


def set_hermes_cron_job_state(job_id: str, action: str) -> dict[str, Any]:
    try:
        _ensure_hermes_import_path()
        from cron.jobs import pause_job, resume_job, trigger_job
        actions = {"pause": pause_job, "resume": resume_job, "trigger": trigger_job}
        operation = actions.get(action)
        if operation is None:
            return {"success": False, "error": "Acción de cron no permitida."}
        job = operation(job_id)
        if job is None:
            return {"success": False, "error": "Cron job no encontrado."}
        return _sanitize_json_obj({"success": True, "job": job})
    except Exception as exc:
        return _sanitize_json_obj({"success": False, "error": str(exc)})


def update_hermes_cron_job(job_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Actualiza sólo los campos de cron que son seguros de editar desde JARVIS."""
    allowed_fields = {"name", "prompt", "schedule"}
    safe_updates = {key: value for key, value in (updates or {}).items() if key in allowed_fields}
    if not safe_updates:
        return {"success": False, "error": "No se recibió ningún campo de cron editable."}
    try:
        _ensure_hermes_import_path()
        from cron.jobs import update_job

        job = update_job(job_id, safe_updates)
        if job is None:
            return {"success": False, "error": "Cron job no encontrado."}
        return _sanitize_json_obj({"success": True, "job": job})
    except Exception as exc:
        return _sanitize_json_obj({"success": False, "error": str(exc)})


def delete_hermes_cron_job(job_id: str) -> dict[str, Any]:
    """Elimina un cron job concreto mediante la API validada de Hermes."""
    try:
        _ensure_hermes_import_path()
        from cron.jobs import remove_job

        if not remove_job(job_id):
            return {"success": False, "error": "Cron job no encontrado."}
        return {"success": True, "removed": job_id}
    except Exception as exc:
        return _sanitize_json_obj({"success": False, "error": str(exc)})


def get_hermes_cron_outputs(job_id: str, limit: int = 10) -> dict[str, Any]:
    """Retorna salida histórica acotada de un job validado por Hermes."""
    try:
        _ensure_hermes_import_path()
        from cron.jobs import get_job

        job = get_job(job_id)
        if job is None:
            return {"outputs": [], "error": "Cron job no encontrado."}
        canonical_id = str(job["id"])
        if not canonical_id or any(token in canonical_id for token in ("/", "\\", "..")):
            return {"outputs": [], "error": "Identificador de cron inválido."}

        output_root = (_get_hermes_home_path() / "cron" / "output").resolve()
        output_dir = (output_root / canonical_id).resolve()
        if output_dir.parent != output_root or not output_dir.exists():
            return {"outputs": []}

        records = []
        for output_path in sorted(output_dir.glob("*.md"), key=lambda path: path.stat().st_mtime, reverse=True)[:max(1, min(limit, 25))]:
            try:
                content = output_path.read_text(encoding="utf-8")
                records.append({
                    "name": output_path.name,
                    "created_at": output_path.stat().st_mtime,
                    "content": content[-16000:],
                })
            except OSError:
                continue
        return _sanitize_json_obj({"outputs": records})
    except Exception as exc:
        return _sanitize_json_obj({"outputs": [], "error": str(exc)})


def reload_hermes_slow_worker() -> dict[str, Any]:
    """Aplica configuración al worker SLOW sin reiniciar voz, FAST ni JARVIS."""
    if _kernel is None:
        return {"success": False, "error": "Kernel no registrado."}
    brain = getattr(_kernel, "brain", None)
    if brain is None or not hasattr(brain, "reload_slow_worker"):
        return {"success": False, "error": "El worker Hermes SLOW no admite recarga en caliente."}
    try:
        success, message = brain.reload_slow_worker()
        return {"success": bool(success), "message": str(message)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
