import os
import re
import time
import unicodedata
from dataclasses import dataclass


MUSIC_TOOL_INTENT_WINDOW_SECONDS = float(os.getenv("MUSIC_TOOL_INTENT_WINDOW_SECONDS", "15.0"))
COGNITIVE_UTTERANCE_RETENTION_SECONDS = float(os.getenv("COGNITIVE_UTTERANCE_RETENTION_SECONDS", "30.0"))


def _read_bool_env(name: str, default: bool = True) -> bool:
    fallback = "1" if default else "0"
    return os.getenv(name, fallback).strip().lower() not in {"0", "false", "no", "off"}


MUSIC_TOOL_INTENT_TERMS = (
    "reproduce",
    "reproducir",
    "pon",
    "ponme",
    "ponelo",
    "ponla",
    "toca",
    "coloca",
    "quiero escuchar",
    "escuchar",
    "abre youtube",
    "youtube",
    "musica",
    "cancion",
    "video",
    "play",
)

MUSIC_TOOL_NEGATIVE_TERMS = (
    "no reproduzcas",
    "no pongas",
    "no quiero escuchar",
    "no abras youtube",
    "no musica",
    "no pongas musica",
    "don't play",
    "do not play",
)

CANCEL_TOOL_INTENT_TERMS = (
    "cancela",
    "cancelar",
    "deten",
    "detener",
    "detente",
    "para",
    "parar",
    "interrumpe",
    "interrumpir",
    "stop",
    "olvidalo",
    "dejalo",
    "ya no",
    "no hagas nada",
    "basta",
    "corta",
)

CANCEL_TOOL_NEGATIVE_TERMS = (
    "no canceles",
    "no detengas",
    "no pares",
    "no interrumpas",
    "don't stop",
    "do not stop",
)

TASK_STATUS_PHRASE_INTENTS = (
    "como va",
    "como va la tarea",
    "como va eso",
    "estado de la tarea",
    "estado de tareas",
    "que estas haciendo",
    "sigues trabajando",
    "sigue trabajando",
    "ya terminaste",
    "ya termino",
    "terminaste",
    "termino la tarea",
    "que hay en cola",
    "tareas pendientes",
    "hay algo pendiente",
)

TODAY_SUMMARY_PHRASE_INTENTS = (
    "que tenemos hoy",
    "que tengo hoy",
    "que hay hoy",
    "que toca hoy",
    "agenda de hoy",
    "mi agenda de hoy",
    "calendario de hoy",
    "pendientes de hoy",
    "tareas de hoy",
    "que tenemos para hoy",
    "que tengo para hoy",
)

TODAY_SUMMARY_EXTERNAL_TERMS = (
    "noticia",
    "noticias",
    "internet",
    "web",
    "precio",
    "precios",
    "clima",
)

