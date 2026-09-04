"""
tests/test_wake_word_pipeline.py — Pruebas unitarias para el sistema Wake Word y AudioPipeline.

Valida:
  1. RingBuffer: escrituras, lectura de últimos N bytes/ms, wrapping circular.
  2. OpenWakeWordDetector: inicialización, buffering PCM (1280 muestras), histéresis multi-frame, cooldown.
  3. AudioPipeline: flujo en DORMANT vs ACTIVE, inyección de pre-roll, emisión de eventos por Synapse.
"""
import asyncio
import time
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from src.adapters.audio.ring_buffer import RingBuffer
from src.adapters.audio.openwakeword_detector import OpenWakeWordDetector
from src.adapters.audio.audio_pipeline import AudioPipeline
from src.core.interfaces.audio import IAudioCapture
from src.core.interfaces.wake_word import WakeWordResult
from src.kernel.activation_gate import ActivationGate, ActivationState
from src.kernel.synapse import Synapse


class MockAudioCapture(IAudioCapture):
    """Capturador simulado para pruebas de audio en memoria."""
    def __init__(self):
        self.started = False
        self.stopped = False
        self.terminated = False
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.muted = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def terminate(self):
        self.terminated = True

    async def read_chunk(self) -> bytes:
        return await self.queue.get()

    def has_recent_voice(self, window_seconds=None):
        return True

    def reset_recent_voice(self):
        pass


class TestRingBuffer(unittest.TestCase):
    def test_ring_buffer_write_and_read_ms(self):
        # 1 segundo a 16kHz 16-bit mono = 32000 bytes
        rb = RingBuffer(capacity_bytes=32000)
        self.assertEqual(len(rb), 0)

        # Escribir 500 ms de audio (16000 bytes)
        chunk_500ms = b"\x01\x00" * 8000  # 8000 muestras int16 = 16000 bytes
        rb.write(chunk_500ms)
        self.assertEqual(len(rb), 16000)

        # Leer los últimos 250 ms (8000 bytes)
        last_250ms = rb.get_last_ms(250, sample_rate=16000)
        self.assertEqual(len(last_250ms), 8000)
        self.assertEqual(last_250ms, chunk_500ms[-8000:])

    def test_ring_buffer_circular_wrap(self):
        # Buffer de capacidad para 100 bytes
        rb = RingBuffer(capacity_bytes=100)
        # Escribir 80 bytes
        rb.write(b"A" * 80)
        self.assertEqual(len(rb), 80)
        # Escribir 40 bytes más (total 120 -> debe sobreescribir los primeros 20)
        rb.write(b"B" * 40)
        self.assertEqual(len(rb), 100)

        # Los últimos 40 bytes deben ser "B" * 40
        last_40 = rb.get_last_bytes(40)
        self.assertEqual(last_40, b"B" * 40)

        # Los últimos 60 bytes deben ser "A"*20 + "B"*40
        last_60 = rb.get_last_bytes(60)
        self.assertEqual(last_60, b"A" * 20 + b"B" * 40)


class TestOpenWakeWordDetector(unittest.TestCase):
    def test_detector_buffering_and_metrics(self):
        detector = OpenWakeWordDetector(
            model_name="hey_jarvis",
            threshold=0.5,
            consecutive_frames_required=2,
            cooldown_seconds=1.0,
        )

        if not detector.is_ready():
            self.skipTest("openwakeword model files not available in this test environment")

        # Probar que chunks pequeños (< 2560 bytes) se acumulan sin error
        small_chunk = b"\x00" * 512
        res = detector.process_audio(small_chunk)
        self.assertFalse(res.detected)

        # Enviar suficientes bytes para completar al menos 1 frame (1280 muestras = 2560 bytes)
        for _ in range(6):
            res = detector.process_audio(small_chunk)

        # Verificar métricas
        metrics = detector.get_metrics()
        self.assertTrue(metrics["ready"])
        self.assertEqual(metrics["threshold"], 0.5)
        self.assertEqual(metrics["consecutive_frames_required"], 2)
        self.assertIn("hey_jarvis", metrics["models"])

    def test_detector_hysteresis_logic_with_mock_model(self):
        detector = OpenWakeWordDetector(
            model_name="hey_jarvis",
            threshold=0.6,
            consecutive_frames_required=2,
            cooldown_seconds=1.0,
        )

        mock_model = MagicMock()
        detector._model = mock_model
        detector._ready = True
        detector._consecutive_hits = {"hey_jarvis": 0}

        frame_bytes = b"\x00" * 2560

        # Frame 1: score 0.7 (hit 1/2) -> No debe disparar aún
        mock_model.predict.return_value = {"hey_jarvis": 0.7}
        res1 = detector.process_audio(frame_bytes)
        self.assertFalse(res1.detected)
        self.assertEqual(res1.score, 0.7)
        self.assertEqual(detector._consecutive_hits["hey_jarvis"], 1)

        # Frame 2: score 0.8 (hit 2/2) -> Debe disparar Wake Word!
        mock_model.predict.return_value = {"hey_jarvis": 0.8}
        res2 = detector.process_audio(frame_bytes)
        self.assertTrue(res2.detected)
        self.assertEqual(res2.model, "hey_jarvis")
        self.assertEqual(res2.score, 0.8)
        self.assertEqual(detector._total_detections, 1)


