import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from src.core.interfaces.brain import IAgentBrain, BrainResult
from src.kernel.action_router import ActionRouter
from src.kernel.synapse import Synapse


class MinimalBrainWithoutAttr(IAgentBrain):
    """Brain de prueba que NO define explícitamente model_brain."""
    async def run_task(self, task: str, event_listener=None) -> BrainResult:
        return BrainResult(f"Respuesta a: {task}", success=True)

    def is_available(self) -> bool:
        return True

    def interrupt(self, reason: str = "") -> None:
        pass


class TestExternalPrompt(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.synapse = Synapse()
        self.synapse.attach_loop(asyncio.get_running_loop())
        self.mock_brain_slow = MinimalBrainWithoutAttr()
        self.mock_brain_fast = MinimalBrainWithoutAttr()
        self.mock_brain_fast.model_brain = "test-fast-model"

        self.router = ActionRouter(
            brain_adapter=self.mock_brain_slow,
            synapse=self.synapse,
            get_session_callback=lambda: None,
            brain_fast=self.mock_brain_fast,
        )

    def test_iagentbrain_default_attributes_and_think_alias(self):
        """Verifica que IAgentBrain exponga model_brain y el método think() como alias."""
        brain = MinimalBrainWithoutAttr()
        self.assertEqual(brain.model_brain, "unknown")
        self.assertTrue(hasattr(brain, "think"))

    async def test_iagentbrain_think_delegates_to_run_task(self):
        brain = MinimalBrainWithoutAttr()
        res = await brain.think("hola")
        self.assertTrue(res.success)
        self.assertEqual(res.text, "Respuesta a: hola")

    async def test_submit_external_prompt_does_not_crash_without_model_brain(self):
        """Verifica que submit_external_prompt no lance AttributeError por model_brain."""
        # Un brain sin atributo model_brain de instancia
        res = await self.router.submit_external_prompt("Hola mundo", source="telegram")
        self.assertIn("Respuesta a: Hola mundo", res)

    async def test_submit_external_prompt_empty(self):
        res = await self.router.submit_external_prompt("", source="telegram")
        self.assertEqual(res, "No se recibió ninguna instrucción.")

    async def test_submit_external_prompt_brain_failure(self):
        failing_brain = MinimalBrainWithoutAttr()
        failing_brain.run_task = AsyncMock(return_value=BrainResult("", success=False, error="Quota exceeded"))
        self.router.brain = failing_brain
        self.router.brain_fast = None

        res = await self.router.submit_external_prompt("buscar algo", source="telegram")
        self.assertIn("⚠️ Error en Hermes: Quota exceeded", res)

    async def test_submit_external_prompt_brain_unavailable(self):
        unavail_brain = MinimalBrainWithoutAttr()
        unavail_brain.is_available = MagicMock(return_value=False)
        self.router.brain = unavail_brain
        self.router.brain_fast = None

        res = await self.router.submit_external_prompt("buscar algo", source="telegram")
        self.assertIn("no está disponible", res)