HERMES_INTENT_TERMS = (
    "analiza",
    "analizar",
    "investiga",
    "investigar",
    "busca",
    "buscar",
    "consulta",
    "consultar",
    "noticia",
    "noticias",
    "internet",
    "web",
    "actual",
    "precio",
    "precios",
    "archivo",
    "archivos",
    "carpeta",
    "carpetas",
    "documento",
    "documentos",
    "ppt",
    "pptx",
    "powerpoint",
    "presentacion",
    "presentaciones",
    "diapositiva",
    "diapositivas",
    "slides",
    "slide",
    "docx",
    "word",
    "xlsx",
    "excel",
    "pdf",
    "csv",
    "informe",
    "report",
    "reporte",
    "tabla",
    "grafico",
    "grafica",
    "codigo",
    "programa",
    "script",
    "terminal",
    "ejecuta",
    "ejecutar",
    "crea",
    "crear",
    "edita",
    "editar",
    "lee",
    "leer",
    "guarda",
    "guardar",
    "descarga",
    "descargar",
    "resume",
    "resumir",
    "resumen",
    "compara",
    "comparar",
    "planifica",
    "planificar",
    "tarea",
    "tareas",
    "proyecto",
    "proyectos",
    "recuerda",
    "recordar",
    "memoria",
    "memoriza",
    "preferencia",
    "preferencias",
    "nombre",
    "personalidad",
    "aprende",
    "aprender",
    "aprendido",
    "whatsapp",
    "correo",
    "agenda",
    "calendario",
    "mcp",
    "servidor mcp",
    "github",
    "postgres",
    "mysql",
    "base de datos",
    "database",
    "notion",
    "linear",
    "jira",
    "pantalla",
    "captura",
    "screenshot",
    "escritorio",
    "imagen",
    "imagenes",
    "video",
    "videos",
    "capacidades",
    "habilidades",
    "escribe",
    "escribir",
    "corrige",
    "corregir",
    "instala",
    "instalar",
    "mira",
    "mirar",
    "inspecciona",
    "inspeccionar",
    "automatiza",
    "automatizar",
    "depura",
    "depurar",
    "debug",
    "debuggear",
    "test",
    "testear",
    "prueba",
    "probar",
    "compila",
    "compilar",
    "refactoriza",
    "refactorizar",
    "docker",
    "git",
    "commit",
    "push",
    "pull",
    "branch",
    "servidor",
    "api",
    "endpoint",
    "sql",
    "query",
    "blender",
    "render",
    "renderizar",
    "proceso",
    "procesos",
    "log",
    "logs",
    "error",
    "errores",
    "bug",
    "bugs",
    "problema",
    "soluciona",
    "solucionar",
)

HERMES_PHRASE_INTENTS = (
    "como me llamo",
    "que sabes de mi",
    "que recuerdas",
    "te acuerdas",
    "lo que te dije",
    "mis preferencias",
    "mi nombre",
    "mi personalidad",
    "que puedes hacer",
    "que sabes hacer",
    "cuales son tus capacidades",
    "cuales son tus habilidades",
    "que herramientas tienes",
    "como funcionas",
)

SIMPLE_LIVE_ONLY_TERMS = (
    "hola",
    "buenas",
    "gracias",
    "ok",
    "okay",
    "vale",
    "listo",
    "adios",
    "chao",
)


@dataclass(frozen=True)
class ToolDecision:
    allowed: bool
    status: str
    message: str
    reason: str

    @classmethod
    def allow(cls, reason: str = "allowed") -> "ToolDecision":
        return cls(True, "aceptado", "", reason)

    @classmethod
    def reject(cls, status: str, message: str, reason: str) -> "ToolDecision":
        return cls(False, status, message, reason)


