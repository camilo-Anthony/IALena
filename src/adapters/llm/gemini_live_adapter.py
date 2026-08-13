"""
Cliente S2S (Speech-to-Speech) para JARVIS usando Google Gemini Live API.

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
import time
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
LIVE_SESSION_SOFT_REFRESH_SECONDS = int(os.getenv("LIVE_SESSION_SOFT_REFRESH_SECONDS", "720"))
LIVE_SESSION_FORCE_REFRESH_SECONDS = int(os.getenv("LIVE_SESSION_FORCE_REFRESH_SECONDS", "840"))
LIVE_DEBUG_AUDIO = os.getenv("LIVE_DEBUG_AUDIO", "").lower() in {"1", "true", "yes", "on"}
REQUIRE_RECENT_VOICE_FOR_TOOLS = os.getenv("REQUIRE_RECENT_VOICE_FOR_TOOLS", "1").lower() not in {"0", "false", "no", "off"}
REQUIRE_NEW_TRANSCRIPT_FOR_HERMES = os.getenv("REQUIRE_NEW_TRANSCRIPT_FOR_HERMES", "1").lower() not in {"0", "false", "no", "off"}
VOICE_TOOL_GATE_WINDOW_SECONDS = float(os.getenv("VOICE_TOOL_GATE_WINDOW_SECONDS", "12.0"))
VOICE_TOOL_RECONNECT_GRACE_SECONDS = float(os.getenv("VOICE_TOOL_RECONNECT_GRACE_SECONDS", "2.0"))
LIVE_QUOTA_BACKOFF_SECONDS = float(os.getenv("LIVE_QUOTA_BACKOFF_SECONDS", "60.0"))
LIVE_QUOTA_MAX_BACKOFF_SECONDS = float(os.getenv("LIVE_QUOTA_MAX_BACKOFF_SECONDS", "300.0"))


# pyrefly: ignore [missing-import]
from src.core.interfaces.voice_llm import IVoiceAssistant
from src.kernel.cognitive_policy import CognitivePolicy, ToolDecision

# ═════════════════════════════════════════════════════════════════════════
class GeminiLiveAdapter(IVoiceAssistant):
    """Adaptador para el modelo de voz Gemini Live (Google)."""

    def __init__(
        self,
        audio_capture,
        audio_playback,
        context_manager,
        action_router,
        activation_gate=None,
        conversation_sessions=None,
        cognitive_policy=None,
    ):
        self.capture = audio_capture
        self.playback = audio_playback
        self.context_mgr = context_manager
        self.hermes_router = action_router
        self.activation_gate = activation_gate
        self.conversation_sessions = conversation_sessions
        self.cognitive_policy = cognitive_policy or CognitivePolicy()

        self.client = genai.Client(
            api_key=GEMINI_API_KEY,
            http_options=types.HttpOptions(api_version="v1alpha"),
        )
        self.session = None
        self.is_running = False
        self.session_epoch = 0
        self._session_started_at = 0.0
        self._reconnect_output_suppressed_logged = False
        self._hermes_speech_revision = 0
        self._last_hermes_speech_revision = 0

    def _is_session_recycle_error(self, exc: BaseException) -> bool:
        text = str(exc)
        return (
            "GoAway" in text
            or "failed to close the connection" in text
            or "received 1008" in text
            or "policy violation" in text
        )

    def _is_live_quota_error(self, exc: BaseException) -> bool:
        text = str(exc).lower()
        return (
            "resource has been exhausted" in text
            or "quota" in text
            or "rate limit" in text
            or "rate_limit" in text
            or "429" in text
        )

    async def _pause_after_quota_error(self, delay_seconds: float) -> None:
        delay_seconds = max(1.0, delay_seconds)
        print(
            f"[JARVIS] Cuota de Gemini Live agotada. "
            f"Pausando reconexion {delay_seconds:.0f}s para evitar bucle."
        )
        activation_gate = getattr(self, "activation_gate", None)
        if activation_gate:
            activation_gate.force_sleep("live_quota_exhausted")
        self._close_conversation_session("live_quota_exhausted")
        await asyncio.sleep(delay_seconds)

    def _is_reconnect_grace_active(self) -> bool:
        if not self._session_started_at:
            return False
        return (time.monotonic() - self._session_started_at) < VOICE_TOOL_RECONNECT_GRACE_SECONDS

    def _mark_user_voice(self, reason: str) -> None:
        activation_gate = getattr(self, "activation_gate", None)
        if activation_gate:
            activation_gate.mark_user_voice(reason)
        conversation_sessions = getattr(self, "conversation_sessions", None)
        if conversation_sessions:
            conversation_sessions.ensure_active_session(self.session_epoch)

    def _record_user_text(self, text: str, kind: str = "speech") -> None:
        if kind == "speech":
            self._policy().record_user_utterance(text)
            self._hermes_speech_revision = getattr(self, "_hermes_speech_revision", 0) + 1
        conversation_sessions = getattr(self, "conversation_sessions", None)
        if conversation_sessions:
            conversation_sessions.record_user(text, kind=kind, session_epoch=self.session_epoch)

    def _record_assistant_text(self, text: str, kind: str = "speech") -> None:
        conversation_sessions = getattr(self, "conversation_sessions", None)
        if conversation_sessions:
            conversation_sessions.record_assistant(text, kind=kind, session_epoch=self.session_epoch)

    def _close_conversation_session(self, reason: str) -> None:
        conversation_sessions = getattr(self, "conversation_sessions", None)
        if conversation_sessions:
            conversation_sessions.close_active_session(reason)

    @staticmethod
    def _extract_transcription_text(transcription) -> str:
        if not transcription:
            return ""
        text = getattr(transcription, "text", None)
        if text:
            return str(text).strip()
        return str(transcription).strip()

    def _policy(self) -> CognitivePolicy:
        policy = getattr(self, "cognitive_policy", None)
        if policy is None:
            policy = CognitivePolicy()
            self.cognitive_policy = policy
        return policy

    def _remember_user_utterance(self, text: str) -> None:
        self._policy().record_user_utterance(text)

    def _recent_user_utterance_text(self, window_seconds: float) -> str:
        return self._policy().recent_user_text(window_seconds)

    def _is_explicit_music_request(self, song: str = "") -> bool:
        return self._policy().has_explicit_music_request(song)

    @staticmethod
    def _looks_like_internal_delivery_prompt(prompt: str) -> bool:
        normalized = CognitivePolicy.normalize_for_intent(prompt)
        if not normalized:
            return False
        internal_markers = (
            "jarvis internal delivery",
            "mensaje interno de delivery",
            "resultado de la tarea solicitada",
            "resultado rapido",
            "fallo de tarea interna",
            "no es una orden nueva del usuario",
            "no usar herramientas",
        )
        return any(marker in normalized for marker in internal_markers)

    def _evaluate_hermes_transcript_gate(self, prompt: str = "") -> ToolDecision:
        if self._looks_like_internal_delivery_prompt(prompt):
            return ToolDecision.reject(
                "ignorado",
                "Ignore una redelegacion generada por una entrega interna.",
                "delivery_interno_no_es_orden",
            )
        if not REQUIRE_NEW_TRANSCRIPT_FOR_HERMES:
            return ToolDecision.allow("transcript_gate_disabled")
        current_revision = getattr(self, "_hermes_speech_revision", 0)
        consumed_revision = getattr(self, "_last_hermes_speech_revision", 0)
        if current_revision <= consumed_revision:
            return ToolDecision.reject(
                "ignorado",
                "No detecte una nueva frase transcrita del usuario para iniciar otra tarea.",
                "sin_transcripcion_nueva",
            )
        return ToolDecision.allow("transcripcion_nueva")

    def _mark_hermes_transcript_consumed(self) -> None:
        self._last_hermes_speech_revision = getattr(self, "_hermes_speech_revision", 0)

    def _has_recent_user_voice(self) -> bool:
        if not REQUIRE_RECENT_VOICE_FOR_TOOLS:
            return True
        activation_gate = getattr(self, "activation_gate", None)
        if not activation_gate and self._is_reconnect_grace_active():
            return False
        has_recent_voice = getattr(self.capture, "has_recent_voice", None)
        if not callable(has_recent_voice):
            return True
        recent_voice = bool(has_recent_voice(VOICE_TOOL_GATE_WINDOW_SECONDS))
        if recent_voice:
            self._mark_user_voice("tool_call_voice")
        if activation_gate and not activation_gate.allows_user_tool_call():
            return False
        return recent_voice

    def _should_suppress_reconnect_output(self) -> bool:
        activation_gate = getattr(self, "activation_gate", None)
        if activation_gate:
            return not activation_gate.allows_model_output()
        return REQUIRE_RECENT_VOICE_FOR_TOOLS and self._is_reconnect_grace_active()

    @staticmethod
    def _has_hermes_tool_call(msg) -> bool:
        tool_call = getattr(msg, "tool_call", None)
        function_calls = getattr(tool_call, "function_calls", None) if tool_call else None
        return any(
            getattr(fn, "name", "") == "ejecutar_hermes_core"
            for fn in (function_calls or [])
        )

    def _should_suppress_model_turn(self, msg) -> tuple[bool, str]:
        if self._should_suppress_reconnect_output():
            return True, "post_reconnect"
        if self._has_hermes_tool_call(msg):
            return True, "hermes_tool_call"
        return False, ""

    def _claim_response_for_hermes(self, prompt: str) -> None:
        print(
            "\033[95m[JARVIS]\033[0m Turno delegado a Hermes; salida Live directa descartada "
            f"(prompt_chars={len(prompt)})."
        )
        print("[LiveAdapter] direct_output suppressed reason=delivery_claimed")

    async def _reject_tool_without_recent_voice(self, call_id: str, name: str):
        print(f"\033[95m[JARVIS]\033[0m Tool call ignorada sin voz reciente: {name}")
        if not self.session:
            return
        try:
            await self.session.send_tool_response(
                function_responses=[
                    types.FunctionResponse(
                        id=call_id,
                        name=name,
                        response={
                            "status": "ignorado",
                            "mensaje": "No detecté una orden de voz reciente, así que no inicié ninguna tarea.",
                        },
                    )
                ]
            )
        except Exception as exc:
            print(f"\033[95m[JARVIS]\033[0m Error respondiendo tool call sin voz reciente: {exc}")

    async def _reject_tool_without_confirmed_intent(self, call_id: str, name: str, reason: str):
        print(f"\033[95m[JARVIS]\033[0m Tool call ignorada por intencion no confirmada: {name} ({reason})")
        if not self.session:
            return
        try:
            await self.session.send_tool_response(
                function_responses=[
                    types.FunctionResponse(
                        id=call_id,
                        name=name,
                        response={
                            "status": "ignorado",
                            "mensaje": "No detecte una orden explicita para usar esa herramienta.",
                        },
                    )
                ]
            )
        except Exception as exc:
            print(f"\033[95m[JARVIS]\033[0m Error respondiendo tool call sin intencion confirmada: {exc}")

    async def _reject_tool_by_policy(self, call_id: str, name: str, decision: ToolDecision):
        print(f"\033[92m[ToolGate]\033[0m Tool call rechazada: {name} ({decision.reason})")
        if not self.session:
            return
        try:
            await self.session.send_tool_response(
                function_responses=[
                    types.FunctionResponse(
                        id=call_id,
                        name=name,
                        response={
                            "status": decision.status,
                            "mensaje": decision.message,
                            "reason": decision.reason,
                        },
                    )
                ]
            )
        except Exception as exc:
            print(f"\033[92m[ToolGate]\033[0m Error respondiendo rechazo de tool call: {exc}")

    # ── Conexión principal ───────────────────────────────────────────────
    async def connect(self):
        if not GEMINI_API_KEY:
            print("\033[91m[ERROR] Falta GEMINI_API_KEY / GOOGLE_API_KEY en .env\033[0m")
            return

        print(f"\033[95m[JARVIS]\033[0m Iniciando sistema Auto-Reconexión para {MODEL_LIVE}…")
        try:
            self.is_running = True
            self.capture.start()
            self.playback.start()

            reconnect_count = 0
            quota_backoff_seconds = LIVE_QUOTA_BACKOFF_SECONDS
            while self.is_running:
                # Obtener la configuración fresca del gestor de contexto (incluye memoria inyectada)
                config = self.context_mgr.get_live_config()

                try:
                    async with self.client.aio.live.connect(model=MODEL_LIVE, config=config) as session:
                        self.session = session
                        reset_recent_voice = getattr(self.capture, "reset_recent_voice", None)
                        if callable(reset_recent_voice):
                            reset_recent_voice()
                        self._session_started_at = time.monotonic()
                        if self.activation_gate:
                            # Primer inicio de sesión de la ejecución: activar de inmediato
                            is_first_session = (self.session_epoch == 0)
                            self.session_epoch = self.activation_gate.start_live_session("live_connected")
                            if is_first_session:
                                self.activation_gate.mark_user_voice("initial_activation")
                        else:
                            self.session_epoch += 1
                        self._reconnect_output_suppressed_logged = False
                        print("\033[95m[JARVIS]\033[0m ¡Conexión en vivo establecida! Escuchando…")

                        t_send = asyncio.create_task(self._send_audio())
                        t_recv = asyncio.create_task(self._receive())
                        t_watchdog = asyncio.create_task(self._session_watchdog())

                        done, pending = await asyncio.wait(
                            [t_send, t_recv, t_watchdog],
                            return_when=asyncio.FIRST_COMPLETED
                        )

                        # Limpiar tareas huérfanas
                        self.session = None
                        for task in pending:
                            task.cancel()
                        if pending:
                            await asyncio.gather(*pending, return_exceptions=True)

                        recycle_reason = None
                        for task in done:
                            try:
                                exc = task.exception()
                            except asyncio.CancelledError:
                                exc = None
                            if exc:
                                if str(exc) == "Proactive_Refresh":
                                    recycle_reason = "refresh"
                                elif self._is_live_quota_error(exc):
                                    recycle_reason = "quota"
                                elif self._is_session_recycle_error(exc):
                                    recycle_reason = "goaway"
                                else:
                                    raise exc

                        if not self.is_running:
                            break
                        if recycle_reason == "refresh":
                            quota_backoff_seconds = LIVE_QUOTA_BACKOFF_SECONDS
                            print("\033[95m[JARVIS]\033[0m Sesion reciclada preventivamente. Reconectando en silencio...")
                        elif recycle_reason == "quota":
                            await self._pause_after_quota_error(quota_backoff_seconds)
                            quota_backoff_seconds = min(
                                LIVE_QUOTA_MAX_BACKOFF_SECONDS,
                                quota_backoff_seconds * 2,
                            )
                        elif recycle_reason == "goaway":
                            quota_backoff_seconds = LIVE_QUOTA_BACKOFF_SECONDS
                            print("\033[95m[JARVIS]\033[0m Sesion Live expiro; reciclando conexion...")
                        else:
                            quota_backoff_seconds = LIVE_QUOTA_BACKOFF_SECONDS
                            print("\033[95m[JARVIS]\033[0m Sesion reciclada. Reconectando en silencio...")
                        continue
                except Exception as exc:
                    if not self.is_running:
                        break
                    if str(exc) == "Proactive_Refresh":
                        quota_backoff_seconds = LIVE_QUOTA_BACKOFF_SECONDS
                        print("\033[95m[JARVIS]\033[0m Refresco preventivo exitoso.")
                    elif self._is_live_quota_error(exc):
                        await self._pause_after_quota_error(quota_backoff_seconds)
                        quota_backoff_seconds = min(
                            LIVE_QUOTA_MAX_BACKOFF_SECONDS,
                            quota_backoff_seconds * 2,
                        )
                    elif self._is_session_recycle_error(exc):
                        quota_backoff_seconds = LIVE_QUOTA_BACKOFF_SECONDS
                        print("\033[95m[JARVIS]\033[0m Sesion Live expiro; reconectando en 2s...")
                        await asyncio.sleep(2)
                    else:
                        print(f"\033[95m[JARVIS]\033[0m Caída de red detectada ({exc}). Reconectando en 2s...")
                        await asyncio.sleep(2)

                    reconnect_count += 1
        except Exception as exc:
            print(f"\033[95m[JARVIS]\033[0m Error fatal de conexión: {exc}")
        finally:
            self.is_running = False
            self._close_conversation_session("voice_adapter_stopped")
            self.capture.terminate()
            self.playback.terminate()

    def stop(self):
        """Detiene el bucle y cierra la conexión."""
        self.is_running = False
        self._close_conversation_session("voice_adapter_stop_requested")
        self.capture.stop()
        self.playback.stop()

    async def _session_watchdog(self):
        """Evita el corte brusco de Google (15 min) refrescando la sesión en un momento de silencio."""
        watchdog_epoch = self.session_epoch
        start_time = time.time()
        while self.is_running and self.session:
            if watchdog_epoch != self.session_epoch:
                break
            elapsed = time.time() - start_time
            if self.activation_gate:
                if self.activation_gate.sleep_if_idle():
                    self._close_conversation_session("idle_timeout")
            if elapsed > LIVE_SESSION_FORCE_REFRESH_SECONDS:
                print("[JARVIS] Refrescando sesion proactivamente por limite de duracion...")
                raise Exception("Proactive_Refresh")
            if elapsed > LIVE_SESSION_SOFT_REFRESH_SECONDS and not getattr(self.playback, "is_busy", False):
                print("[JARVIS] Refrescando sesion proactivamente en silencio...")
                raise Exception("Proactive_Refresh")
            await asyncio.sleep(2)

    # ── Envío de audio (micrófono → Gemini) ──────────────────────────────
    async def _send_audio(self):
        send_epoch = self.session_epoch
        while self.is_running and self.session:
            if send_epoch != self.session_epoch:
                print("[JARVIS] Envio de audio detenido por cambio de epoch de sesion.")
                break
            try:
                chunk = await self.capture.read_chunk()
                has_recent_voice = getattr(self.capture, "has_recent_voice", None)
                if callable(has_recent_voice) and has_recent_voice(0.25):
                    self._mark_user_voice("audio_activity")
                await self.session.send_realtime_input(
                    audio=types.Blob(data=chunk, mime_type=f"audio/pcm;rate={INPUT_RATE}")
                )
            except Exception as exc:
                if self._is_live_quota_error(exc):
                    print("[JARVIS] Envio de audio detenido por cuota agotada de Gemini Live.")
                    raise
                if self._is_session_recycle_error(exc):
                    print("[JARVIS] Envio de audio detenido por reciclado de sesion.")
                else:
                    print(f"[JARVIS] Error enviando audio: {exc}")
                break

    # ── Recepción de audio / tool calls (Gemini → altavoz) ───────────────
    async def _receive(self):
        receive_epoch = self.session_epoch
        while self.is_running and self.session:
            try:
                async for msg in self.session.receive():
                    if receive_epoch != self.session_epoch:
                        print("[JARVIS] Recepcion descartada por cambio de epoch de sesion.")
                        break
                    # Audio y texto del modelo
                    if msg.server_content:
                        sc = msg.server_content
                        input_text = self._extract_transcription_text(getattr(sc, "input_transcription", None))
                        if input_text:
                            self._record_user_text(input_text, kind="speech")
                        if sc.model_turn:
                            suppress_model_turn, suppress_reason = self._should_suppress_model_turn(msg)
                            if suppress_model_turn:
                                if suppress_reason == "post_reconnect" and not self._reconnect_output_suppressed_logged:
                                    print("[JARVIS] Salida Live ignorada durante gracia post-reconexion.")
                                    print("[LiveAdapter] direct_output suppressed reason=post_reconnect")
                                    self._reconnect_output_suppressed_logged = True
                                elif suppress_reason == "hermes_tool_call":
                                    print("[JARVIS] Salida Live directa ignorada: el turno fue delegado a Hermes.")
                                    print("[LiveAdapter] direct_output suppressed reason=hermes_tool_call")
                            else:
                                for part in sc.model_turn.parts:
                                    if part.inline_data:
                                        if LIVE_DEBUG_AUDIO:
                                            print(f" [Audio rec. {len(part.inline_data.data)}b] ", end="", flush=True)
                                        self.playback.enqueue(part.inline_data.data)
                                    if part.text:
                                        print(f"\n[JARVIS Texto] {part.text.strip()}", flush=True)
                                        self._record_assistant_text(part.text.strip(), kind="speech")
                        if sc.interrupted:
                            print("\n[JARVIS] Interrumpida.", flush=True)
                            # Barge-in de voz: solo corta la respuesta hablada.
                            # No cancela Hermes; la cancelacion requiere tool call explicita.
                            self.playback.flush()

                    # Llamadas a funciones
                    if msg.tool_call:
                        for fn in msg.tool_call.function_calls:
                            args = dict(getattr(fn, "args", {}) or {})
                            decision = self._policy().evaluate_tool_call(
                                fn.name,
                                args=args,
                                has_recent_voice=self._has_recent_user_voice(),
                            )
                            if not decision.allowed:
                                await self._reject_tool_by_policy(fn.id, fn.name, decision)
                                continue

                            # Validación adicional de transcripción para Hermes
                            if fn.name == "ejecutar_hermes_core":
                                prompt = args.get("prompt", "")
                                transcript_decision = self._evaluate_hermes_transcript_gate(prompt)
                                if not transcript_decision.allowed:
                                    await self._reject_tool_by_policy(fn.id, fn.name, transcript_decision)
                                    continue
                                self._mark_hermes_transcript_consumed()
                                self._record_user_text(prompt, kind="hermes_tool_call")
                                self._claim_response_for_hermes(prompt)

                            elif fn.name == "cancelar_tarea_hermes":
                                motivo = args.get("motivo", "")
                                self._record_user_text(
                                    motivo or "Cancelar tarea Hermes activa",
                                    kind="cancel_tool_call",
                                )
                            elif fn.name == "consultar_estado_tareas":
                                self._record_user_text(
                                    "Consultar estado de tareas complejas",
                                    kind="task_status_tool_call",
                                )
                            elif fn.name == "consultar_resumen_hoy":
                                self._record_user_text(
                                    "Consultar resumen local de hoy",
                                    kind="today_summary_tool_call",
                                )
                            elif fn.name == "reproducir_musica_youtube":
                                cancion = args.get("cancion", "")
                                self._record_user_text(f"Reproducir en YouTube: {cancion}", kind="music_tool_call")
                                print(f"[JARVIS] Reproduciendo en YouTube: {cancion}")

                            print(f"[ToolGate] Tool call aceptada: {fn.name} ({decision.reason})")
                            print(f"[LiveAdapter] delegated call={fn.id} tool={fn.name} suppress_live_output=true")
                            if self.hermes_router:
                                asyncio.create_task(
                                    self.hermes_router.submit_tool_call(
                                        fn.name, args, self.session, fn.id
                                    )
                                )
                            else:
                                print("[JARVIS] Error: hermes_router no está inicializado.")
            except asyncio.CancelledError:
                break
            except Exception as exc:
                if self._is_live_quota_error(exc):
                    print("[JARVIS] Recepcion detenida por cuota agotada de Gemini Live.")
                    raise
                if self._is_session_recycle_error(exc):
                    print("[JARVIS] Recepcion detenida por reciclado de sesion.")
                else:
                    print(f"[JARVIS] Error recibiendo: {exc}")
                break
