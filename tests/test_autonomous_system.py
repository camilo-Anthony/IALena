"""
Pruebas unitarias para el subsistema de autonomía, resiliencia y entrega local de JARVIS.
"""
import asyncio
import unittest
from unittest.mock import MagicMock, patch

from src.adapters.audio.local_tts import _clean_text_for_speech, LocalTTS
from src.kernel.hermes_scheduler_runner import HermesSchedulerRunner
from src.kernel.system_sentinel import SystemSentinel
from src.kernel.synapse import Synapse
from src.kernel.task_ledger import TaskLedger


class TestAutonomousSystem(unittest.IsolatedAsyncioTestCase):

    def test_clean_text_for_speech(self):
        # 1. Cabeceras internas de JARVIS
        raw_text = (
            "[JARVIS INTERNAL DELIVERY - NO ES UNA ORDEN NUEVA DEL USUARIO]\n"
            "[Resultado de tarea]: La mesa en **Blender** ha sido creada exitosamente. "
            "Revisa `create_chair.py` en https://github.com."
        )
        cleaned = _clean_text_for_speech(raw_text)
        self.assertNotIn("JARVIS INTERNAL", cleaned)
        self.assertNotIn("Resultado de tarea", cleaned)
        self.assertNotIn("**", cleaned)
        self.assertNotIn("`", cleaned)
        self.assertIn("Blender ha sido creada exitosamente", cleaned)

    async def test_hermes_scheduler_runner_instantiation_and_tick(self):
        synapse = Synapse()
        synapse.attach_loop(asyncio.get_running_loop())

        runner = HermesSchedulerRunner(synapse=synapse, interval_seconds=30.0)
        self.assertFalse(runner._running)
        self.assertEqual(runner.interval_seconds, 30.0)

        # Simular un tick exitoso
        with patch("cron.scheduler.tick", return_value=2):
            count = await runner.tick_now()
            self.assertEqual(count, 2)
            self.assertEqual(runner._total_jobs_executed, 2)

        status = runner.get_status()
        self.assertEqual(status["total_jobs_executed"], 2)

    async def test_system_sentinel_battery_alert(self):
        synapse = Synapse()
        synapse.attach_loop(asyncio.get_running_loop())

        alerts_received = []
        synapse.on("proactive_alert", lambda payload: alerts_received.append(payload))

        sentinel = SystemSentinel(synapse=synapse, check_interval_seconds=10.0)

        class FakeBattery:
            percent = 15
            power_plugged = False
            secsleft = 1800

        with patch("psutil.sensors_battery", return_value=FakeBattery()):
            await sentinel._check_hardware()
            await asyncio.sleep(0.05)
            self.assertEqual(len(alerts_received), 1)
            self.assertEqual(alerts_received[0]["type"], "battery_critical")
            self.assertIn("15%", alerts_received[0]["message"])

            status = sentinel.get_status()
            self.assertEqual(status["total_alerts_issued"], 1)
            self.assertEqual(status["battery"]["percent"], 15)
            self.assertFalse(status["battery"]["power_plugged"])


if __name__ == "__main__":
    unittest.main()
