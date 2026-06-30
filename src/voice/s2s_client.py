"""
Cliente S2S (Speech-to-Speech) para Jarvis usando Google Gemini Live API.

Arquitectura de doble velocidad:
  - Carril Rápido: Audio bidireccional vía Gemini Multimodal Live (baja latencia).
  - Carril Lento:  Hermes Agent Core para tareas complejas (ejecución asíncrona).

Optimización de latencia:
  - La tool call se responde INMEDIATAMENTE con un ACK para que Gemini hable.
  - Hermes trabaja en segundo plano sin bloquear el audio.
  - El resultado se inyecta como nuevo turno de cliente cuando Hermes termina.
"""
import asyncio
import sys
import os
import random
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
from google import genai
from google.genai import types

# ── Rutas ────────────────────────────────────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_HERMES_DIR = os.path.join(_PROJECT_ROOT, "Hermes-Agent")
if _HERMES_DIR not in sys.path:
    sys.path.append(_HERMES_DIR)

from src.voice.audio_capture import AudioCapture
from src.voice.audio_playback import AudioPlayback
from src.voice.key_rotator import start_proxy, PROXY_PORT

# ── Hermes Agent (importación segura) ────────────────────────────────────
try:
    from run_agent import AIAgent  # type: ignore # pyright: ignore[reportMissingImports]
    from hermes_constants import get_hermes_home
except ImportError:
    AIAgent = None
    get_hermes_home = None

# ── Configuración ────────────────────────────────────────────────────────
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")

# Carga todas las claves de Hermes definidas como HERMES_API_KEY_1, _2, _3...
# Fallback a GEMINI_API_KEY si no hay ninguna.
_raw_hermes_keys = [
    os.getenv(f"HERMES_API_KEY_{i}")
    for i in range(1, 10)
]
HERMES_API_KEYS: list[str] = [k for k in _raw_hermes_keys if k] or [GEMINI_API_KEY]

INPUT_RATE  = 16_000   # Gemini Live espera entrada a 16 kHz
OUTPUT_RATE = 24_000   # Gemini Live devuelve audio a 24 kHz
MODEL_LIVE  = "gemini-2.5-flash-native-audio-latest"
MODEL_BRAIN = "gemini-2.5-flash"       # Más capaz → menos llamadas internas por tarea
VOICE_NAME  = "Aoede"


