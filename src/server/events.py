"""
events.py — WebSocket broadcaster para la UI de JARVIS.

Mantiene una lista de clientes WebSocket conectados y emite
eventos en tiempo real cuando el estado del kernel cambia.
"""
from __future__ import annotations
import asyncio
import json
import time
import logging
from typing import Set, Any

from fastapi import WebSocket

logger = logging.getLogger("JARVIS.events")

# ── Pool de clientes conectados ────────────────────────────────────────────
_clients: Set[WebSocket] = set()
_clients_lock = asyncio.Lock()

# ── Último estado conocido del orbe (para diff) ───────────────────────────
_last_orb_state: str = ""


async def register(ws: WebSocket) -> None:
    async with _clients_lock:
        _clients.add(ws)


async def unregister(ws: WebSocket) -> None:
    async with _clients_lock:
        _clients.discard(ws)


async def broadcast(event_type: str, data: dict[str, Any]) -> None:
    """Emite un evento a todos los clientes conectados."""
    if not _clients:
        return
    payload = json.dumps({
        "type": event_type,
        "ts": time.time(),
        "data": data,
    })
    dead: list[WebSocket] = []
    async with _clients_lock:
        for ws in list(_clients):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            _clients.discard(ws)


# ── Polling loop — emite eventos cuando el estado cambia ──────────────────

async def start_event_loop(poll_interval: float = 0.5) -> None:
    """
    Loop background que detecta cambios de estado y los emite via WebSocket.
    Arranca como tarea asyncio junto al servidor FastAPI.
    """
    global _last_orb_state
    from src.server.kernel_bridge import get_orb_state, get_status, get_tasks, get_logs

    logger.info("[Events] Loop de eventos iniciado.")
    _last_log_ts: float = 0.0

    while True:
        try:
            orb_state = get_orb_state()
            if orb_state != _last_orb_state:
                _last_orb_state = orb_state
                await broadcast("state_change", {"orb_state": orb_state})

            if _clients:
                tasks = get_tasks()
                await broadcast("task_update", tasks)

                # Emitir nuevas entradas de log desde el buffer
                logs = get_logs(200)
                new_logs = [e for e in logs if e.get("ts", 0) > _last_log_ts]
                if new_logs:
                    _last_log_ts = max(e["ts"] for e in new_logs)
                    for entry in new_logs:
                        await broadcast("log_entry", entry)

        except Exception as exc:
            logger.debug(f"[Events] Error en loop: {exc}")

        await asyncio.sleep(poll_interval)

