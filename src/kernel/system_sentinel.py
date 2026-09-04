"""
system_sentinel.py — Centinela Autónomo Proactivo del Sistema para JARVIS.

Monitorea continuamente el hardware y entorno operativo (batería, alimentación, recursos)
e inicia alertas proactivas a través de Synapse y el canal de voz/texto sin requerir
que el usuario diga "Hey Jarvis".
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Optional

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False


class SystemSentinel:
    """Centinela proactivo de hardware y sistema operativo."""

    def __init__(
        self,
        synapse: Optional[Any] = None,
        activation_gate: Optional[Any] = None,
        action_router: Optional[Any] = None,
        local_tts: Optional[Any] = None,
        check_interval_seconds: float = 15.0,
    ):
        self.synapse = synapse
        self.activation_gate = activation_gate
        self.action_router = action_router
        self.local_tts = local_tts

        self.check_interval_seconds = max(
            5.0,
            float(os.getenv("SENTINEL_CHECK_INTERVAL_SECONDS", str(check_interval_seconds)))
        )
        self.battery_alert_threshold = int(os.getenv("SENTINEL_BATTERY_LOW_THRESHOLD", "20"))
        self.battery_emergency_threshold = int(os.getenv("SENTINEL_BATTERY_EMERGENCY_THRESHOLD", "10"))
        self.cooldown_seconds = float(os.getenv("SENTINEL_ALERT_COOLDOWN_SECONDS", "300.0"))

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_battery_alert_time = 0.0
        self._last_known_power_plugged: Optional[bool] = None
        self._last_battery_percent: Optional[int] = None
        self._total_alerts_issued = 0

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """Inicia el bucle centinela."""
        if self._running or not _PSUTIL_AVAILABLE:
            return
        self._running = True
        target_loop = loop or asyncio.get_event_loop()
        self._task = target_loop.create_task(self._sentinel_loop())
        print(f"\033[32m[SystemSentinel]\033[0m Centinela del sistema activo (intervalo={self.check_interval_seconds:.0f}s).")

    def stop(self) -> None:
        """Detiene el bucle centinela."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None
        print("[SystemSentinel] Centinela del sistema detenido.")

    async def _sentinel_loop(self) -> None:
        # Espera inicial de estabilización
        await asyncio.sleep(5.0)

        while self._running:
            try:
                await self._check_hardware()
                await asyncio.sleep(self.check_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                print(f"[SystemSentinel] Error en bucle centinela: {exc}")
                await asyncio.sleep(self.check_interval_seconds)

    async def _check_hardware(self) -> None:
        if not _PSUTIL_AVAILABLE:
            return

        try:
            battery = psutil.sensors_battery()
            if battery is None:
                return

            percent = int(battery.percent)
            plugged = bool(battery.power_plugged)
            now = time.time()

            # 1. Notificar cambio de estado del cargador (desconexión)
            if self._last_known_power_plugged is True and plugged is False and percent <= 35:
                msg = f"Aviso: el cargador ha sido desconectado. Nivel de batería al {percent}%."
                await self._dispatch_proactive_alert(
                    msg,
                    alert_type="power_disconnected",
                    priority=50,
                )

            # 2. Alerta de batería crítica (< 20% y sin cargador)
            is_critical = percent <= self.battery_alert_threshold and not plugged
            is_emergency = percent <= self.battery_emergency_threshold and not plugged
            time_since_last_alert = now - self._last_battery_alert_time

            should_alert = False
            if is_emergency and time_since_last_alert >= 120.0:
                should_alert = True
                msg = f"¡Atención urgente señor! La batería está crítica al {percent}%. Por favor conecte el cargador de inmediato."
            elif is_critical and time_since_last_alert >= self.cooldown_seconds:
                should_alert = True
                msg = f"Señor, le informo que la batería ha bajado al {percent}% y el equipo no está conectado a la corriente."

            if should_alert:
                self._last_battery_alert_time = now
                self._total_alerts_issued += 1
                await self._dispatch_proactive_alert(
                    msg,
                    alert_type="battery_critical",
                    priority=80 if is_emergency else 65,
                )

            self._last_known_power_plugged = plugged
            self._last_battery_percent = percent

        except Exception as exc:
            print(f"[SystemSentinel] Error comprobando sensores: {exc}")

    async def _dispatch_proactive_alert(self, message: str, alert_type: str, priority: int) -> None:
        print(f"\033[93m[SystemSentinel] [ALERTA PROACTIVA]\033[0m {message}")

        # 1. Emitir evento por Synapse
        if self.synapse:
            try:
                self.synapse.emit(
                    "proactive_alert",
                    {
                        "type": alert_type,
                        "message": message,
                        "priority": priority,
                        "timestamp": time.time(),
                    },
                )
            except Exception:
                pass

        # 2. Despertar ActivationGate para permitir salida de audio
        if self.activation_gate:
            self.activation_gate.request_wake(
                source="sentinel",
                reason=alert_type,
                priority=priority,
            )

        # 3. Intentar entrega a través del ActionRouter
        delivered = False
        if self.action_router and hasattr(self.action_router, "deliver_proactive_speech"):
            delivered = await self.action_router.deliver_proactive_speech(message, priority=priority)

        # 4. Fallback directo a LocalTTS si ActionRouter no pudo entregar
        if not delivered and self.local_tts and hasattr(self.local_tts, "speak"):
            await self.local_tts.speak(message, non_blocking=True)

    def get_status(self) -> dict[str, Any]:
        battery_data = None
        if _PSUTIL_AVAILABLE:
            try:
                b = psutil.sensors_battery()
                if b:
                    battery_data = {
                        "percent": int(b.percent),
                        "power_plugged": bool(b.power_plugged),
                        "seconds_left": b.secsleft if b.secsleft >= 0 else None,
                    }
            except Exception:
                pass

        return {
            "running": self._running,
            "check_interval_seconds": self.check_interval_seconds,
            "total_alerts_issued": self._total_alerts_issued,
            "last_alert_time": self._last_battery_alert_time,
            "battery": battery_data,
        }