# ═════════════════════════════════════════════════════════════════════════
class S2SClient:
    """Orquestador principal: micrófono ↔ Gemini Live ↔ altavoz ↔ Hermes."""

    def __init__(self):
        self.capture  = AudioCapture(rate=INPUT_RATE)
        self.playback = AudioPlayback(rate=OUTPUT_RATE)
        self.client   = genai.Client(
            api_key=GEMINI_API_KEY,
            http_options=types.HttpOptions(api_version="v1alpha"),
        )
        self.session    = None
        self.is_running = False

        # ── Proxy local: distribuye cada llamada LLM entre todas las keys ───
        # Hermes apunta a localhost; el proxy rota la key en cada request.
        # Una tarea de 10 llamadas usa 5 de Key-1 y 5 de Key-2 automáticamente.
        proxy_port = start_proxy(HERMES_API_KEYS)
        self._proxy_base_url = f"http://127.0.0.1:{proxy_port}/v1/"

        # ── Carril Lento: UN solo agente Hermes apuntando al proxy ─────────
        print(f"[Jarvis] Inicializando Hermes Core ({len(HERMES_API_KEYS)} clave(s) en rotación)…")
        self.hermes = None
        if AIAgent:
            try:
                self.hermes = AIAgent(
                    base_url=self._proxy_base_url,   # ← proxy local
                    api_key="proxy-managed",           # el proxy gestiona las keys
                    model=MODEL_BRAIN,
                    quiet_mode=True,
                    save_trajectories=True,
                )
                print("[Jarvis] Hermes Core listo (rotación activa).")
            except Exception as exc:
                self.hermes = None
                print(f"[ERROR] Hermes no pudo inicializarse: {exc}")
        else:
            print("[ERROR] No se encontró el módulo Hermes Agent.")

    def _load_hermes_context(self) -> str:
        """Carga la memoria a largo plazo y las habilidades de Hermes."""
        context = ""
        if get_hermes_home:
            try:
                hermes_home = get_hermes_home()
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
                print(f"[Jarvis] Error cargando contexto de Hermes: {exc}")
        return context

    # ── Conexión principal ───────────────────────────────────────────────
    async def connect(self):
        if not GEMINI_API_KEY:
            print("[ERROR] Falta GEMINI_API_KEY / GOOGLE_API_KEY en .env")
            return

        hermes_context = self._load_hermes_context()
        # Variables base de identidad
        bot_name = os.getenv("ASSISTANT_NAME", "Jarvis")
        user_name = os.getenv("USER_NAME", "Señor")

        system_instruction_text = (
            f"Eres {bot_name}, un asistente virtual de voz hiper-inteligente. "
            f"Estás hablando con tu usuario, a quien debes referirte como '{user_name}'. "
            "Habla siempre en español, de forma concisa y natural. "
            "Para tareas complejas (archivos, código, búsquedas web, ejecutar comandos en terminal "
            "o consultar recuerdos que no sepas) usa la herramienta 'ejecutar_hermes_core'. "
            "REGLA DE IDENTIDAD CRÍTICA: Tú eres UNA SOLA ENTIDAD. NUNCA menciones la palabra 'Hermes', "
            "ni digas que estás consultando a otro agente, ni hables de herramientas. "
            "Di siempre 'Déjame buscarlo', 'Lo estoy haciendo', 'Revisaré mi base de datos', etc.\n"
        )
        if hermes_context:
            system_instruction_text += (
                "\nTienes acceso a tu contexto y memoria a largo plazo:\n"
                f"{hermes_context}\n"
                "Usa esta información para personalizar tus respuestas. Si el usuario te pregunta sobre "
                "datos pasados, sus preferencias, o tareas complejas que no tienes en este contexto directo, "
                "usa 'ejecutar_hermes_core' para investigarlo tú mismo (sin decirle al usuario cómo lo haces)."
            )

        config = types.LiveConnectConfig(
            system_instruction=types.Content(
                parts=[types.Part(text=system_instruction_text)]
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
                )
            ])],
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE_NAME)
                )
            ),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )

        print(f"[Jarvis] Conectando a Gemini Live ({MODEL_LIVE})…")
        try:
            self.is_running = True
            self.capture.start()
            self.playback.start()

            async with self.client.aio.live.connect(model=MODEL_LIVE, config=config) as session:
                self.session = session
                print("[Jarvis] ¡Conexión establecida! Escuchando…")
                await asyncio.gather(
                    self._send_audio(),
                    self._receive(),
                    self._inject_context(),
                )
        except Exception as exc:
            print(f"[Jarvis] Error de conexión: {exc}")
        finally:
            self.is_running = False
            self.capture.terminate()
            self.playback.terminate()

    # ── Envío de audio (micrófono → Gemini) ──────────────────────────────
    async def _send_audio(self):
        while self.is_running and self.session:
            try:
                chunk = await self.capture.read_chunk()
                await self.session.send_realtime_input(
                    audio=types.Blob(data=chunk, mime_type=f"audio/pcm;rate={INPUT_RATE}")
                )
            except Exception as exc:
                print(f"[Jarvis] Error enviando audio: {exc}")
                break

    # ── Recepción de audio / tool calls (Gemini → altavoz) ───────────────
    async def _receive(self):
        while self.is_running and self.session:
            try:
                async for msg in self.session.receive():
                    # Audio del modelo
                    if msg.server_content:
                        sc = msg.server_content
                        if sc.model_turn:
                            for part in sc.model_turn.parts:
                                if part.inline_data:
                                    self.playback.enqueue(part.inline_data.data)
                        if sc.interrupted:
                            self.playback.flush()

                    # Llamadas a funciones
                    if msg.tool_call:
                        for fn in msg.tool_call.function_calls:
                            if fn.name == "ejecutar_hermes_core":
                                asyncio.create_task(
                                    self._run_hermes(fn.id, fn.name, fn.args.get("prompt", ""))
                                )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                print(f"[Jarvis] Error recibiendo: {exc}")
                break

    # ── Puente asíncrono con Hermes (Carril Lento) ───────────────────────
    async def _run_hermes(self, call_id: str, name: str, prompt: str):
        print(f"[Hermes] Procesando: {prompt[:80]}…")
        try:
            # ── FASE 1: ACK inmediato ──────────────────────────────────────────
            # Responder la tool call de inmediato para que Gemini empiece a hablar.
            # Gemini recibirá esto y generará audio de confirmación sin esperar.
            _ACKS = [
                "Entendido, dame un momento para revisarlo.",
                "Claro, estoy en ello. Procesando tu solicitud ahora mismo.",
                "Perfecto, lo estoy tramitando. Regreso en un segundo.",
                "De acuerdo, estoy trabajando en eso. Un momento.",
                "Enseguida, déjame buscar esa información para ti.",
                "Procesando...",
            ]
            if self.session:
                try:
                    await self.session.send_tool_response(
                        function_responses=[
                            types.FunctionResponse(
                                id=call_id,
                                name=name,
                                response={"status": "procesando", "mensaje": random.choice(_ACKS)},
                            )
                        ]
                    )
                except Exception as exc:
                    print(f"[Hermes] Error enviando ACK: {exc}")
    
            # ── FASE 2: Ejecutar Hermes en segundo plano ───────────────────────
            import re
            loop = asyncio.get_running_loop()
            result = "Error: Hermes Core no está disponible."
    
            # Prefijo de contexto del sistema operativo para que Hermes
            # use el navegador predeterminado del sistema (con audio real)
            # en vez de su browser automatizado interno (headless/muted).
            _WINDOWS_HINT = (
            "[CONTEXTO DEL SISTEMA - Windows 11]\n"
            "IMPORTANTE: Estás operando en Windows 11. Para abrir URLs o reproducir "
            "media (YouTube, Spotify, videos), el usuario debe escucharlo, así que "
            "usa SIEMPRE el comando de terminal: `start <URL>`.\n"
            "REGLA CRÍTICA PARA MÚSICA/VIDEOS: NO abras páginas de resultados de búsqueda (ej. youtube.com/results). "
            "El usuario quiere que se reproduzca automáticamente. "
            "Primero usa tus herramientas (búsqueda web o browser) de forma silenciosa para encontrar "
            "la URL directa del video (ej. https://www.youtube.com/watch?v=...). "
            "SOLO CUANDO TENGAS LA URL DIRECTA DEL VIDEO, ejecuta `start <URL>`.\n\n"
            f"TAREA: {prompt}"
        )
    
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                try:
                    if self.hermes:
                        result = await loop.run_in_executor(None, self.hermes.chat, _WINDOWS_HINT)
                    break  # éxito — salir del bucle
                except Exception as exc:
                    err_str = str(exc)
                    # El proxy ya rota las keys automáticamente en cada llamada.
                    # Aquí solo manejamos fallos totales con backoff.
                    match = re.search(r"retry in ([\d.]+)s", err_str, re.IGNORECASE)
                    if match and attempt < max_retries:
                        wait = float(match.group(1)) + 5.0
                        print(f"[Hermes] Esperando {wait:.0f}s sugeridos por Google (intento {attempt}/{max_retries})…")
                        await asyncio.sleep(wait)
                    elif attempt < max_retries:
                        wait = 10.0 * attempt
                        print(f"[Hermes] Error (intento {attempt}/{max_retries}). Reintentando en {wait:.1f}s… [{exc}]")
                        await asyncio.sleep(wait)
                    else:
                        result = f"Error en Hermes tras {max_retries} intentos: {exc}"
    
            print(f"[Hermes] Listo.")
    
            # ── FASE 3: Inyectar resultado como nuevo turno ────────────────────
            # Ahora que Hermes terminó, inyectamos el resultado como un mensaje
            # de cliente para que Gemini lo lea en voz alta de forma natural.
            if self.session:
                try:
                    # Truncar el resultado para no exceder el contexto (tokens) de Gemini Live
                    res_str = str(result)
                    if len(res_str) > 800:
                        res_str = res_str[:800] + "... [truncado por longitud]"
    
                    result_text = (
                        f"[Resultado de tu búsqueda interna]: {res_str}. "
                        "Por favor preséntale este resultado al usuario de forma natural, como si tú mismo lo hubieras encontrado o hecho. NUNCA menciones la palabra 'Hermes'."
                    )
                    await self.session.send_client_content(
                        turns=types.Content(
                            role="user",
                            parts=[types.Part(text=result_text)],
                        ),
                        turn_complete=True,
                    )
                except Exception as exc:
                    print(f"[Hermes] Error inyectando resultado: {exc}")

        except Exception as exc:
            import traceback
            print(f"[Hermes] Fallo crítico en _run_hermes: {exc}")
            traceback.print_exc()

    # ── Inyección de contexto (habilidades aprendidas) ───────────────────
    async def _inject_context(self):
        while self.is_running and self.session:
            await asyncio.sleep(60)
            try:
                skills_dir = os.path.join(_HERMES_DIR, "skills")
                if os.path.isdir(skills_dir):
                    files = os.listdir(skills_dir)
                    if files:
                        print(f"[Jarvis] Habilidades detectadas: {len(files)}")
            except Exception as exc:
                print(f"[Jarvis] Error inyectando contexto: {exc}")



