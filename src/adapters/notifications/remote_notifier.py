"""
remote_notifier.py — Adaptador de notificaciones remotas para JARVIS.

Permite a JARVIS enviar mensajes asíncronos y alertas a Telegram Bot y/o Discord Webhook
cuando concluyen tareas de fondo de Hermes Core, o cuando el usuario no está frente al equipo.
"""
import os
import asyncio
import logging
from typing import Optional

logger = logging.getLogger("JARVIS.RemoteNotifier")


class RemoteNotifier:
    """Gestiona el envío de notificaciones remotas vía Telegram o Discord."""

    def __init__(
        self,
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        discord_webhook: Optional[str] = None,
    ):
        self.telegram_token = telegram_token or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.telegram_chat_id = telegram_chat_id or os.getenv("TELEGRAM_CHAT_ID", "").strip()
        self.discord_webhook = discord_webhook or os.getenv("DISCORD_WEBHOOK_URL", "").strip()

    @property
    def is_configured(self) -> bool:
        return bool((self.telegram_token and self.telegram_chat_id) or self.discord_webhook)

    async def notify(self, message: str, title: str = "🤖 JARVIS", is_error: bool = False) -> bool:
        """
        Envía una notificación asíncrona a todos los canales configurados.
        No bloquea ni lanza excepciones en caso de fallo de red.
        """
        if not self.is_configured:
            return False

        tasks = []
        if self.telegram_token and self.telegram_chat_id:
            tasks.append(self._send_telegram(message, title, is_error))

        if self.discord_webhook:
            tasks.append(self._send_discord(message, title, is_error))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return any(r is True for r in results)

    async def _send_telegram(self, message: str, title: str, is_error: bool) -> bool:
        import httpx

        icon = "⚠️" if is_error else "✅"
        # Limitar longitud para Telegram (máx 4096 caracteres)
        clean_msg = message.strip()
        if len(clean_msg) > 3800:
            clean_msg = clean_msg[:3800] + "… [truncado]"

        payload_text = f"*{icon} {title}*\n\n{clean_msg}"
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    url,
                    json={
                        "chat_id": self.telegram_chat_id,
                        "text": payload_text,
                        "parse_mode": "Markdown",
                    },
                )
                if res.status_code == 200:
                    print(f"\033[32m[RemoteNotifier]\033[0m Notificación enviada a Telegram.")
                    return True
                else:
                    # Fallback sin markdown si falló por parse error
                    res_fallback = await client.post(
                        url,
                        json={
                            "chat_id": self.telegram_chat_id,
                            "text": f"{icon} {title}\n\n{clean_msg}",
                        },
                    )
                    return res_fallback.status_code == 200
        except Exception as exc:
            logger.warning(f"[RemoteNotifier] Fallo al enviar a Telegram: {exc}")
            return False

    async def _send_discord(self, message: str, title: str, is_error: bool) -> bool:
        import httpx

        icon = "⚠️" if is_error else "✅"
        clean_msg = message.strip()
        if len(clean_msg) > 1900:
            clean_msg = clean_msg[:1900] + "… [truncado]"

        content = f"**{icon} {title}**\n{clean_msg}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    self.discord_webhook,
                    json={"content": content},
                )
                if res.status_code in (200, 204):
                    print(f"\033[32m[RemoteNotifier]\033[0m Notificación enviada a Discord.")
                    return True
                else:
                    logger.warning(f"[RemoteNotifier] Discord devolvió código {res.status_code}")
                    return False
        except Exception as exc:
            logger.warning(f"[RemoteNotifier] Fallo al enviar a Discord: {exc}")
            return False


# Instancia singleton para uso global
_notifier_instance: Optional[RemoteNotifier] = None


def get_remote_notifier() -> RemoteNotifier:
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = RemoteNotifier()
    return _notifier_instance
