"""
task_lane.py — Clasificación formal de carriles de ejecución para JARVIS.

Define tres carriles:
  LOCAL       → Acciones inmediatas sin Hermes (status, cancel, música local, ACK)
  FAST_HERMES → Tareas cortas read-only con timeout (clima, cálculos, traducciones)
  SLOW_HERMES → Tareas complejas con efectos (código, archivos, memoria, skills)
"""
import unicodedata
import re
import os
from enum import Enum
from dataclasses import dataclass, field
from typing import Set, List

from src.kernel.capability_registry import TaskCapability

class TaskLane(str, Enum):
    LOCAL = "local"
    FAST_HERMES = "fast_hermes"
    SLOW_HERMES = "slow_hermes"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

@dataclass
class LaneDecision:
    lane: TaskLane
    required_capabilities: Set[TaskCapability] = field(default_factory=set)
    risk: RiskLevel = RiskLevel.LOW
    reason: str = ""
    is_ambiguous: bool = False


# ── Herramientas siempre LOCAL ────────────────────────────────────────────────
_LOCAL_TOOLS = frozenset({
    "cancelar_tarea_hermes",
    "consultar_estado_tareas",
    "consultar_resumen_hoy",
    "reproducir_musica_youtube",
})

# ── Términos que FUERZAN SLOW sin importar el resto ───────────────────────────
_SLOW_FORCE_TERMS = (
    # Código y ejecución
    "codigo", "code", "programa", "programar", "script", "terminal",
    "ejecuta", "ejecutar", "instala", "instalar", "corre", "correr",
    "refactoriza", "refactorizar", "debuggear", "depura", "depurar",
    "compila", "compilar",
    # Archivos y documentos
    "archivo", "archivos", "carpeta", "carpetas", "directorio", "directorios",
    "crea", "crear", "escribe", "edita", "editar", "modifica", "modificar",
    "guarda", "guardar", "borra", "borrar", "elimina", "eliminar", "mueve",
    "pptx", "powerpoint", "presentacion", "diapositiva", "diapositivas",
    "docx", "word", "xlsx", "excel", "pdf", "csv",
    "informe", "reporte", "report",
    # Memoria, identidad y skills
    "recuerda", "recordar", "memoria", "memoriza", "memorizar",
    "aprende", "aprender", "aprendido", "skill", "habilidad",
    "preferencia", "preferencias", "personalidad",
    # Análisis profundo
    "analiza", "analizar", "analisis", "investigar", "investigacion",
    "proyecto", "proyectos",
    # Comunicaciones
    "whatsapp", "correo", "email", "mensaje", "mensajes",
)

# ── Términos que sugieren FAST ────────────────────────────────────────────────
_FAST_INTENT_TERMS = (
    # Consultas rápidas de información
    "clima", "temperatura", "tiempo", "lluvia", "pronostico",
    "hora", "fecha", "hoy es", "que dia",
    "precio", "cotizacion", "dolar", "euro",
    "cuanto es", "cuanto vale", "cuantos",
    # Música (cuando va a Hermes porque el tool directo está desactivado)
    "musica", "cancion", "canciones", "reproduce", "reproducir",
    "pon", "ponme", "escuchar", "play", "youtube", "spotify",
    # Cálculos y conversiones
    "convierte", "convertir", "calcula", "calcular",
    "suma", "resta", "divide", "multiplica",
    "cuanto son", "a cuanto",
    # Traducciones
    "traduce", "traducir", "traduccion", "como se dice",
    "en ingles", "en español", "en frances",
    # Explicaciones breves
    "explica", "explicar", "que es", "que significa",
    "define", "definir", "definicion",
    # Búsquedas simples (una respuesta concreta)
    "busca rapidamente", "dime rapidamente", "dame rapidamente",
    "cuál es la capital", "quien es", "cuando fue",
    "en que año",
)

_MUSIC_INTENT_TERMS = (
    "musica", "cancion", "canciones", "reproduce", "reproducir",
    "pon", "ponme", "escuchar", "play", "youtube", "spotify",
)

_MUSIC_NEGATIVE_TERMS = (
    "no pongas",
    "no reproduzcas",
    "no quiero escuchar",
    "no abras youtube",
    "no musica",
    "no pongas musica",
)


