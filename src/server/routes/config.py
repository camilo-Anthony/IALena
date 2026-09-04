import os
import re
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.server.security import mask_sensitive_config
from src.server.kernel_bridge import append_log

router = APIRouter(prefix="/config", tags=["Config"])

# Campos permitidos en POST /config — lista explícita por seguridad
_ALLOWED_FIELDS = {
    "MODEL_LIVE",
    "MODEL_BRAIN",
    "MODEL_BRAIN_FAST",
    "VOICE_NAME",
    "ASSISTANT_NAME",
    "USER_NAME",
    "FAST_BRAIN_TIMEOUT_SECONDS",
    "FAST_BRAIN_MAX_PARALLEL",
    "LIVE_VAD_SILENCE_DURATION_MS",
    "LIVE_VAD_PREFIX_PADDING_MS",
    "LIVE_VAD_START_SENSITIVITY",
    "LIVE_VAD_END_SENSITIVITY",
    "LIVE_ACTIVE_SESSION_CONTEXT_MAX_CHARS",
    "MIC_NOISE_GATE_ENABLED",
    "MIC_GAIN",
    "ENABLE_MUSIC_TOOL",
    "STRICT_HERMES_INTENT_GATE",
    "ACTIVATION_IDLE_SLEEP_SECONDS",
    "DAILY_BUDGET",
    "MONTHLY_BUDGET",
    "LANGUAGE",
    "LOG_LEVEL",
    "WAKE_WORD_ENABLED",
    "WAKE_WORD_MODEL",
    "WAKE_WORD_THRESHOLD",
    "WAKE_WORD_CONSECUTIVE_FRAMES",
    "WAKE_WORD_PRE_ROLL_MS",
    "WAKE_WORD_COOLDOWN_SECONDS",
    "RESULT_DELIVERY_IDLE_SECONDS",
    "RESULT_DELIVERY_POLL_SECONDS",
    "RESULT_DELIVERY_MAX_WAIT_SECONDS",
    "HERMES_PLATFORM",
    "HERMES_ENABLED_TOOLSETS",
    "HERMES_DISABLED_TOOLSETS",
    "HERMES_LIVE_MEMORY_MAX_CHARS",
    "HERMES_LIVE_IDENTITY_MAX_CHARS",
    "HERMES_LIVE_AGENT_MEMORY_MAX_CHARS",
    "HERMES_LIVE_SKILLS_MAX",
    "HERMES_SLOW_TIMEOUT_SECONDS",
    "HERMES_SKIP_MEMORY",
    "HERMES_LOAD_SOUL_IDENTITY",
    "HERMES_SKIP_CONTEXT_FILES",
    "HERMES_PASS_SESSION_ID",
    # Keys del pool Hermes (1-20)
    *[f"HERMES_API_KEY_{i}" for i in range(1, 21)],
    # Keys principales
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
}


def _locate_env_file() -> Path:
    """Busca el .env desde la raíz del proyecto."""
    # Subimos desde src/server/routes hasta la raíz
    here = Path(__file__).resolve()
    for parent in [here.parent, here.parent.parent, here.parent.parent.parent,
                   here.parent.parent.parent.parent]:
        candidate = parent / ".env"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No se encontró el archivo .env")


def _update_env_file(env_path: Path, updates: dict[str, str]) -> None:
    """
    Actualiza variables en el .env in-place.
    Si la variable existe, la reemplaza. Si no, la agrega al final.
    """
    text = env_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    updated_keys: set[str] = set()

    new_lines = []
    for line in lines:
        matched = False
        for key, value in updates.items():
            # Buscar línea con KEY= o KEY =
            pattern = rf"^\s*{re.escape(key)}\s*="
            if re.match(pattern, line):
                new_lines.append(f"{key}={value}\n")
                updated_keys.add(key)
                matched = True
                break
        if not matched:
            new_lines.append(line)

    # Agregar claves que no existían en el .env
    for key, value in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}\n")

    env_path.write_text("".join(new_lines), encoding="utf-8")


