"""
telegram_bridge.py — Puente bidireccional de Telegram para JARVIS.

Permite interactuar con JARVIS y Hermes Core a través de un bot de Telegram:
- Recibe comandos de texto y solicitudes remotas.
- Solo procesa mensajes del usuario autorizado (TELEGRAM_CHAT_ID).
- Enruta la consulta al carril adecuado de Hermes en ActionRouter.
- Responde directamente al chat con el resultado procesado.
"""
import os
import asyncio
import logging
from typing import Optional, Callable, Any

logger = logging.getLogger("JARVIS.TelegramBridge")


class TelegramBridge:
    """Escucha y responde mensajes de Telegram de forma asíncrona."""

    def __init__(
        self,
        token: Optional[str] = None,
        authorized_chat_id: Optional[str] = None,
        router_dispatch_fn: Optional[Callable[[str, str], Any]] = None,
    ):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.authorized_chat_id = str(authorized_chat_id or os.getenv("TELEGRAM_CHAT_ID", "").strip())
        self.dispatch_fn = router_dispatch_fn
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_update_id = 0

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.authorized_chat_id)

    def start(self) -> None:
        """Inicia el ciclo de polling en segundo plano."""
        if not self.is_configured:
            print("[TelegramBridge] No configurado (faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID en .env).")
            return
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        print(f"\033[32m[TelegramBridge]\033[0m Iniciado para el chat autorizado: {self.authorized_chat_id}")

    def stop(self) -> None:
        """Detiene el ciclo de polling."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        print("[TelegramBridge] Detenido.")

    async def _send_message(self, chat_id: str | int, text: str, reply_to_id: Optional[int] = None) -> bool:
        """Envía un mensaje de respuesta a Telegram."""
        import httpx

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        # Limitar longitud para evitar error 400 de Telegram
        clean_text = text.strip()
        if len(clean_text) > 3900:
            clean_text = clean_text[:3900] + "\n… [Respuesta truncada por longitud]"

        payload = {
            "chat_id": chat_id,
            "text": clean_text,
        }
        if reply_to_id:
            payload["reply_to_message_id"] = reply_to_id

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, json=payload)
                return res.status_code == 200
        except Exception as exc:
            logger.warning(f"[TelegramBridge] Error enviando mensaje a Telegram: {exc}")
            return False

    async def _handle_message(self, message: dict) -> None:
        """Procesa un mensaje recibido."""
        from_user = message.get("from", {})
        chat = message.get("chat", {})
        chat_id = str(chat.get("id", ""))
        message_id = message.get("message_id")
        text = (message.get("text") or "").strip()

        # Validación estricta de seguridad
        if chat_id != self.authorized_chat_id:
            logger.warning(
                f"[TelegramBridge] Mensaje ignorado de usuario no autorizado: "
                f"id={chat_id}, username={from_user.get('username')}"
            )
            return

        if not text:
            await self._send_message(
                chat_id,
                "🤖 JARVIS recibió tu mensaje, pero solo procesa texto actualmente.",
                reply_to_id=message_id,
            )
            return

        print(f"\033[35m[TelegramBridge]\033[0m Mensaje recibido: '{text}' (msg_id={message_id})")

        # Confirmación inmediata de recepción
        await self._send_message(
            chat_id,
            f"⚡ *JARVIS*: Procesando tu orden con Hermes Core…\n`{text[:80]}...`" if len(text) > 80 else f"⚡ *JARVIS*: Procesando: '{text}'…",
            reply_to_id=message_id,
        )

        if not self.dispatch_fn:
            await self._send_message(
                chat_id,
                "⚠️ Error interno: el despachador de JARVIS no está disponible.",
                reply_to_id=message_id,
            )
            return

        # Despachar al ActionRouter de JARVIS
        try:
            response_text = await self.dispatch_fn(text, source="telegram")
            if not response_text:
                response_text = "✅ Tarea ejecutada con éxito (sin salida de texto)."

            await self._send_message(chat_id, response_text, reply_to_id=message_id)
            print(f"\033[32m[TelegramBridge]\033[0m Respuesta enviada a Telegram con éxito.")
        except Exception as exc:
            logger.exception(f"[TelegramBridge] Error procesando tarea: {exc}")
            await self._send_message(
                chat_id,
                f"❌ Error ejecutando la tarea: {exc}",
                reply_to_id=message_id,
            )

    async def _poll_loop(self) -> None:
        """Bucle de polling continuo con reconexión automática."""
        import httpx

        poll_url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        backoff = 1.0

        while self._running:
            try:
                params = {
                    "offset": self._last_update_id + 1,
                    "timeout": 20,
                    "allowed_updates": ["message"],
                }
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(poll_url, params=params)

                if resp.status_code == 200:
                    backoff = 1.0
                    data = resp.json()
                    for update in data.get("result", []):
                        update_id = update.get("update_id", 0)
                        if update_id > self._last_update_id:
                            self._last_update_id = update_id

                        msg = update.get("message")
                        if msg:
                            asyncio.create_task(self._handle_message(msg))
                elif resp.status_code in (401, 404):
                    logger.error(f"[TelegramBridge] Token inválido ({resp.status_code}). Deteniendo.")
                    break
                else:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 1.5, 30.0)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(f"[TelegramBridge] Error en polling: {exc}. Reintentando en {backoff}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)


# Instancia singleton
_bridge_instance: Optional[TelegramBridge] = None


def get_telegram_bridge(dispatch_fn: Optional[Callable] = None) -> TelegramBridge:
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = TelegramBridge(router_dispatch_fn=dispatch_fn)
    elif dispatch_fn and not _bridge_instance.dispatch_fn:
        _bridge_instance.dispatch_fn = dispatch_fn
    return _bridge_instance
