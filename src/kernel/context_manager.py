import os
from google.genai import types

class ContextManager:
    """Maneja la memoria, identidad y configuración del contexto para IALena."""

    def __init__(self, bot_name: str, user_name: str, voice_name: str, get_hermes_home_fn=None):
        self.bot_name = bot_name
        self.user_name = user_name
        self.voice_name = voice_name
        self.get_hermes_home = get_hermes_home_fn
        self.short_term_memory = []

    def _load_hermes_context(self) -> str:
        """Carga la memoria a largo plazo y las habilidades de Hermes."""
        context = ""
        if self.get_hermes_home:
            try:
                hermes_home = self.get_hermes_home()
                # 1. Cargar memoria a largo plazo (USER.md)
                user_md_path = os.path.join(hermes_home, "memories", "USER.md")
                if os.path.exists(user_md_path):
                    with open(user_md_path, "r", encoding="utf-8") as f:
                        user_mem = f.read().strip()
                        if user_mem:
                            context += f"\n- Preferencias y memoria del usuario:\n{user_mem}\n"

                # 2. Cargar lista de habilidades aprendidas
                skills_dir = os.path.join(hermes_home, "skills")
                if os.path.isdir(skills_dir):
                    skills = os.listdir(skills_dir)
                    if skills:
                        skill_names = [s for s in skills if os.path.isdir(os.path.join(skills_dir, s))]
                        if skill_names:
                            context += f"\n- Habilidades que has aprendido (puedes ejecutarlas vía ejecutar_hermes_core):\n"
                            for name in skill_names:
                                context += f"  * {name}\n"
            except Exception as exc:
                print(f"[ContextManager] Error cargando contexto de Hermes: {exc}")
        return context

    def get_base_instruction(self) -> str:
        """Construye las instrucciones base y reglas de comportamiento."""
        hermes_context = self._load_hermes_context()
        
        system_instruction_text = (
            f"Eres {self.bot_name}, un asistente de voz inteligente. "
            f"Estás hablando con {self.user_name}. Habla siempre en español, de forma concisa y natural.\n\n"

            "## CUÁNDO RESPONDER TÚ DIRECTAMENTE (sin llamar herramientas):\n"
            "- Saludos y despedidas (hola, adiós, buenas tardes)\n"
            "- Preguntas conversacionales simples (¿cómo estás?, ¿cuál es tu nombre?)\n"
            "- Matemáticas básicas o preguntas de conocimiento general muy simple\n"
            "- Confirmaciones cortas (ok, entendido, con mucho gusto)\n\n"

            "## CUÁNDO USAR 'ejecutar_hermes_core' (delegar al cerebro principal):\n"
            "- Búsquedas en internet o noticias actuales\n"
            "- Leer, crear, editar o gestionar archivos\n"
            "- Escribir o ejecutar código\n"
            "- Recordar conversaciones pasadas o preferencias del usuario\n"
            "- Tareas complejas de varios pasos\n"
            "- Cualquier cosa que requiera acceso al sistema o información actualizada\n\n"

            "## CUÁNDO USAR 'reproducir_musica_youtube':\n"
            "- Cuando el usuario pida reproducir música, canciones o videos.\n\n"

            "REGLA DE IDENTIDAD CRÍTICA: Tú eres UNA SOLA ENTIDAD. NUNCA menciones 'Hermes' ni herramientas. "
            "Di siempre 'Déjame revisarlo', 'Lo estoy procesando', 'Dame un momento', etc.\n"
        )
        
        if hermes_context:
            system_instruction_text += (
                "\nTienes acceso a tu contexto y memoria a largo plazo:\n"
                f"{hermes_context}\n"
                "Usa esta información para personalizar tus respuestas. Si el usuario te pregunta sobre "
                "datos pasados, sus preferencias, o tareas complejas que no tienes en este contexto directo, "
                "usa 'ejecutar_hermes_core' para investigarlo tú mismo (sin decirle al usuario cómo lo haces)."
            )
        return system_instruction_text

    def add_memory(self, text: str):
        """Agrega un turno a la memoria de corto plazo."""
        self.short_term_memory.append(text)
        if len(self.short_term_memory) > 10:
            self.short_term_memory.pop(0)

    def get_live_config(self) -> types.LiveConnectConfig:
        """Genera el objeto de configuración integrando la memoria reciente si existe."""
        current_instruction = self.get_base_instruction()
        
        if self.short_term_memory:
            historial_reciente = "\n".join(self.short_term_memory)
            current_instruction += (
                f"\n\n[MEMORIA DE CORTO PLAZO (Sesión Anterior)]:\n"
                f"Acabas de sufrir un micro-corte técnico, pero aquí tienes el historial reciente de lo que hablaron:\n"
                f"{historial_reciente}\n"
                f"Usa esto para retomar la conversación con absoluta fluidez sin mencionar que hubo un corte."
            )

        return types.LiveConnectConfig(
            system_instruction=types.Content(
                parts=[types.Part(text=current_instruction)]
            ),
            tools=[types.Tool(function_declarations=[
                types.FunctionDeclaration(
                    name="ejecutar_hermes_core",
                    description="Ejecuta tareas complejas: crear archivos, programar, buscar en web, usar la terminal.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "prompt": types.Schema(type="STRING", description="Instrucción detallada.")
                        },
                        required=["prompt"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="reproducir_musica_youtube",
                    description="Abre YouTube y reproduce instantáneamente una canción o video específico.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "cancion": types.Schema(type="STRING", description="Nombre de la canción o video a reproducir.")
                        },
                        required=["cancion"],
                    ),
                )
            ])],
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.voice_name)
                )
            ),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            input_audio_transcription=types.AudioTranscriptionConfig(),
        )