@router.get("")
def read_config():
    """Retorna la configuración actual enmascarada (keys nunca completas)."""
    cfg: dict[str, str | None] = {
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
        "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"),
        "MODEL_LIVE": os.getenv("MODEL_LIVE", "gemini-3.1-flash-live-preview"),
        "MODEL_BRAIN": os.getenv("MODEL_BRAIN", "gemini-3.1-flash-lite"),
        "MODEL_BRAIN_FAST": os.getenv("MODEL_BRAIN_FAST", "gemini-3.1-flash-lite"),
        "ASSISTANT_NAME": os.getenv("ASSISTANT_NAME", "JARVIS"),
        "USER_NAME": os.getenv("USER_NAME", "Señor"),
        "VOICE_NAME": os.getenv("VOICE_NAME", "Aoede"),
        "FAST_BRAIN_TIMEOUT_SECONDS": os.getenv("FAST_BRAIN_TIMEOUT_SECONDS", "30"),
        "FAST_BRAIN_MAX_PARALLEL": os.getenv("FAST_BRAIN_MAX_PARALLEL", "3"),
        "LIVE_VAD_SILENCE_DURATION_MS": os.getenv("LIVE_VAD_SILENCE_DURATION_MS", "1400"),
        "LIVE_VAD_PREFIX_PADDING_MS": os.getenv("LIVE_VAD_PREFIX_PADDING_MS", "300"),
        "LIVE_VAD_START_SENSITIVITY": os.getenv("LIVE_VAD_START_SENSITIVITY", "HIGH"),
        "LIVE_VAD_END_SENSITIVITY": os.getenv("LIVE_VAD_END_SENSITIVITY", "LOW"),
        "ENABLE_MUSIC_TOOL": os.getenv("ENABLE_MUSIC_TOOL", "0"),
        "MIC_NOISE_GATE_ENABLED": os.getenv("MIC_NOISE_GATE_ENABLED", "0"),
        "HERMES_PLATFORM": os.getenv("HERMES_PLATFORM", ""),
        "HERMES_ENABLED_TOOLSETS": os.getenv("HERMES_ENABLED_TOOLSETS", ""),
        "HERMES_DISABLED_TOOLSETS": os.getenv("HERMES_DISABLED_TOOLSETS", ""),
    }
    # Pool de keys Hermes
    for i in range(1, 21):
        key = f"HERMES_API_KEY_{i}"
        val = os.getenv(key)
        if val:
            cfg[key] = val
    return mask_sensitive_config(cfg)


class ConfigUpdate(BaseModel):
    updates: dict[str, str]


@router.post("")
def write_config(body: ConfigUpdate):
    """
    Actualiza variables de configuración permitidas en el .env.
    Las API keys se aceptan pero nunca se loggean completas.
    Campos desconocidos son rechazados con 422.
    """
    # Validar que todos los campos sean permitidos
    unknown = set(body.updates.keys()) - _ALLOWED_FIELDS
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Campos no permitidos: {', '.join(sorted(unknown))}",
        )

    if not body.updates:
        raise HTTPException(status_code=400, detail="No se proporcionaron cambios")

    try:
        env_path = _locate_env_file()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Aplicar cambios en memoria de proceso también
    for key, value in body.updates.items():
        os.environ[key] = value

    # Persistir en .env
    _update_env_file(env_path, body.updates)

    # Log seguro: enmascara keys sensibles
    safe_keys = []
    for key in body.updates:
        if "KEY" in key or "TOKEN" in key:
            safe_keys.append(f"{key}=****")
        else:
            safe_keys.append(f"{key}={body.updates[key]}")
    append_log("INFO", f"Config actualizada: {', '.join(safe_keys)}", source="api")

    return {
        "status": "ok",
        "updated_keys": list(body.updates.keys()),
        "message": f"{len(body.updates)} campo(s) actualizados correctamente",
    }