class TestAudioPipeline(unittest.IsolatedAsyncioTestCase):
    async def test_audio_pipeline_dormant_to_active_with_preroll(self):
        raw_capture = MockAudioCapture()
        gate = ActivationGate(idle_sleep_seconds=10.0)
        gate.state = ActivationState.DORMANT
        synapse = Synapse()
        synapse.attach_loop(asyncio.get_running_loop())

        # Mock del detector
        mock_detector = MagicMock()
        mock_detector.is_ready.return_value = True
        mock_detector.get_metrics.return_value = {"models": ["hey_jarvis"]}

        pipeline = AudioPipeline(
            raw_capture=raw_capture,
            wake_word_detector=mock_detector,
            activation_gate=gate,
            synapse=synapse,
            pre_roll_ms=500,
            wake_word_enabled=True,
        )

        wake_events = []
        synapse.on("wake_word_detected", lambda payload: wake_events.append(payload))

        pipeline.start()

        # 1. Enviar audio silencioso mientras está DORMANT
        mock_detector.process_audio.return_value = WakeWordResult(detected=False)
        chunk_dummy = b"\x01\x00" * 256  # 512 bytes
        await raw_capture.queue.put(chunk_dummy)

        # Dar tiempo al bucle asíncrono
        await asyncio.sleep(0.05)
        self.assertEqual(gate.state, ActivationState.DORMANT)
        self.assertEqual(len(wake_events), 0)

        # 2. Simular detección de Wake Word
        mock_detector.process_audio.return_value = WakeWordResult(
            detected=True,
            model="hey_jarvis",
            score=0.89,
            processing_ms=12.5,
            frame_index=10,
        )

        wake_chunk = b"\x02\x00" * 256
        await raw_capture.queue.put(wake_chunk)
        await asyncio.sleep(0.05)

        # 3. Validar transición de estado
        self.assertEqual(gate.state, ActivationState.ACTIVE)
        self.assertEqual(len(wake_events), 1)
        self.assertEqual(wake_events[0]["model"], "hey_jarvis")

        # 4. Validar que la cola de salida recibió el Pre-roll + el chunk
        output_chunk_1 = await pipeline.read_chunk()
        self.assertTrue(len(output_chunk_1) > 0)

        metrics = pipeline.get_metrics()
        self.assertEqual(metrics["pre_rolls_injected"], 1)
        self.assertTrue(metrics["last_wake_timestamp"] > 0)

        pipeline.stop()


class TestSerializationAndNumpySafety(unittest.TestCase):
    """Verifica que ningún tipo numpy rompa FastAPI jsonable_encoder ni JSON responses."""

    def test_sanitize_json_obj_numpy_types(self):
        from src.server.kernel_bridge import _sanitize_json_obj
        from fastapi.encoders import jsonable_encoder

        payload = {
            "float32": np.float32(0.8523),
            "float64": np.float64(0.123456),
            "int64": np.int64(42),
            "array": np.array([1.0, 2.0, 3.0], dtype=np.float32),
            "nested": {
                "score": np.float32(0.999),
                "list": [np.float32(0.1), np.float32(0.2)],
            },
        }

        sanitized = _sanitize_json_obj(payload)

        # Debe serializar con FastAPI jsonable_encoder sin error
        encoded = jsonable_encoder(sanitized)
        self.assertIsInstance(encoded["float32"], float)
        self.assertIsInstance(encoded["float64"], float)
        self.assertIsInstance(encoded["int64"], int)
        self.assertIsInstance(encoded["array"], list)
        self.assertIsInstance(encoded["nested"]["score"], float)
        self.assertIsInstance(encoded["nested"]["list"][0], float)

    def test_openwakeword_numpy_scores_types(self):
        from fastapi.encoders import jsonable_encoder

        detector = OpenWakeWordDetector(
            model_name="hey_jarvis",
            threshold=0.5,
            consecutive_frames_required=1,
            cooldown_seconds=0.1,
        )
        mock_model = MagicMock()
        detector._model = mock_model
        detector._ready = True
        detector._consecutive_hits = {"hey_jarvis": 0}

        # Simular que openWakeWord devuelve numpy.float32 (comportamiento real de ONNX)
        mock_model.predict.return_value = {"hey_jarvis": np.float32(0.92)}

        frame_bytes = b"\x00" * 2560
        res = detector.process_audio(frame_bytes)

        self.assertTrue(res.detected)
        self.assertIsInstance(res.score, float)
        self.assertNotEqual(type(res.score), np.float32)
        self.assertIsInstance(res.raw_scores["hey_jarvis"], float)
        self.assertNotEqual(type(res.raw_scores["hey_jarvis"]), np.float32)

        metrics = detector.get_metrics()
        self.assertIsInstance(metrics["avg_score"], float)
        self.assertNotEqual(type(metrics["avg_score"]), np.float32)
        self.assertIsInstance(metrics["last_detected_score"], float)
        self.assertNotEqual(type(metrics["last_detected_score"]), np.float32)

        # Debe serializar directamente sin error con jsonable_encoder
        encoded = jsonable_encoder(metrics)
        self.assertEqual(encoded["last_detected_model"], "hey_jarvis")


if __name__ == "__main__":
    unittest.main()
