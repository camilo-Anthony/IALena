"""Worker aislado para el carril SLOW de Hermes.

El proceso principal nunca ejecuta AIAgent directamente en SLOW. Este worker
mantiene una sola instancia de Hermes, procesa una tarea a la vez y acepta una
cancelación cooperativa mientras la tarea está ejecutándose. Si el proceso no
responde, el supervisor puede terminarlo sin dejar un hilo huérfano.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from typing import Any


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
_HERMES_DIR = os.path.join(_PROJECT_ROOT, "Hermes-Agent")
if _HERMES_DIR not in sys.path:
    sys.path.append(_HERMES_DIR)


def _safe_ipc_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _safe_ipc_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_ipc_value(item) for item in value]
    return repr(value)


def _send(conn, lock: threading.Lock, message: dict[str, Any]) -> bool:
    try:
        with lock:
            conn.send(message)
        return True
    except (BrokenPipeError, EOFError, OSError):
        return False


def _inspect_tools(agent) -> list[str]:
    if hasattr(agent, "valid_tool_names") and agent.valid_tool_names:
        return sorted(str(name) for name in agent.valid_tool_names)
    if hasattr(agent, "tools") and agent.tools:
        return sorted(
            str(tool["function"]["name"])
            for tool in agent.tools
            if isinstance(tool, dict) and "function" in tool and "name" in tool["function"]
        )
    return []


def _register_mcp_servers(report_status) -> None:
    servers: dict[str, Any] = {}
    try:
        import yaml
        from tools.mcp_tool import register_mcp_servers

        cfg_path = os.path.expanduser("~/.hermes/config.yaml")
        if not os.path.exists(cfg_path):
            return
        with open(cfg_path, "r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}
        servers = config.get("mcp_servers", {})
        if not isinstance(servers, dict):
            servers = {}
        servers = {
            str(name): value
            for name, value in servers.items()
            if not isinstance(value, dict) or value.get("enabled", True)
        }
        if servers:
            print(f"[HermesWorker][SLOW] Inicializando MCP: {list(servers.keys())}", flush=True)
            registered = register_mcp_servers(servers) or []
            print(f"[HermesWorker][SLOW] MCP registrados: {len(registered)}", flush=True)
            tools = [str(tool) for tool in registered]
            if tools:
                report_status("ready", list(servers.keys()), tools)
            else:
                report_status(
                    "failed",
                    list(servers.keys()),
                    [],
                    "El servidor MCP no registró herramientas utilizables.",
                )
        else:
            report_status("unconfigured", [], [])
    except Exception as exc:
        print(f"[HermesWorker][SLOW] Aviso MCP: {exc}", flush=True)
        report_status("failed", list(servers.keys()), [], str(exc))


def _result_payload(result: Any, started_at: float) -> dict[str, Any]:
    if isinstance(result, dict):
        text = result.get("final_response") or ""
        interrupted = bool(result.get("interrupted"))
        failed = bool(result.get("failed"))
        completed = bool(result.get("completed"))
        reason = result.get("error") or result.get("turn_exit_reason")
        success = completed and not failed and not interrupted and bool(text)
        return {
            "type": "result",
            "text": text,
            "raw_text": text,
            "success": success,
            "error": None if success else (reason or ("Interrumpido" if interrupted else "Sin resultado textual")),
            "interrupted": interrupted,
            "started_at": started_at,
            "finished_at": time.time(),
        }

    text = result or ""
    return {
        "type": "result",
        "text": text,
        "raw_text": text,
        "success": bool(text),
        "error": None if text else "Sin resultado textual",
        "interrupted": False,
        "started_at": started_at,
        "finished_at": time.time(),
    }


def run_slow_worker(conn, proxy_base_url: str, model_brain: str, runtime_config: dict[str, Any]) -> None:
    """Entry point top-level compatible con multiprocessing spawn en Windows."""
    send_lock = threading.Lock()
    agent = None
    try:
        from run_agent import AIAgent  # type: ignore

        def emit(event_type: str, *args):
            _send(
                conn,
                send_lock,
                {"type": "event", "event_type": event_type, "args": _safe_ipc_value(args)},
            )

        agent = AIAgent(
            base_url=proxy_base_url,
            api_key="proxy-managed",
            model=model_brain,
            quiet_mode=True,
            save_trajectories=True,
            enabled_toolsets=runtime_config["enabled_toolsets"],
            disabled_toolsets=runtime_config["disabled_toolsets"],
            platform=runtime_config["platform"],
            user_name=runtime_config["user_name"],
            load_soul_identity=runtime_config["load_soul_identity"],
            skip_context_files=runtime_config["skip_context_files"],
            skip_memory=runtime_config["skip_memory"],
            pass_session_id=runtime_config["pass_session_id"],
            checkpoints_enabled=True,
            tool_start_callback=lambda *args: emit("tool_start", *args),
            tool_complete_callback=lambda *args: emit("tool_complete", *args),
            status_callback=lambda *args: emit("status", *args),
        )
        skill_nudge = int(os.getenv("HERMES_SKILL_NUDGE_INTERVAL", "0"))
        if hasattr(agent, "_skill_nudge_interval"):
            setattr(agent, "_skill_nudge_interval", skill_nudge)
        # MCP discovery can block up to its own 120s budget. It must not hold
        # the readiness handshake hostage: Hermes can answer normal tasks while
        # MCP connects in the background, and a broken MCP must remain isolated.
        def report_mcp_status(status: str, servers: list[str], tools: list[str], error: str = "") -> None:
            _send(
                conn,
                send_lock,
                {
                    "type": "mcp_status",
                    "status": status,
                    "servers": servers,
                    "tools": tools,
                    "error": error,
                },
            )

        mcp_thread = threading.Thread(
            target=_register_mcp_servers,
            args=(report_mcp_status,),
            name="HermesSlowMCPInit",
            daemon=True,
        )
        mcp_thread.start()
        print("[HermesWorker][SLOW] MCP en inicializacion de fondo; Hermes listo para tareas.", flush=True)
        _send(conn, send_lock, {"type": "ready", "tools": _inspect_tools(agent), "skill_nudge": skill_nudge})
    except Exception as exc:
        _send(conn, send_lock, {"type": "init_error", "error": str(exc)})
        try:
            conn.close()
        finally:
            return

    while True:
        try:
            command = conn.recv()
        except (EOFError, BrokenPipeError, OSError):
            return

        command_type = command.get("type") if isinstance(command, dict) else None
        if command_type == "shutdown":
            return
        if command_type == "review_memory":
            try:
                messages = list(command.get("messages") or [])
                if hasattr(agent, "_spawn_background_review"):
                    agent._spawn_background_review(messages, review_memory=True, review_skills=bool(command.get("review_skills")))
                    payload = {"type": "result", "text": "Revision de memoria de sesion encolada.", "success": True, "error": None, "interrupted": False}
                elif hasattr(agent, "commit_memory_session"):
                    agent.commit_memory_session(messages)
                    payload = {"type": "result", "text": "Sesion de memoria consolidada.", "success": True, "error": None, "interrupted": False}
                else:
                    payload = {"type": "result", "text": "", "success": False, "error": "Hermes no expone revision de memoria.", "interrupted": False}
            except Exception as exc:
                payload = {"type": "result", "text": "", "success": False, "error": str(exc), "interrupted": False}
            _send(conn, send_lock, payload)
            continue
        if command_type != "run":
            continue

        task = str(command.get("task") or "")
        started_at = time.time()
        result_holder: dict[str, Any] = {}
        finished = threading.Event()

        def execute() -> None:
            try:
                result_holder["payload"] = _result_payload(agent.run_conversation(task), started_at)
            except Exception as exc:
                result_holder["payload"] = {
                    "type": "result", "text": "", "raw_text": "", "success": False,
                    "error": str(exc), "interrupted": False,
                    "started_at": started_at, "finished_at": time.time(),
                }
            finally:
                finished.set()

        running = threading.Thread(target=execute, name="HermesSlowTask", daemon=True)
        running.start()

        while not finished.is_set():
            if not conn.poll(0.1):
                continue
            try:
                control = conn.recv()
            except (EOFError, BrokenPipeError, OSError):
                return
            control_type = control.get("type") if isinstance(control, dict) else None
            if control_type == "cancel":
                try:
                    if hasattr(agent, "interrupt"):
                        agent.interrupt(str(control.get("reason") or "Cancelado por JARVIS"))
                except Exception as exc:
                    _send(conn, send_lock, {"type": "worker_log", "message": f"Error solicitando cancelacion: {exc}"})
            elif control_type == "shutdown":
                return

        running.join(timeout=0.2)
        _send(conn, send_lock, result_holder["payload"])
