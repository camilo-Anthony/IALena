import os
import sys
import asyncio
import time
import threading
from typing import Callable, Optional, Dict, Any

# Asegurar que Hermes-Agent está en el path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
_HERMES_DIR = os.path.join(_PROJECT_ROOT, "Hermes-Agent")
if _HERMES_DIR not in sys.path:
    sys.path.append(_HERMES_DIR)

from src.core.interfaces.brain import IAgentBrain, BrainResult

# Importaciones seguras de Hermes
try:
    from run_agent import AIAgent  # type: ignore
except ImportError:
    AIAgent = None

from src.adapters.brain.key_rotator import start_proxy


def _parse_csv_env(name: str) -> Optional[list[str]]:
    """Lee una variable CSV/semicolon y devuelve items unicos preservando orden."""
    raw = os.getenv(name)
    if raw is None:
        return None

    values: list[str] = []
    for chunk in raw.replace(";", ",").split(","):
        value = chunk.strip()
        if value and value not in values:
            values.append(value)
    return values or None


def _read_optional_env(name: str) -> Optional[str]:
    raw = os.getenv(name)
    if raw is None:
        return None
    value = raw.strip()
    return value or None


def _read_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _resolve_platform_toolsets(platform: Optional[str]) -> Optional[list[str]]:
    """Usa la resolucion nativa de Hermes para platform_toolsets."""
    if not platform:
        return None

    try:
        from hermes_cli.config import load_config  # type: ignore
        from hermes_cli.tools_config import _get_platform_tools  # type: ignore

        return sorted(_get_platform_tools(load_config(), platform))
    except Exception as exc:
        print(
            f"[HermesAdapter] No se pudo resolver platform_toolsets "
            f"para '{platform}': {exc}"
        )
        return None


def _read_runtime_config() -> Dict[str, Any]:
    platform = _read_optional_env("HERMES_PLATFORM")
    enabled_toolsets = _parse_csv_env("HERMES_ENABLED_TOOLSETS")
    if enabled_toolsets is None:
        enabled_toolsets = _resolve_platform_toolsets(platform)

    return {
        "platform": platform,
        "enabled_toolsets": enabled_toolsets,
        "disabled_toolsets": _parse_csv_env("HERMES_DISABLED_TOOLSETS"),
        "user_name": _read_optional_env("USER_NAME"),
        "load_soul_identity": _read_bool_env("HERMES_LOAD_SOUL_IDENTITY", True),
        "skip_context_files": _read_bool_env("HERMES_SKIP_CONTEXT_FILES", False),
        "skip_memory": _read_bool_env("HERMES_SKIP_MEMORY", False),
        "pass_session_id": _read_bool_env("HERMES_PASS_SESSION_ID", True),
    }


def _format_config_list(values: Optional[list[str]]) -> str:
    if values is None:
        return "default"
    if not values:
        return "none"
    return ",".join(values)


