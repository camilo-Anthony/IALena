"""
Cliente S2S (Speech-to-Speech) para IALena usando Google Gemini Live API.

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



# ── Configuración ────────────────────────────────────────────────────────
load_dotenv(encoding="utf-8")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")

# Carga todas las claves de Hermes definidas como HERMES_API_KEY_1, _2, _3...
# Fallback a GEMINI_API_KEY si no hay ninguna.
_raw_hermes_keys = [
    os.getenv(f"HERMES_API_KEY_{i}")
    for i in range(1, 30)
]
HERMES_API_KEYS: list[str] = [k for k in _raw_hermes_keys if k] or [GEMINI_API_KEY]

INPUT_RATE  = 16_000   # Gemini Live espera entrada a 16 kHz
OUTPUT_RATE = 24_000   # Gemini Live devuelve audio a 24 kHz
MODEL_LIVE  = os.getenv("MODEL_LIVE", "gemini-3.1-flash-live-preview")
MODEL_BRAIN = os.getenv("MODEL_BRAIN", "gemini-3.1-flash-lite")
VOICE_NAME  = os.getenv("VOICE_NAME", "Aoede")


# pyrefly: ignore [missing-import]
from src.core.interfaces.voice_llm import IVoiceAssistant

# ═════════════════════════════════════════════════════════════════════════
class GeminiLiveAdapter(IVoiceAssistant):
    """Adaptador para el modelo de voz Gemini Live (Google)."""

    def __init__(self, audio_capture, audio_playback, context_manager, action_router):
        self.capture = audio_capture
        self.playback = audio_playback
        self.context_mgr = context_manager
        self.hermes_router = action_router
        
        self.client = genai.Client(
            api_key=GEMINI_API_KEY,
            http_options=types.HttpOptions(api_version="v1alpha"),
        )
        self.session = None
        self.is_running = False

    # ── Conexión principal ───────────────────────────────────────────────
    async def connect(self):
        if not GEMINI_API_KEY:
            print("[ERROR] Falta GEMINI_API_KEY / GOOGLE_API_KEY en .env")
            return

        print(f"[IALena] Iniciando sistema Auto-Reconexión para {MODEL_LIVE}…")
        try:
            self.is_running = True
            self.capture.start()
            self.playback.start()

            reconnect_count = 0
            while self.is_running:
                # Obtener la configuración fresca del gestor de contexto (incluye memoria inyectada)
                config = self.context_mgr.get_live_config()

                try:
                    async with self.client.aio.live.connect(model=MODEL_LIVE, config=config) as session:
                        self.session = session
                        print("[IALena] ¡Conexión en vivo establecida! Escuchando…")
                        
                        t_send = asyncio.create_task(self._send_audio())
                        t_recv = asyncio.create_task(self._receive())
                        t_watchdog = asyncio.create_task(self._session_watchdog())

                        done, pending = await asyncio.wait(
                            [t_send, t_recv, t_watchdog],
                            return_when=asyncio.FIRST_COMPLETED
                        )
                        
                        # Limpiar tareas huérfanas
                        for task in pending:
                            task.cancel()
                        
                        if not self.is_running:
                            break
                        
                        print("[IALena] Sesión reciclada. Reconectando en silencio...")
                except Exception as exc:
                    if not self.is_running:
                        break
                    if str(exc) == "Proactive_Refresh":
                        print("[IALena] Refresco preventivo exitoso.")
                    else:
                        print(f"[IALena] Caída de red detectada ({exc}). Reconectando en 2s...")
                        await asyncio.sleep(2)
                    
                    reconnect_count += 1
        except Exception as exc:
            print(f"[IALena] Error fatal de conexión: {exc}")
        finally:
            self.is_running = False
            self.capture.terminate()
            self.playback.terminate()

    def stop(self):
        """Detiene el bucle y cierra la conexión."""
        self.is_running = False
        self.capture.stop()
        self.playback.stop()

    async def _session_watchdog(self):
        """Evita el corte brusco de Google (15 min) refrescando la sesión en un momento de silencio."""
        import time
        start_time = time.time()
        while self.is_running and self.session:
            elapsed = time.time() - start_time
            # Límite de Google: 15 min (900s). Empezamos a buscar silencio a los 13.5 min (810s).
            if elapsed > 810:
                # Si el modelo no está hablando y la cola de reproducción está vacía, reciclamos de forma segura.
                # Como self.playback usa una cola, comprobamos si tiene elementos encolados.
                try:
                    if hasattr(self.playback, "is_busy"):
                        if not self.playback.is_busy:
                            print("[IALena] Refrescando sesión proactivamente (evitando corte brusco)...")
                            raise Exception("Proactive_Refresh")
                    else:
                        # Si no podemos chequear la cola, esperamos al minuto 14 para forzarlo
                        if elapsed > 840:
                            print("[IALena] Refrescando sesión proactivamente...")
                            raise Exception("Proactive_Refresh")
                except Exception as e:
                    if str(e) == "Proactive_Refresh":
                        raise e
            await asyncio.sleep(2)

    # ── Envío de audio (micrófono → Gemini) ──────────────────────────────
    async def _send_audio(self):
        while self.is_running and self.session:
            try:
                chunk = await self.capture.read_chunk()
                await self.session.send_realtime_input(
                    audio=types.Blob(data=chunk, mime_type=f"audio/pcm;rate={INPUT_RATE}")
                )
            except Exception as exc:
                print(f"[IALena] Error enviando audio: {exc}")
                break

    # ── Recepción de audio / tool calls (Gemini → altavoz) ───────────────
    async def _receive(self):
        while self.is_running and self.session:
            try:
                async for msg in self.session.receive():
                    # Audio y texto del modelo
                    if msg.server_content:
                        sc = msg.server_content
                        if sc.model_turn:
                            for part in sc.model_turn.parts:
                                if part.inline_data:
                                    self.playback.enqueue(part.inline_data.data)
                                if part.text:
                                    self.context_mgr.add_memory(f"IALena dijo: {part.text.strip()}")
                        if sc.interrupted:
                            self.playback.flush()

                    # Llamadas a funciones
                    if msg.tool_call:
                        for fn in msg.tool_call.function_calls:
                            if fn.name == "ejecutar_hermes_core":
                                prompt = fn.args.get("prompt", "")
                                self.context_mgr.add_memory(f"El usuario te pidió la siguiente tarea compleja: {prompt}")
                                    
                                if self.hermes_router:
                                    asyncio.create_task(
                                        self.hermes_router.run_hermes(fn.id, fn.name, prompt)
                                    )
                                else:
                                    print("[IALena] Error: hermes_router no está inicializado.")
                            elif fn.name == "reproducir_musica_youtube":
                                cancion = fn.args.get("cancion", "")
                                print(f"[IALena] Reproduciendo en YouTube: {cancion}")
                                # 1. Cerrar el ciclo de la tool call de inmediato
                                try:
                                    await self.session.send_tool_response(
                                        function_responses=[
                                            types.FunctionResponse(
                                                name="reproducir_musica_youtube",
                                                id=fn.id,
                                                response={"result": f"Reproduciendo '{cancion}' en YouTube."}
                                            )
                                        ]
                                    )
                                except Exception as e:
                                    print(f"[IALena] Error tool response música: {e}")
                                # 2. Lanzar el script de YouTube en background
                                import subprocess
                                play_yt_path = os.path.join(os.path.dirname(__file__), "play_yt.py")
                                subprocess.Popen([sys.executable, play_yt_path, cancion])
            except asyncio.CancelledError:
                break
            except Exception as exc:
                print(f"[IALena] Error recibiendo: {exc}")
                break

