import os
import time
import random
import asyncio
from google.genai import types

# pyrefly: ignore [missing-import]
from src.core.interfaces.brain import IAgentBrain

class ActionRouter:
    """Enruta peticiones complejas de la voz hacia el cerebro asíncrono (IAgentBrain)."""
    
    def __init__(self, brain_adapter: IAgentBrain, get_session_callback, is_busy_callback=None):
        self.brain = brain_adapter
        self.get_session = get_session_callback
        self.is_busy = is_busy_callback
        
        self._ACKS = [
            "Dile al usuario: 'Entendido, dame un momento para revisarlo.' y espera pacientemente.",
            "Dile al usuario: 'Claro, estoy en ello. Un segundo...' y espera pacientemente.",
            "Dile al usuario: 'Perfecto, lo estoy buscando. Regreso en un segundo.' y espera pacientemente.",
            "Dile al usuario: 'De acuerdo, trabajando en eso. Un momento.' y espera pacientemente.",
            "Dile al usuario: 'Enseguida, déjame consultar eso para ti.' y espera pacientemente."
        ]

    def _computing_sound(self):
        """Efecto de sonido J.A.R.V.I.S. sin interrumpir la voz."""
        try:
            import winsound
            wav_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "voice", "assets", "jarvis_processing.wav")
            if os.path.exists(wav_path):
                winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except:
            pass

    async def run_hermes(self, call_id: str, name: str, prompt: str):
        """Ejecuta una herramienta compleja de forma asíncrona y devuelve el resultado a la sesión activa."""
        start_time = time.time()
        
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, self._computing_sound)
        
        try:
            # ── FASE 1: ACK inmediato ──────────────────────────────────────────
            session = self.get_session()
            if session:
                try:
                    await session.send_tool_response(
                        function_responses=[
                            types.FunctionResponse(
                                id=call_id,
                                name=name,
                                response={"status": "procesando", "mensaje": random.choice(self._ACKS)}
                            )
                        ]
                    )
                except Exception as exc:
                    print(f"[HermesRouter] Error enviando ACK: {exc}")

            # ── FASE 2: Ejecutar Hermes en segundo plano ───────────────────────
            result = "Error: Hermes Core no está disponible."
            bot_name = os.getenv("ASSISTANT_NAME", "IALena")
            user_name = os.getenv("USER_NAME", "Señor")
            
            if self.brain.is_available():
                # Prefijo de contexto para que el Cerebro herede la personalidad y reglas de la PC
                prompt_enriquecido = (
                    f"[IDENTIDAD CRÍTICA]\n"
                    f"Eres el núcleo lógico e investigativo del asistente '{bot_name}'. "
                    f"El usuario '{user_name}' te ha pedido algo mediante la interfaz de voz.\n\n"
                    f"[CONTEXTO DEL SISTEMA - Windows 11]\n"
                    "IMPORTANTE: Estás operando en Windows 11. Para abrir URLs, usar el navegador "
                    "o reproducir multimedia, DEBES usar comandos de terminal compatibles con Windows (ej. `start <URL>`).\n"
                    "Para reproducir música/videos: NO abras páginas de resultados de YouTube. "
                    "Usa tus herramientas para buscar la URL directa del video y luego ejecuta `start <URL>`.\n\n"
                    f"TAREA DEL USUARIO: {prompt}\n\n"
                    "[INSTRUCCIÓN INTERNA]: Resuelve la tarea usando tus herramientas. "
                    "Cuando termines, devuelve SOLO los datos o el resultado final de tu investigación/acción. "
                    f"NUNCA redactes un saludo, no actúes como asistente ni pidas confirmación. {bot_name} se encargará de hablar con el usuario basándose en tus datos puros."
                )

                max_retries = 3
                for attempt in range(1, max_retries + 1):
                    try:
                        result = await loop.run_in_executor(None, self.brain.chat, prompt_enriquecido)
                        break
                    except Exception as exc:
                        if "429" in str(exc) and attempt < max_retries:
                            await asyncio.sleep(2)
                        else:
                            result = f"Error en Cerebro tras {max_retries} intentos: {exc}"

            print(f"[HermesRouter] Tarea finalizada.")
    
            # ── FASE 3: Inyectar resultado evitando cortes bruscos ─────────────
            current_session = self.get_session()
            if current_session:
                try:
                    res_str = str(result)
                    if len(res_str) > 800:
                        res_str = res_str[:800] + "... [truncado por longitud]"

                    # ANTI-INTERRUPCIÓN: Esperar a que el modelo termine de hablar el ACK
                    if self.is_busy:
                        while self.is_busy():
                            await asyncio.sleep(0.5)
                    else:
                        elapsed = time.time() - start_time
                        if elapsed < 5.0:
                            await asyncio.sleep(5.0 - elapsed)

                    result_text = (
                        f"[Resultado de tu búsqueda interna]: {res_str}. "
                        "Por favor preséntale este resultado al usuario de forma natural, NUNCA menciones a 'Hermes'."
                    )
                    await current_session.send_client_content(
                        turns=[
                            types.Content(
                                role="user",
                                parts=[types.Part(text=result_text)],
                            )
                        ],
                        turn_complete=True,
                    )
                except Exception as exc:
                    print(f"[HermesRouter] Error inyectando resultado: {exc}")

        except Exception as exc:
            import traceback
            print(f"[HermesRouter] Fallo crítico en run_hermes: {exc}")
            traceback.print_exc()