def _normalize(text: str) -> str:
    """Normaliza texto: minúsculas, sin tildes, sin signos."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9\s']", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _has_term(normalized_text: str, terms: tuple) -> bool:
    """Comprueba si alguno de los términos está presente (palabra completa o frase)."""
    tokens = set(normalized_text.split())
    for term in terms:
        n = _normalize(term)
        if not n:
            continue
        if " " in n:
            if n in normalized_text:
                return True
        elif n in tokens:
            return True
    return False


def _read_bool_env(name: str, default: bool = True) -> bool:
    fallback = "1" if default else "0"
    return os.getenv(name, fallback).strip().lower() not in {"0", "false", "no", "off"}


def _is_music_request(normalized_text: str) -> bool:
    if not normalized_text:
        return False
    if _has_term(normalized_text, _MUSIC_NEGATIVE_TERMS):
        return False
    return _has_term(normalized_text, _MUSIC_INTENT_TERMS)


def classify_tool_call(tool_name: str, args: dict | None = None) -> LaneDecision:
    """
    Clasifica una tool call en un carril de ejecución retornando un LaneDecision detallado.
    """
    # Caso 1: Herramientas siempre LOCAL
    if tool_name in _LOCAL_TOOLS:
        return LaneDecision(lane=TaskLane.LOCAL, risk=RiskLevel.LOW, reason="local_tool_override")

    if tool_name != "ejecutar_hermes_core":
        return LaneDecision(lane=TaskLane.LOCAL, risk=RiskLevel.LOW, reason="non_hermes_tool")

    prompt = str((args or {}).get("prompt", "")).strip()
    normalized = _normalize(prompt)

    # Inicialización de la decisión
    decision = LaneDecision(
        lane=TaskLane.SLOW_HERMES,
        risk=RiskLevel.LOW,
        reason="fallback_slow",
    )

    # 1. Determinar el carril base
    if _is_music_request(normalized) and not _read_bool_env("ENABLE_MUSIC_TOOL", True):
        decision.lane = TaskLane.SLOW_HERMES
        decision.reason = "music_delegated_to_slow_terminal"
        decision.required_capabilities.add(TaskCapability.TERMINAL)
    elif _has_term(normalized, _SLOW_FORCE_TERMS):
        decision.lane = TaskLane.SLOW_HERMES
        decision.reason = "slow_force_term_detected"
    elif _has_term(normalized, _FAST_INTENT_TERMS):
        decision.lane = TaskLane.FAST_HERMES
        decision.reason = "fast_intent_term_detected"
    else:
        decision.lane = TaskLane.SLOW_HERMES
        decision.reason = "default_slow_fallback"

    # 2. Identificar capacidades requeridas semánticas
    # Web / Búsqueda
    if _has_term(normalized, ("busca", "buscar", "investiga", "investigar", "clima", "temperatura", "precio", "noticias")):
        decision.required_capabilities.add(TaskCapability.WEB)

    # Archivos
    if _has_term(normalized, ("archivo", "archivos", "pptx", "docx", "xlsx", "pdf", "csv", "escribe", "crear archivo", "crea un archivo", "edita el", "borra el")):
        decision.required_capabilities.add(TaskCapability.FILE)

    # Requerimiento PPTX/Presentaciones: requiere FILE + TERMINAL
    if _has_term(normalized, ("pptx", "powerpoint", "presentacion", "presentaciones", "diapositiva", "diapositivas", "slide", "slides")):
        decision.required_capabilities.add(TaskCapability.FILE)
        decision.required_capabilities.add(TaskCapability.TERMINAL)

    # Terminal
    if _has_term(normalized, ("terminal", "comando", "ejecuta", "ejecutar", "instala", "instalar", "corre", "correr")):
        decision.required_capabilities.add(TaskCapability.TERMINAL)

    # Browser
    if _has_term(normalized, ("browser", "navegador", "navega", "navegar", "entra a la web", "descarga")):
        decision.required_capabilities.add(TaskCapability.BROWSER)

    # Memoria / Identidad
    if _has_term(normalized, ("recuerda", "recordar", "memoria", "memoriza", "preferencia", "preferencias", "personalidad", "mi nombre es", "me llamo", "llamame", "me gusta", "te acuerdas")):
        decision.required_capabilities.add(TaskCapability.MEMORY)

    # Skills
    if _has_term(normalized, ("skill", "habilidad", "habilidades")):
        decision.required_capabilities.add(TaskCapability.SKILLS)

    # Todo
    if _has_term(normalized, ("todo", "tareas pendientes", "lista de tareas")):
        decision.required_capabilities.add(TaskCapability.TODO)

    # Cronjob
    if _has_term(normalized, ("cron", "cronjob", "automatiza", "cada lunes", "programar tarea", "programa una tarea")):
        decision.required_capabilities.add(TaskCapability.CRONJOB)

    # Session Search
    if _has_term(normalized, ("historial de sesion", "busca en la sesion", "que te dije antes")):
        decision.required_capabilities.add(TaskCapability.SESSION_SEARCH)

    # Visión
    if _has_term(normalized, ("vision", "imagen", "imagenes", "pantalla", "screenshot", "captura", "mira esto")):
        decision.required_capabilities.add(TaskCapability.VISION)

    # MCP
    if _has_term(normalized, ("mcp", "herramienta mcp", "servidor mcp")):
        decision.required_capabilities.add(TaskCapability.MCP)

    # Home Assistant
    if _has_term(normalized, ("home assistant", "homeassistant", "enciende la luz", "apaga la luz", "dispositivo inteligente")):
        decision.required_capabilities.add(TaskCapability.HOME_ASSISTANT)

    # Computer Use
    if _has_term(normalized, ("computer use", "computeruse", "mouse", "mueve el raton", "haz click", "teclea")):
        decision.required_capabilities.add(TaskCapability.COMPUTER_USE)

    # Generación de Imágenes
    if _has_term(normalized, ("genera una imagen", "genera imagen", "crea una imagen", "dibuja", "dibujar", "dibujo", "ilustra", "ilustracion", "image generate", "genera foto", "genera un logo", "genera un icono")):
        decision.required_capabilities.add(TaskCapability.IMAGE_GEN)
        decision.lane = TaskLane.SLOW_HERMES
        if not decision.reason.startswith("slow_force"):
            decision.reason = "image_gen_requires_slow"

    # Text-to-Speech (generación de archivos de audio)
    if _has_term(normalized, ("lee en voz alta", "genera audio", "convierte a audio", "text to speech", "crea un audio", "graba en audio", "lee este documento", "narracion")):
        decision.required_capabilities.add(TaskCapability.TTS)
        decision.lane = TaskLane.SLOW_HERMES
        if not decision.reason.startswith("slow_force"):
            decision.reason = "tts_requires_slow"

    # 3. Clasificación de Niveles de Riesgo y Ambigüedad
    # Riesgo HIGH: borrado/destrucción, transacciones, compras, mandar correos externos
    high_keywords = ("borra", "borrar", "elimina", "eliminar", "destruye", "destruir", "compra", "comprar", "manda correo", "envia correo", "publica")
    # Riesgo MEDIUM: crear/editar archivos, programar cronjobs, instalar skills, abrir navegador
    medium_keywords = ("crea", "crear", "escribe", "escribir", "edita", "editar", "modifica", "modificar", "automatiza", "cron", "navega", "browser")

    if _has_term(normalized, high_keywords):
        decision.risk = RiskLevel.HIGH

        # Validar ambigüedad en HIGH (ej. "borra todo", "elimina" sin especificar objetivo)
        # Si el prompt no contiene una extensión común o tiene menos de 22 caracteres
        if len(prompt) < 22 or not any(ext in normalized for ext in (".txt", ".py", ".md", ".json", ".pptx", ".docx", ".pdf", "temporal", "temporales")):
            decision.is_ambiguous = True

    elif _has_term(normalized, medium_keywords):
        decision.risk = RiskLevel.MEDIUM

        # Validar ambigüedad en MEDIUM (ej. "edita el archivo" o "modifica" sin especificar qué ni cómo)
        if _has_term(normalized, ("edita", "editar", "modifica", "modificar")):
            # Si no menciona un nombre de archivo o extensión, o es sumamente corto
            if len(prompt) < 22 or not any(ext in normalized for ext in (".txt", ".py", ".md", ".json", ".pptx", ".docx", ".pdf", "archivo", "carpeta")):
                decision.is_ambiguous = True

    return decision


def lane_display_name(lane: TaskLane) -> str:
    """Nombre legible para logs."""
    return {
        TaskLane.LOCAL: "LOCAL",
        TaskLane.FAST_HERMES: "FAST",
        TaskLane.SLOW_HERMES: "SLOW",
    }.get(lane, lane.value.upper())