class HermesAdapter(IAgentBrain):
    """Adaptador que envuelve al sistema AIAgent de Hermes para actuar como Cerebro de JARVIS"""
    
    def __init__(self, api_keys: list, model_brain: str):
        self.hermes_agent = None

        # Diccionario para enrutar eventos por ID de hilo
        self._thread_listeners: Dict[int, Callable] = {}
        self._listeners_lock = threading.Lock()

        # Lock async para serializar la ejecución de Hermes por event loop
        self._async_locks: Dict[asyncio.AbstractEventLoop, asyncio.Lock] = {}

        if not AIAgent:
            print("[HermesAdapter] ERROR: No se encontró el módulo Hermes Agent en el path.")
            return

        try:
            # Iniciamos el proxy de llaves local
            proxy_port = start_proxy(api_keys)
            proxy_base_url = f"http://127.0.0.1:{proxy_port}/v1/"

            print(f"[HermesAdapter] Inicializando Hermes Core ({len(api_keys)} clave(s) en rotación)…")

            runtime_config = _read_runtime_config()
            print(
                "[HermesAdapter] Config Hermes: "
                f"platform={runtime_config['platform'] or 'default'}, "
                f"enabled_toolsets={_format_config_list(runtime_config['enabled_toolsets'])}, "
                f"disabled_toolsets={_format_config_list(runtime_config['disabled_toolsets'])}, "
                f"identity={'on' if runtime_config['load_soul_identity'] else 'off'}, "
                f"memory={'off' if runtime_config['skip_memory'] else 'on'}"
            )

            self.hermes_agent = AIAgent(
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
                tool_start_callback=self._on_tool_start,
                tool_complete_callback=self._on_tool_complete,
                status_callback=self._on_status,
            )

            # Desactivar self-improvement en modo voz
            self.hermes_agent._skill_nudge_interval = 0

            print("[HermesAdapter] Hermes Core listo (rotación activa).")
        except Exception as exc:
            print(f"[HermesAdapter] Error al inicializar: {exc}")

    # ── Callbacks de Enrutamiento Dinámico ────────────────────────────────

    def _get_current_listener(self) -> Optional[Callable]:
        tid = threading.get_ident()
        with self._listeners_lock:
            return self._thread_listeners.get(tid)

    def _on_tool_start(self, tc_id, name, display_args):
        listener = self._get_current_listener()
        if listener:
            listener("tool_start", tc_id, name, display_args)

    def _on_tool_complete(self, tc_id, name, display_args, result):
        listener = self._get_current_listener()
        if listener:
            listener("tool_complete", tc_id, name, display_args, result)

    def _on_status(self, kind, message):
        listener = self._get_current_listener()
        if listener:
            listener("status", kind, message)

    # ── Interfaz IAgentBrain ──────────────────────────────────────────────

    def _get_lock(self):
        loop = asyncio.get_running_loop()
        if loop not in self._async_locks:
            self._async_locks[loop] = asyncio.Lock()
        return self._async_locks[loop]

    async def run_task(self, task: str, event_listener: Optional[Callable] = None) -> BrainResult:
        """Ejecuta una instrucción asíncrona en el agente Hermes subyacente de forma serializada."""
        if not self.is_available():
            return BrainResult("", success=False, error="Hermes Core no está disponible.")

        started_at = time.time()

        def _execute_sync() -> BrainResult:
            tid = threading.get_ident()
            if event_listener:
                with self._listeners_lock:
                    self._thread_listeners[tid] = event_listener
            try:
                # run_conversation conserva metadatos de interrupcion que chat() descarta.
                result = self.hermes_agent.run_conversation(task)
                if isinstance(result, dict):
                    text_result = result.get("final_response") or ""
                    interrupted = bool(result.get("interrupted"))
                    failed = bool(result.get("failed"))
                    completed = bool(result.get("completed"))
                    reason = (
                        result.get("error")
                        or result.get("turn_exit_reason")
                        or ("Interrumpido" if interrupted else None)
                    )
                    success = completed and not failed and not interrupted and bool(text_result)
                    return BrainResult(
                        text=text_result,
                        raw_text=text_result,
                        success=success,
                        error=None if success else (reason or "Sin resultado textual"),
                        interrupted=interrupted,
                        started_at=started_at,
                        finished_at=time.time()
                    )

                text_result = result or ""
                return BrainResult(
                    text=text_result,
                    success=bool(text_result),
                    error="Sin resultado textual" if not text_result else None,
                    interrupted=False,
                    started_at=started_at,
                    finished_at=time.time()
                )
            except Exception as e:
                return BrainResult(
                    text="",
                    success=False,
                    error=str(e),
                    started_at=started_at,
                    finished_at=time.time()
                )
            finally:
                if event_listener:
                    with self._listeners_lock:
                        self._thread_listeners.pop(tid, None)

        # Usar to_thread dentro del lock serializado
        async with self._get_lock():
            return await asyncio.to_thread(_execute_sync)

    def is_available(self) -> bool:
        """Retorna True si el agente se inicializó correctamente."""
        return self.hermes_agent is not None

    async def review_session_memory(
        self,
        messages: list[dict[str, Any]],
        review_skills: bool = False,
    ) -> BrainResult:
        """Dispara la revision de memoria de Hermes para una sesion de voz cerrada."""
        if not self.is_available():
            return BrainResult("", success=False, error="Hermes Core no esta disponible.")

        def _execute_sync() -> BrainResult:
            try:
                if hasattr(self.hermes_agent, "_spawn_background_review"):
                    self.hermes_agent._spawn_background_review(
                        list(messages or []),
                        review_memory=True,
                        review_skills=review_skills,
                    )
                    return BrainResult("Revision de memoria de sesion encolada.", success=True)

                if hasattr(self.hermes_agent, "commit_memory_session"):
                    self.hermes_agent.commit_memory_session(list(messages or []))
                    return BrainResult("Sesion de memoria consolidada.", success=True)

                return BrainResult("", success=False, error="Hermes no expone revision de memoria.")
            except Exception as exc:
                return BrainResult("", success=False, error=str(exc))

        async with self._get_lock():
            return await asyncio.to_thread(_execute_sync)

    def interrupt(self, reason: str = "Usuario interrumpió la tarea.") -> None:
        """Solicita cancelación cooperativa a Hermes."""
        if self.is_available():
            # Inyectar el método si es que run_agent.py lo expone
            if hasattr(self.hermes_agent, "interrupt"):
                self.hermes_agent.interrupt(reason)
            else:
                print(f"[HermesAdapter] Advertencia: AIAgent no expone interrupt()")
