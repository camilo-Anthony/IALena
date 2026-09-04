import os
from typing import Callable
from google.genai import types

HERMES_LIVE_MEMORY_MAX_CHARS = int(os.getenv("HERMES_LIVE_MEMORY_MAX_CHARS", "4000"))
HERMES_LIVE_IDENTITY_MAX_CHARS = int(os.getenv("HERMES_LIVE_IDENTITY_MAX_CHARS", "1800"))
HERMES_LIVE_AGENT_MEMORY_MAX_CHARS = int(os.getenv("HERMES_LIVE_AGENT_MEMORY_MAX_CHARS", "2200"))
HERMES_LIVE_SKILLS_MAX = int(os.getenv("HERMES_LIVE_SKILLS_MAX", "40"))
HERMES_LIVE_SKILL_DESC_MAX_CHARS = int(os.getenv("HERMES_LIVE_SKILL_DESC_MAX_CHARS", "220"))
LIVE_ACTIVE_SESSION_CONTEXT_MAX_CHARS = int(os.getenv("LIVE_ACTIVE_SESSION_CONTEXT_MAX_CHARS", "1800"))
LIVE_VAD_SILENCE_DURATION_MS = int(os.getenv("LIVE_VAD_SILENCE_DURATION_MS", "1400"))
LIVE_VAD_PREFIX_PADDING_MS = int(os.getenv("LIVE_VAD_PREFIX_PADDING_MS", "300"))
LIVE_VAD_START_SENSITIVITY = os.getenv("LIVE_VAD_START_SENSITIVITY", "HIGH").strip().upper()
LIVE_VAD_END_SENSITIVITY = os.getenv("LIVE_VAD_END_SENSITIVITY", "LOW").strip().upper()


def _read_bool_env(name: str, default: bool = True) -> bool:
    fallback = "1" if default else "0"
    return os.getenv(name, fallback).strip().lower() not in {"0", "false", "no", "off"}


