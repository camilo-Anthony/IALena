"""
hermes_scheduler_runner.py — Motor de Ejecución en Segundo Plano del Scheduler de Hermes.

Conecta el sistema nativo de Cron de Hermes (Hermes-Agent/cron/scheduler.py)
con el Kernel de JARVIS, ejecutando periódicamente 'tick()' para despertar
los cron jobs programados y canalizar sus alertas hacia Synapse y la voz del asistente.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from typing import Any, Optional

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_HERMES_DIR = os.path.join(_PROJECT_ROOT, "Hermes-Agent")
if _HERMES_DIR not in sys.path:
    sys.path.insert(0, _HERMES_DIR)


class HermesSchedulerRunner:
    """Ejecutor periódico del scheduler de cron de Hermes."""

    def __init__(
        self,
        synapse: Optional[Any] = None,
        activation_gate: Optional[Any] = None,
        action_router: Optional[Any] = None,
        interval_seconds: float = 60.0,
    ):
        self.synapse = synapse
        self.activation_gate = activation_gate
        self.action_router = action_router
        self.interval_seconds = max(
            15.0,
            float(os.getenv("HERMES_CRON_TICK_SECONDS", str(interval_seconds)))
        )
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_tick_at = 0.0
        self._total_jobs_executed = 0

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """Inicia el bucle periódico de ticks de cron."""
        if self._running:
            return
        self._running = True
        target_loop = loop or asyncio.get_event_loop()
        self._task = target_loop.create_task(self._cron_loop())
        print(f"\033[34m[HermesScheduler]\033[0m Scheduler de Hermes activo (intervalo={self.interval_seconds:.0f}s).")

    def stop(self) -> None:
        """Detiene el bucle de ticks."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None
        print("[HermesScheduler] Scheduler de Hermes detenido.")

    async def _cron_loop(self) -> None:
        # Esperar 10s tras el boot inicial para dar tiempo a que los subsistemas carguen
        await asyncio.sleep(10.0)

        while self._running:
            try:
                await self.tick_now()
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                print(f"[HermesScheduler] Error en bucle de cron: {exc}")
                await asyncio.sleep(self.interval_seconds)

    async def tick_now(self) -> int:
        """Ejecuta una comprobación inmediata de cron jobs vencidos."""
        self._last_tick_at = time.time()
        try:
            from cron.scheduler import tick as hermes_tick

            # Ejecutar el tick en un hilo separado para no bloquear el bucle asyncio
            executed_count = await asyncio.to_thread(hermes_tick, verbose=False)

            if executed_count and executed_count > 0:
                self._total_jobs_executed += executed_count
                print(
                    f"\033[34m[HermesScheduler]\033[0m ¡{executed_count} cron job(s) de Hermes "
                    f"ejecutado(s)! (Total={self._total_jobs_executed})"
                )

                if self.synapse:
                    try:
                        self.synapse.emit(
                            "hermes_cron_executed",
                            {
                                "count": executed_count,
                                "timestamp": self._last_tick_at,
                                "total": self._total_jobs_executed,
                            },
                        )
                    except Exception:
                        pass

                # Despertar y avisar proactivamente si hay un resultado relevante
                if self.activation_gate:
                    self.activation_gate.request_wake(
                        source="hermes_cron",
                        reason="cron_job_finished",
                        priority=60,
                    )

                # Notificar a Telegram / Discord si está configurado
                try:
                    from src.adapters.notifications.remote_notifier import get_remote_notifier
                    notifier = get_remote_notifier()
                    if notifier.is_configured:
                        asyncio.create_task(
                            notifier.notify(
                                message=f"Se completó la ejecución de {executed_count} tarea(s) programada(s) de fondo.",
                                title="⏰ Tarea Programada",
                            )
                        )
                except Exception:
                    pass

            return executed_count or 0

        except ImportError:
            # Hermes cron no está instalado o no se encuentra
            return 0
        except Exception as exc:
            print(f"[HermesScheduler] Error ejecutando cron tick: {exc}")
            return 0

    def get_status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "interval_seconds": self.interval_seconds,
            "last_tick_at": self._last_tick_at,
            "total_jobs_executed": self._total_jobs_executed,
        }