class CognitivePolicy:
    """Autoridad local para validar intenciones antes de ejecutar herramientas Live."""

    def __init__(
        self,
        music_intent_window_seconds: float = MUSIC_TOOL_INTENT_WINDOW_SECONDS,
        utterance_retention_seconds: float = COGNITIVE_UTTERANCE_RETENTION_SECONDS,
    ):
        self.music_intent_window_seconds = music_intent_window_seconds
        self.utterance_retention_seconds = max(utterance_retention_seconds, music_intent_window_seconds)
        self._recent_user_utterances: list[tuple[float, str]] = []

    @staticmethod
    def normalize_for_intent(text: str) -> str:
        text = unicodedata.normalize("NFKD", text or "")
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = re.sub(r"[^a-zA-Z0-9\s']", " ", text.lower())
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _contains_term(normalized_text: str, terms: tuple[str, ...]) -> bool:
        tokens = set(normalized_text.split())
        for term in terms:
            normalized_term = CognitivePolicy.normalize_for_intent(term)
            if not normalized_term:
                continue
            if " " in normalized_term:
                if normalized_term in normalized_text:
                    return True
            elif normalized_term in tokens:
                return True
        return False

    def record_user_utterance(self, text: str, now: float | None = None) -> None:
        text = (text or "").strip()
        if not text:
            return
        now = time.monotonic() if now is None else now
        self._recent_user_utterances.append((now, text))
        cutoff = now - self.utterance_retention_seconds
        self._recent_user_utterances = [
            item for item in self._recent_user_utterances[-12:]
            if item[0] >= cutoff
        ]

    def recent_user_text(self, window_seconds: float, now: float | None = None) -> str:
        now = time.monotonic() if now is None else now
        recent = [
            text for ts, text in self._recent_user_utterances
            if now - ts <= window_seconds
        ]
        return " ".join(recent)

    def has_explicit_music_request(self, song: str = "") -> bool:
        normalized = self.normalize_for_intent(
            self.recent_user_text(self.music_intent_window_seconds)
        )
        if not normalized:
            if self._recent_user_utterances:
                return False
            # Si no hay texto reciente ni historial previo, permitir si el modelo generó una canción específica
            return bool(song and song.lower() not in {"musica", "musica variada", "cancion", "algo"})

        if self._contains_term(normalized, MUSIC_TOOL_NEGATIVE_TERMS):
            return False

        # Si el usuario mencionó cualquier término o nombre de canción
        if song and self.normalize_for_intent(song) in normalized:
            return True
        return self._contains_term(normalized, MUSIC_TOOL_INTENT_TERMS) or len(normalized.split()) >= 2

    @staticmethod
    def music_tool_enabled() -> bool:
        return _read_bool_env("ENABLE_MUSIC_TOOL", True)

    @staticmethod
    def strict_hermes_intent_gate_enabled() -> bool:
        return _read_bool_env("STRICT_HERMES_INTENT_GATE", False)

    def has_explicit_cancel_request(self) -> bool:
        normalized = self.normalize_for_intent(
            self.recent_user_text(max(8.0, self.music_intent_window_seconds))
        )
        if not normalized:
            return True
        if self._contains_term(normalized, CANCEL_TOOL_NEGATIVE_TERMS):
            return False
        return (
            self._contains_term(normalized, CANCEL_TOOL_INTENT_TERMS)
            or "cancel" in normalized
            or "para" in normalized
            or "stop" in normalized
            or "dejalo" in normalized
            or "olvidalo" in normalized
            or "ya no" in normalized
        )

    def has_explicit_task_status_request(self) -> bool:
        normalized = self.normalize_for_intent(
            self.recent_user_text(self.utterance_retention_seconds)
        )
        if not normalized:
            return False
        return any(phrase in normalized for phrase in TASK_STATUS_PHRASE_INTENTS)

    def has_explicit_today_summary_request(self) -> bool:
        normalized = self.normalize_for_intent(
            self.recent_user_text(self.utterance_retention_seconds)
        )
        if not normalized:
            return False
        if self._contains_term(normalized, TODAY_SUMMARY_EXTERNAL_TERMS):
            return False
        return any(phrase in normalized for phrase in TODAY_SUMMARY_PHRASE_INTENTS)

    def has_explicit_hermes_request(self, prompt: str = "") -> bool:
        recent_text = self.recent_user_text(self.utterance_retention_seconds)
        normalized_recent = self.normalize_for_intent(recent_text)
        normalized_prompt = self.normalize_for_intent(prompt)

        # Evaluar texto reciente de voz si está disponible
        if normalized_recent:
            if normalized_recent in SIMPLE_LIVE_ONLY_TERMS:
                return False
            if self._contains_term(normalized_recent, HERMES_INTENT_TERMS):
                return True
            if not self.music_tool_enabled() and self._contains_term(normalized_recent, MUSIC_TOOL_INTENT_TERMS):
                if not self._contains_term(normalized_recent, MUSIC_TOOL_NEGATIVE_TERMS):
                    return True
            if any(phrase in normalized_recent for phrase in HERMES_PHRASE_INTENTS):
                return True

        # Fallback al prompt explícito generado por el modelo
        if normalized_prompt:
            if normalized_prompt in SIMPLE_LIVE_ONLY_TERMS:
                return False
            if self._contains_term(normalized_prompt, HERMES_INTENT_TERMS):
                return True
            if any(phrase in normalized_prompt for phrase in HERMES_PHRASE_INTENTS):
                return True
            if len(normalized_prompt.split()) >= 3:
                return True

        return False

    def evaluate_tool_call(
        self,
        name: str,
        args: dict | None = None,
        has_recent_voice: bool = True,
    ) -> ToolDecision:
        if not has_recent_voice:
            return ToolDecision.reject(
                "ignorado",
                "No detecte una orden de voz reciente, asi que no inicie ninguna tarea.",
                "sin_voz_reciente",
            )

        if name == "reproducir_musica_youtube":
            song = str((args or {}).get("cancion", ""))
            if not self.music_tool_enabled():
                return ToolDecision.reject(
                    "ignorado",
                    "La herramienta directa de YouTube esta desactivada. Responde conversacionalmente por voz.",
                    "musica_tool_desactivada",
                )
            if not self.has_explicit_music_request(song):
                return ToolDecision.reject(
                    "ignorado",
                    "No se detectó una orden explícita para reproducir música en este turno. Si el usuario solo saludó o te habló, respóndele amablemente por voz.",
                    "musica_sin_intencion_explicita",
                )
            return ToolDecision.allow("musica_confirmada")

        if name == "cancelar_tarea_hermes":
            if not self.has_explicit_cancel_request():
                return ToolDecision.reject(
                    "ignorado",
                    "No detecte una orden explicita para cancelar la tarea de fondo.",
                    "cancelacion_sin_intencion_explicita",
                )
            return ToolDecision.allow("cancelacion_confirmada")

        if name == "consultar_estado_tareas":
            return ToolDecision.allow("estado_tareas_confirmado")

        if name == "consultar_resumen_hoy":
            return ToolDecision.allow("resumen_hoy_confirmado")

        if name == "guardar_memoria_usuario":
            texto = str((args or {}).get("contenido") or (args or {}).get("texto") or "").strip()
            if not texto:
                return ToolDecision.reject(
                    "ignorado",
                    "No hay texto para registrar en la memoria persistente.",
                    "memoria_texto_vacio",
                )
            if not has_recent_voice:
                return ToolDecision.reject(
                    "ignorado",
                    "No se puede guardar memoria de usuario sin intervencion de voz reciente.",
                    "memoria_sin_voz_reciente",
                )
            return ToolDecision.allow("memoria_usuario_confirmada")

        if name == "capturar_pantalla":
            return ToolDecision.allow("captura_pantalla_confirmada")

        if name == "ejecutar_hermes_core":
            prompt = str((args or {}).get("prompt", ""))
            normalized_recent = self.normalize_for_intent(
                self.recent_user_text(self.utterance_retention_seconds)
            )
            normalized_prompt = self.normalize_for_intent(prompt)

            if not normalized_prompt:
                return ToolDecision.reject(
                    "ignorado",
                    "No llego una instruccion util para enviar al cerebro principal.",
                    "prompt_vacio",
                )

            if (
                not self.music_tool_enabled()
                and self._contains_term(normalized_recent, MUSIC_TOOL_NEGATIVE_TERMS)
                and self._contains_term(normalized_prompt, MUSIC_TOOL_INTENT_TERMS)
            ):
                return ToolDecision.reject(
                    "ignorado",
                    "El usuario nego la reproduccion de musica; no se delego esa accion.",
                    "musica_negada",
                )

            if self.has_explicit_today_summary_request():
                return ToolDecision.reject(
                    "ignorado",
                    "La pregunta sobre que hay hoy se resuelve con estado local, no con el cerebro principal.",
                    "resumen_hoy_debe_ser_local",
                )

            if not self.strict_hermes_intent_gate_enabled():
                return ToolDecision.allow("delegacion_hermes")

            if not self.has_explicit_hermes_request(prompt):
                return ToolDecision.reject(
                    "ignorado",
                    "No detecte una tarea compleja, memoria o accion explicita para delegar al cerebro principal.",
                    "hermes_sin_intencion_explicita",
                )
            return ToolDecision.allow("delegacion_hermes")

        return ToolDecision.reject(
            "rechazado",
            "Esa herramienta no esta habilitada por la politica cognitiva.",
            "herramienta_desconocida",
        )