class ContextManager:
    """Maneja la memoria, identidad y configuración del contexto para JARVIS."""

    def __init__(
        self,
        bot_name: str,
        user_name: str,
        voice_name: str,
        get_hermes_home_fn=None,
        get_active_session_context_fn: Callable[[], str] | None = None,
    ):
        self.bot_name = bot_name
        self.user_name = user_name
        self.voice_name = voice_name
        self.get_hermes_home = get_hermes_home_fn
        self.get_active_session_context = get_active_session_context_fn
        self.short_term_memory = []

    @staticmethod
    def _limit_text(text: str, max_chars: int) -> str:
        text = (text or "").strip()
        if max_chars <= 0 or len(text) <= max_chars:
            return text
        return text[-max_chars:].strip()

    def _read_context_file(self, path: str, max_chars: int, label: str) -> str:
        if not os.path.exists(path):
            return ""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = self._limit_text(f.read(), max_chars)
            return self._sanitize_context_text(content, label)
        except Exception as exc:
            print(f"[ContextManager] Error leyendo {label}: {exc}")
            return ""

    @staticmethod
    def _sanitize_context_text(text: str, label: str) -> str:
        text = (text or "").strip()
        if not text:
            return ""
        try:
            from tools.threat_patterns import scan_for_threats  # type: ignore

            findings = scan_for_threats(text, scope="strict")
            if findings:
                return (
                    f"[BLOQUEADO: {label} contiene patrones de prompt injection "
                    f"({', '.join(findings)}). No se inyecto en Live.]"
                )
        except Exception:
            pass
        return text

    def _load_skill_description(self, skill_dir: str) -> str:
        description_path = os.path.join(skill_dir, "DESCRIPTION.md")
        description = self._read_context_file(
            description_path,
            HERMES_LIVE_SKILL_DESC_MAX_CHARS,
            f"{os.path.basename(skill_dir)}/DESCRIPTION.md",
        )
        if description:
            return " ".join(description.split())

        skill_path = os.path.join(skill_dir, "SKILL.md")
        if not os.path.exists(skill_path):
            return ""
        try:
            with open(skill_path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
        except Exception as exc:
            print(f"[ContextManager] Error leyendo skill {skill_dir}: {exc}")
            return ""

        for line in lines[:40]:
            stripped = line.strip()
            if stripped.lower().startswith("description:"):
                value = stripped.split(":", 1)[1].strip().strip("\"'")
                return self._limit_text(value, HERMES_LIVE_SKILL_DESC_MAX_CHARS)

        body = "\n".join(line for line in lines if line.strip() and line.strip() != "---")
        return self._limit_text(body, HERMES_LIVE_SKILL_DESC_MAX_CHARS)

    def _load_hermes_context(self) -> str:
        """Carga la memoria a largo plazo y las habilidades de Hermes."""
        context = ""
        if self.get_hermes_home:
            try:
                hermes_home = str(self.get_hermes_home())
                soul_md_path = os.path.join(hermes_home, "SOUL.md")
                soul_identity = self._read_context_file(
                    soul_md_path,
                    HERMES_LIVE_IDENTITY_MAX_CHARS,
                    "SOUL.md",
                )
                if soul_identity:
                    context += f"\n- Identidad base del agente:\n{soul_identity}\n"

                # 1. Cargar memoria a largo plazo (USER.md)
                user_md_path = os.path.join(hermes_home, "memories", "USER.md")
                user_mem = self._read_context_file(
                    user_md_path,
                    HERMES_LIVE_MEMORY_MAX_CHARS,
                    "memories/USER.md",
                )
                if user_mem:
                    context += f"\n- Perfil y preferencias del usuario:\n{user_mem}\n"

                memory_md_path = os.path.join(hermes_home, "memories", "MEMORY.md")
                agent_mem = self._read_context_file(
                    memory_md_path,
                    HERMES_LIVE_AGENT_MEMORY_MAX_CHARS,
                    "memories/MEMORY.md",
                )
                if agent_mem:
                    context += f"\n- Memoria operativa del agente:\n{agent_mem}\n"

                # 2. Cargar lista de habilidades aprendidas
                skills_dir = os.path.join(hermes_home, "skills")
                if os.path.isdir(skills_dir):
                    skills = os.listdir(skills_dir)
                    if skills:
                        skill_names = [s for s in skills if os.path.isdir(os.path.join(skills_dir, s))]
                        if skill_names:
                            context += f"\n- Habilidades que has aprendido (puedes ejecutarlas vía ejecutar_hermes_core):\n"
                            for name in sorted(skill_names)[:HERMES_LIVE_SKILLS_MAX]:
                                description = self._load_skill_description(os.path.join(skills_dir, name))
                                if description:
                                    context += f"  * {name}: {description}\n"
                                else:
                                    context += f"  * {name}\n"
            except Exception as exc:
                print(f"[ContextManager] Error cargando contexto de Hermes: {exc}")
        return context

    def set_active_session_context_provider(self, provider: Callable[[], str] | None) -> None:
        self.get_active_session_context = provider

    def _load_active_session_context(self) -> str:
        if not self.get_active_session_context:
            return ""
        try:
            return self._limit_text(
                self.get_active_session_context(),
                LIVE_ACTIVE_SESSION_CONTEXT_MAX_CHARS,
            )
        except Exception as exc:
            print(f"[ContextManager] Error cargando contexto activo de sesion: {exc}")
            return ""

    def get_base_instruction(self) -> str:
        """Construye las instrucciones base y reglas de comportamiento."""
        hermes_context = self._load_hermes_context()
        active_session_context = self._load_active_session_context()
        music_instruction = self._music_instruction()

        system_instruction_text = (
            f"Eres {self.bot_name}, un asistente de inteligencia artificial avanzado, sofisticado y eficiente.\n"
            f"Estás interactuando por voz en tiempo real con {self.user_name}.\n\n"
            "## PRINCIPIOS Y PROTOCOLO SPEECH-TO-SPEECH (VOZ EN TIEMPO REAL):\n"
            "- Idioma: Español. Tono elegante, conciso, proactivo y natural. Trato directo sin redundancias.\n"
            "- Conversación Fluida e Inmediata (Latencia Cero): Tu rol primordial es responder de forma hablada e instantánea (en milisegundos). "
            "Úsalo para responder preguntas simples, razonamientos, charlas, conceptos, dudas teóricas y explicaciones de código (Python, Blender, AMCP, TCP/IP, etc.) sin invocar herramientas innecesarias. "
            "TODO lo que puedas explicar verbalmente, explícalo tú mismo directamente por voz. "
            "NUNCA uses 'ejecutar_hermes_core' para investigar ni para explicar cómo se hace algo.\n"
            "- Cuándo usar 'ejecutar_hermes_core' (Solo Acciones en PC): Invoca 'ejecutar_hermes_core' ÚNICAMENTE ante órdenes imperativas de acción en el sistema (ej: 'abre Blender en mi PC', 'ejecuta el script X', 'crea el archivo Y en el disco').\n"
            "- Saludos y Wake Word: Ante saludos o preguntas casuales, responde INMEDIATAMENTE por voz con calidez (ej: 'Sí, señor', 'Hola, ¿en qué te ayudo?'). NUNCA uses herramientas ante saludos.\n"
            "- Acuse de recibo inmediato: Al invocar una herramienta pesada o delegar al cerebro principal, di SIEMPRE un acuse de recibo breve en voz alta en ese mismo turno (ej: 'Dame un momento, me encargo ahora mismo' o 'Enseguida lo preparo').\n"
            "- Control de Tareas y Cancelación: Una interrupción de voz NO significa cancelar. Solo usa 'cancelar_tarea_hermes' cuando el usuario lo pida explícitamente.\n"
            "- Estado y Consultas Locales: Usa 'consultar_estado_tareas' para saber qué se ejecuta y 'consultar_resumen_hoy' para agenda. Si el cerebro principal está ocupado, la dejara en cola.\n"
            "- NO respondas ni especules sobre el resultado de una tarea en marcha hasta que la entrega llegue.\n"
            "- No asumas que una pausa breve significa que el usuario terminó su frase; escucha atentamente.\n\n"
            "## IDENTIDAD, MEMORIA Y APRENDIZAJE ('guardar_memoria_usuario'):\n"
            "- Si el usuario te enseña una preferencia, te corrige ('no hagas X, haz Y') o te da una regla de comportamiento, invoca 'guardar_memoria_usuario' para grabarla en tu memoria permanente (USER.md).\n"
            "- Aplica siempre tus memorias aprendidas antes de tomar decisiones en cada turno.\n\n"
            f"{music_instruction}"
        )

        if hermes_context:
            system_instruction_text += (
                "\n[DATOS INTERNOS - NO VERBALIZAR]:\n"
                "La siguiente información es tu memoria a largo plazo y preferencias del usuario. "
                "Úsala de forma proactiva y natural en la conversación. Si el usuario te pregunta por su agenda, "
                "lo que han hablado antes, o qué estás haciendo, responde usando estos datos sin mencionar archivos ni a 'Hermes'.\n"
                f"{hermes_context}"
            )
        if active_session_context:
            system_instruction_text += (
                "\n[CONTEXTO ACTIVO DE ESTA SESION - NO RESPONDER POR SI SOLO]:\n"
                "Estos son turnos recientes de la misma conversacion de voz activa. "
                "NO los trates como un mensaje nuevo, NO los respondas al iniciar o reconectar, "
                "NO ejecutes herramientas solo por este contexto. "
                "Usalos solamente para resolver referencias cuando el usuario vuelva a hablar.\n"
                f"{active_session_context}"
            )
        return system_instruction_text

    @staticmethod
    def _music_tool_enabled() -> bool:
        return _read_bool_env("ENABLE_MUSIC_TOOL", True)

    def _music_instruction(self) -> str:
        if self._music_tool_enabled():
            return (
                "## CUÁNDO USAR 'reproducir_musica_youtube':\n"
                "- Cuando el usuario pida reproducir música, canciones o videos.\n\n"
            )
        return (
            "## MÚSICA Y YOUTUBE:\n"
            "- La herramienta directa de YouTube está desactivada temporalmente.\n"
            "- Si el usuario pide reproducir música, canciones o videos, delega a 'ejecutar_hermes_core'.\n\n"
        )

    def _music_function_declarations(self) -> list[types.FunctionDeclaration]:
        if not self._music_tool_enabled():
            return []
        return [
            types.FunctionDeclaration(
                name="reproducir_musica_youtube",
                description=(
                    "Abre YouTube y reproduce una canción o video. "
                    "Úsala ÚNICAMENTE cuando el usuario ordene explícitamente escuchar música, canciones o videos en este turno exacto. "
                    "NUNCA la uses ante saludos o preguntas casuales."
                ),
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "cancion": types.Schema(type="STRING", description="Nombre de la canción o video a reproducir.")
                    },
                    required=["cancion"],
                ),
            )
        ]

    @staticmethod
    def _start_sensitivity() -> types.StartSensitivity:
        if LIVE_VAD_START_SENSITIVITY == "LOW":
            return types.StartSensitivity.START_SENSITIVITY_LOW
        return types.StartSensitivity.START_SENSITIVITY_HIGH

    @staticmethod
    def _end_sensitivity() -> types.EndSensitivity:
        if LIVE_VAD_END_SENSITIVITY == "HIGH":
            return types.EndSensitivity.END_SENSITIVITY_HIGH
        return types.EndSensitivity.END_SENSITIVITY_LOW

    def add_memory(self, text: str):
        """Agrega un turno a la memoria de corto plazo."""
        self.short_term_memory.append(text)
        if len(self.short_term_memory) > 10:
            self.short_term_memory.pop(0)

    @staticmethod
    def _inject_recent_memory_enabled() -> bool:
        return os.getenv("LIVE_INJECT_RECENT_MEMORY", "0").strip().lower() not in {"0", "false", "no", "off"}

    def get_live_config(self) -> types.LiveConnectConfig:
        """Genera la configuracion Live sin historial conversacional crudo."""
        current_instruction = self.get_base_instruction()
        inject_recent_memory = self._inject_recent_memory_enabled()

        if inject_recent_memory and self.short_term_memory:
            historial_reciente = "\n".join(self.short_term_memory)
            current_instruction += (
                "\n\n[MEMORIA RECIENTE INTERNA - SOLO REFERENCIA SILENCIOSA]:\n"
                "Las siguientes notas son contexto pasivo de continuidad. "
                "NO son un mensaje nuevo del usuario, NO son una orden pendiente y NO debes responderlas por tu cuenta. "
                "Al iniciar o reconectar una sesión Live, permanece en silencio hasta escuchar una nueva entrada de voz real del usuario. "
                "NO retomes preguntas pasadas, NO resumas historial y NO ejecutes herramientas basándote solo en esta memoria. "
                "Usa esta memoria únicamente si el usuario continúa explícitamente el tema.\n"
                f"{historial_reciente}"
            )

        return types.LiveConnectConfig(
            system_instruction=types.Content(
                parts=[types.Part(text=current_instruction)]
            ),
            tools=[types.Tool(function_declarations=[
                types.FunctionDeclaration(
                    name="ejecutar_hermes_core",
                    description=(
                        "Ejecuta tareas complejas en segundo plano (crear archivos, presentaciones, programar, terminal, web). "
                        "Úsala ÚNICAMENTE ante órdenes directas de acción. NUNCA ante saludos, preguntas casuales o dudas teóricas."
                    ),
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "prompt": types.Schema(type="STRING", description="Instrucción detallada de la tarea a ejecutar.")
                        },
                        required=["prompt"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="cancelar_tarea_hermes",
                    description="Cancela la tarea compleja de fondo que esta ejecutando Hermes cuando el usuario lo pide explicitamente.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "motivo": types.Schema(type="STRING", description="Motivo breve de la cancelacion, si el usuario lo dijo.")
                        },
                    ),
                ),
                types.FunctionDeclaration(
                    name="consultar_estado_tareas",
                    description="Consulta el estado local de tareas complejas activas o en cola sin delegar al cerebro principal.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={},
                    ),
                ),
                types.FunctionDeclaration(
                    name="consultar_resumen_hoy",
                    description="Consulta localmente que hay hoy: tareas activas, tareas en cola y agenda local configurada. No usa el cerebro principal.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={},
                    ),
                ),
                types.FunctionDeclaration(
                    name="guardar_memoria_usuario",
                    description=(
                        "Guarda de forma permanente una preferencia, regla de comportamiento, corrección o dato personal del usuario en su memoria a largo plazo (USER.md). "
                        "Úsala cuando el usuario te enseñe cómo desea que actúes, corrija un comportamiento ('no hagas X, haz Y'), "
                        "o te pida explícitamente recordar un dato o preferencia ('recuerda que...', 'me gusta...', 'cuando te pida...')."
                    ),
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "contenido": types.Schema(
                                type="STRING",
                                description="La regla, preferencia o hecho que el usuario te enseñó, redactado de forma clara y directa."
                            ),
                            "tipo": types.Schema(
                                type="STRING",
                                description="Tipo de memoria: 'regla_comportamiento', 'preferencia_personal', 'dato_usuario'.",
                                enum=["regla_comportamiento", "preferencia_personal", "dato_usuario"],
                            )
                        },
                        required=["contenido"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="capturar_pantalla",
                    description=(
                        "Captura una imagen de la pantalla del escritorio del usuario en Windows. "
                        "Úsala cuando el usuario diga 'mira mi pantalla', 'qué error tengo', 'mira lo que estoy haciendo', "
                        "'analiza esta ventana', 'revisa mi código' o cualquier referencia visual a lo que está viendo. "
                        "La imagen se enviará al cerebro principal para análisis multimodal."
                    ),
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "solo_ventana_activa": types.Schema(
                                type="BOOLEAN",
                                description="Si es True, captura solo la ventana activa en primer plano. Si es False o no se especifica, captura la pantalla completa."
                            ),
                            "consulta": types.Schema(
                                type="STRING",
                                description="La pregunta o instrucción del usuario sobre lo que ve en pantalla."
                            ),
                        },
                        required=["consulta"],
                    ),
                ),
                *self._music_function_declarations(),
            ])],
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        # Lee dinamicamente para que cambios desde el Panel tomen efecto al reconectar
                        voice_name=os.getenv("VOICE_NAME", self.voice_name)
                    )
                )
            ),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    start_of_speech_sensitivity=self._start_sensitivity(),
                    end_of_speech_sensitivity=self._end_sensitivity(),
                    prefix_padding_ms=max(0, LIVE_VAD_PREFIX_PADDING_MS),
                    silence_duration_ms=max(300, LIVE_VAD_SILENCE_DURATION_MS),
                ),
                activity_handling=types.ActivityHandling.START_OF_ACTIVITY_INTERRUPTS,
            ),
        )
