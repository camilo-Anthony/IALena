"""Contratos del control plane: sólo datos reales de Hermes, sin UI Electron."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from src.server import kernel_bridge


class _AvailableBrain:
    def is_available(self) -> bool:
        return True


class _BrokenBrain:
    def is_available(self) -> bool:
        raise RuntimeError("worker unavailable")


class _ReloadableBrain:
    def reload_slow_worker(self) -> tuple[bool, str]:
        return True, "worker reloaded"


class _KernelWithBrain:
    brain = _ReloadableBrain()


class _BusyReloadableBrain:
    def reload_slow_worker(self) -> tuple[bool, str]:
        return False, "Hay una tarea Hermes SLOW en curso; espera a que termine o cancélala."


class _KernelWithBusyBrain:
    brain = _BusyReloadableBrain()


class TestControlPlane(unittest.TestCase):
    def test_memory_payload_reads_hermes_authoritative_documents(self) -> None:
        home = Path("C:/hermes-profile")
        documents = [
            {"exists": True, "content": "Identity from Hermes", "updated_at": 1.0},
            {"exists": True, "content": "User preference", "updated_at": 2.0},
            {"exists": False, "content": "", "updated_at": None},
        ]
        with (
            patch.object(kernel_bridge, "_get_hermes_home_path", return_value=home),
            patch.object(kernel_bridge, "_read_context_document", side_effect=documents),
            patch.object(Path, "exists", return_value=True),
        ):
            payload = kernel_bridge.get_hermes_memory()

        self.assertTrue(payload["home_ready"])
        self.assertEqual(payload["identity"]["content"], "Identity from Hermes")
        self.assertEqual(payload["user_memory"]["content"], "User preference")
        self.assertFalse(payload["agent_memory"]["exists"])

    def test_worker_availability_is_the_readiness_contract(self) -> None:
        self.assertTrue(kernel_bridge._brain_is_available(_AvailableBrain()))
        self.assertFalse(kernel_bridge._brain_is_available(_BrokenBrain()))
        self.assertFalse(kernel_bridge._brain_is_available(None))

    def test_reload_slow_is_delegated_to_the_adapter(self) -> None:
        with patch.object(kernel_bridge, "_kernel", _KernelWithBrain()):
            payload = kernel_bridge.reload_hermes_slow_worker()

        self.assertTrue(payload["success"])
        self.assertEqual(payload["message"], "worker reloaded")

    def test_reload_slow_preserves_adapter_busy_refusal(self) -> None:
        with patch.object(kernel_bridge, "_kernel", _KernelWithBusyBrain()):
            payload = kernel_bridge.reload_hermes_slow_worker()

        self.assertFalse(payload["success"])
        self.assertIn("tarea Hermes SLOW", payload["message"])
