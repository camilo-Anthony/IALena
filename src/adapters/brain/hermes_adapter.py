import os
import sys
import asyncio
import time
import threading
import traceback
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
from src.kernel.capability_registry import capability_registry


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
    platform = _read_optional_env("HERMES_PLATFORM") or "cli"
    enabled_toolsets = _parse_csv_env("HERMES_ENABLED_TOOLSETS")
    disabled_toolsets = _parse_csv_env("HERMES_DISABLED_TOOLSETS")

    # Si HERMES_ENABLED_TOOLSETS no está definido en el env, usar directamente los defaults de JARVIS
    if enabled_toolsets is None:
        enabled_toolsets = [
            "web", "file", "terminal", "browser", "skills", "todo",
            "memory", "session_search", "code_execution", "delegation",
            "cronjob", "vision", "image_gen", "tts"
        ]
    if disabled_toolsets is None:
        disabled_toolsets = [
            "spotify", "discord", "whatsapp", "email", "telegram",
            "slack", "sms", "teams", "google_chat", "matrix",
            "mattermost", "signal"
        ]

    return {
        "platform": platform,
        "enabled_toolsets": enabled_toolsets,
        "disabled_toolsets": disabled_toolsets,
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


# Toolsets seguros para el carril FAST (sin efectos secundarios)
_FAST_SAFE_TOOLSETS = ["web"]
# Toolsets bloqueados en FAST aunque el env lo habilite
_FAST_BLOCKED_TOOLSETS = [
    "terminal", "file", "memory", "skills", "github",
    "spotify", "discord", "whatsapp", "email",
]
# Timeout por defecto para tareas FAST (segundos)
_FAST_DEFAULT_TIMEOUT = float(os.getenv("FAST_BRAIN_TIMEOUT_SECONDS", "60"))


class HermesAdapter(IAgentBrain):
    """Adaptador que envuelve al sistema AIAgent de Hermes para actuar como Cerebro de JARVIS.

    Soporta dos modos:
      mode='slow'  — Carril SLOW: lock serializado, herramientas completas, memoria activa.
      mode='fast'  — Carril FAST: sin lock, herramientas restringidas, timeout corto.
    """

    def __init__(self, api_keys: list, model_brain: str, mode: str = "slow"):
        self.hermes_agent = None
        self.mode = mode  # "slow" | "fast"

        # Diccionario para enrutar eventos por ID de hilo
        self._thread_listeners: Dict[int, Callable] = {}
        self._listeners_lock = threading.Lock()

        # Lock async para serializar la ejecución de Hermes SLOW por event loop
        # El modo FAST NO usa este lock (permite paralelismo real)
        self._async_locks: Dict[asyncio.AbstractEventLoop, asyncio.Lock] = {}

        if not AIAgent:
            print("[HermesAdapter] ERROR: No se encontró el módulo Hermes Agent en el path.")
            return

        try:
            # Iniciamos el proxy de llaves local (el puerto es compartido entre slow y fast)
            proxy_port = start_proxy(api_keys)
            proxy_base_url = f"http://127.0.0.1:{proxy_port}/v1/"

            if mode == "fast":
                self._init_fast_mode(proxy_base_url, model_brain)
            else:
                self._init_slow_mode(proxy_base_url, model_brain)

        except Exception as exc:
            print(f"\033[91m[HermesAdapter] Error al inicializar (mode={mode}): {exc}\033[0m")
            traceback.print_exc()

    def _init_slow_mode(self, proxy_base_url: str, model_brain: str) -> None:
        """Inicialización completa para el carril SLOW."""
        runtime_config = _read_runtime_config()
        print(
            f"\033[94m[HermesAdapter][SLOW]\033[0m Inicializando ({len(runtime_config.get('enabled_toolsets') or []) or 'default'} toolset(s))…"
        )
        print(
            "\033[94m[HermesAdapter][SLOW]\033[0m Config: "
            f"platform={runtime_config['platform'] or 'default'}, "
            f"enabled={_format_config_list(runtime_config['enabled_toolsets'])}, "
            f"disabled={_format_config_list(runtime_config['disabled_toolsets'])}, "
            f"identity={'on' if runtime_config['load_soul_identity'] else 'off'}, "
            f"memory={'off' if runtime_config['skip_memory'] else 'on'}"
        )
        agent_cls = AIAgent
        if agent_cls is None:
            raise RuntimeError("Hermes Core no está disponible (AIAgent es None).")

        self.hermes_agent = agent_cls(
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
        if hasattr(self.hermes_agent, "_skill_nudge_interval"):
            setattr(self.hermes_agent, "_skill_nudge_interval", 0)
        print("\033[94m[HermesAdapter][SLOW]\033[0m Hermes Core listo (rotación activa).")

        tools_list = self._log_available_tools()
        capability_registry.update_capabilities(
            lane="slow",
            toolsets=runtime_config["enabled_toolsets"] or [],
            tools=tools_list
        )

        enabled_str = ",".join(runtime_config["enabled_toolsets"])
        disabled_str = ",".join(runtime_config["disabled_toolsets"])
        tools_str = ",".join(tools_list) if tools_list else "ninguna"

        from src.kernel.capability_registry import TaskCapability
        active_caps = [
            cap.value for cap in TaskCapability
            if capability_registry.has_capability("slow", cap)
        ]
        caps_str = ",".join(active_caps) if active_caps else "ninguna"

        print(f"\033[94m[HermesAdapter][SLOW]\033[0m SLOW enabled_toolsets={enabled_str}")
        print(f"\033[94m[HermesAdapter][SLOW]\033[0m SLOW disabled_toolsets={disabled_str}")
        print(f"\033[94m[HermesAdapter][SLOW]\033[0m SLOW detected_tools={tools_str}")
        print(f"\033[94m[HermesAdapter][SLOW]\033[0m SLOW capabilities={caps_str}")

    def _init_fast_mode(self, proxy_base_url: str, model_brain: str) -> None:
        """Inicialización restringida para el carril FAST."""
        # El carril FAST usa un modelo configurable (puede ser más ligero)
        fast_model = os.getenv("MODEL_BRAIN_FAST", model_brain)
        print(f"\033[96m[HermesAdapter][FAST]\033[0m Inicializando con modelo={fast_model}…")
        # Toolsets: solo los seguros, siempre deshabilitamos los peligrosos
        enabled = _FAST_SAFE_TOOLSETS
        disabled = _FAST_BLOCKED_TOOLSETS
        agent_cls = AIAgent
        if agent_cls is None:
            raise RuntimeError("Hermes Core no está disponible (AIAgent es None).")

        self.hermes_agent = agent_cls(
            base_url=proxy_base_url,
            api_key="proxy-managed",
            model=fast_model,
            quiet_mode=True,
            save_trajectories=False,    # No guardar trayectorias para FAST
            enabled_toolsets=enabled,
            disabled_toolsets=disabled,
            platform=None,
            user_name=_read_optional_env("USER_NAME"),
            load_soul_identity=False,   # Sin identidad soul para FAST
            skip_context_files=True,    # Sin contexto de archivos
            skip_memory=True,           # Sin memoria persistente
            pass_session_id=False,
            tool_start_callback=self._on_tool_start,
            tool_complete_callback=self._on_tool_complete,
            status_callback=self._on_status,
        )
        if hasattr(self.hermes_agent, "_skill_nudge_interval"):
            setattr(self.hermes_agent, "_skill_nudge_interval", 0)
        print(f"\033[96m[HermesAdapter][FAST]\033[0m Listo. Toolsets: {enabled}. Timeout: {_FAST_DEFAULT_TIMEOUT}s")

        tools_list = self._log_available_tools()
        capability_registry.update_capabilities(
            lane="fast",
            toolsets=enabled,
            tools=tools_list
        )

    def _log_available_tools(self) -> list[str]:
        agent = self.hermes_agent
        tools_list = []
        if agent is not None:
            if hasattr(agent, "valid_tool_names") and agent.valid_tool_names:
                tools_list = sorted(list(agent.valid_tool_names))
            elif hasattr(agent, "tools") and agent.tools:
                tools_list = sorted([t["function"]["name"] for t in agent.tools if "function" in t])

        mode_label = self.mode.upper()
        color = "\033[94m" if self.mode == "slow" else "\033[96m"
        if tools_list:
            tools_str = ", ".join(tools_list)
            print(f"{color}[HermesAdapter][{mode_label}]\033[0m Tools activos: {tools_str}")
        else:
            print(f"{color}[HermesAdapter][{mode_label}]\033[0m No se pudo inspeccionar tools activos; usando toolsets configurados.")
        return tools_list

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
        # Purge closed event loops to prevent memory leak across test/restart cycles
        self._async_locks = {l: lock for l, lock in self._async_locks.items() if not l.is_closed()}
        if loop not in self._async_locks:
            self._async_locks[loop] = asyncio.Lock()
        return self._async_locks[loop]

    async def run_task(self, task: str, event_listener: Optional[Callable] = None) -> BrainResult:
        """Ejecuta una instrucción asincrónica en el agente Hermes subyacente.

        Modo SLOW: serializado con lock por event loop.
        Modo FAST: sin lock (paralelo), con timeout configurado.
        """
        if not self.is_available():
            return BrainResult("", success=False, error="Hermes Core no está disponible.")

        started_at = time.time()

        def _execute_sync() -> BrainResult:
            tid = threading.get_ident()
            if event_listener:
                with self._listeners_lock:
                    self._thread_listeners[tid] = event_listener
            try:
                if self.hermes_agent is None:
                    return BrainResult(
                        "",
                        success=False,
                        error="Hermes Core no está disponible (hermes_agent es None).",
                        started_at=started_at,
                        finished_at=time.time(),
                    )
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

        if self.mode == "fast":
            # FAST: sin lock serial, con timeout
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(_execute_sync),
                    timeout=_FAST_DEFAULT_TIMEOUT,
                )
            except asyncio.TimeoutError:
                return BrainResult(
                    "", success=False,
                    error=f"Timeout FAST tras {_FAST_DEFAULT_TIMEOUT}s",
                    started_at=started_at, finished_at=time.time()
                )
        else:
            # SLOW: serializado con lock por event loop
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
        agent = self.hermes_agent
        if agent is None:
            return BrainResult("", success=False, error="Hermes Core no esta disponible.")

        def _execute_sync() -> BrainResult:
            try:
                if hasattr(agent, "_spawn_background_review"):
                    agent._spawn_background_review(
                        list(messages or []),
                        review_memory=True,
                        review_skills=review_skills,
                    )
                    return BrainResult("Revision de memoria de sesion encolada.", success=True)

                if hasattr(agent, "commit_memory_session"):
                    agent.commit_memory_session(list(messages or []))
                    return BrainResult("Sesion de memoria consolidada.", success=True)

                return BrainResult("", success=False, error="Hermes no expone revision de memoria.")
            except Exception as exc:
                return BrainResult("", success=False, error=str(exc))

        async with self._get_lock():
            return await asyncio.to_thread(_execute_sync)

    def interrupt(self, reason: str = "Usuario interrumpió la tarea.") -> None:
        """Solicita cancelación cooperativa a Hermes."""
        agent = self.hermes_agent
        if agent is not None:
            # Inyectar el método si es que run_agent.py lo expone
            if hasattr(agent, "interrupt"):
                agent.interrupt(reason)
            else:
                print(f"[HermesAdapter] Advertencia: AIAgent no expone interrupt()")
