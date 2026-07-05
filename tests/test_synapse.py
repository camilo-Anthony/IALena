import unittest
import asyncio
import os
import time
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from google.genai import types

from src.kernel.synapse import Synapse, TurnState
from src.kernel.action_router import ActionRouter
from src.kernel.context_manager import ContextManager
from src.kernel.activation_gate import ActivationGate, ActivationState
from src.kernel.cognitive_policy import CognitivePolicy
from src.kernel.conversation_session import ConversationSessionManager, SessionMemoryConsolidator
from src.kernel.task_ledger import TaskLedger, TaskStatus
from src.core.interfaces.brain import IAgentBrain, BrainResult
from src.adapters.llm import gemini_live_adapter as live_module

class FakeBrain(IAgentBrain):
    def __init__(self):
        self.is_interrupted = False
        self.delay = 0.1
        self.result_text = "Éxito"
        self.next_result = None
        self.run_count = 0
        self.running = 0
        self.max_running = 0
        self.tasks = []

    async def run_task(self, task: str, event_listener=None) -> BrainResult:
        self.tasks.append(task)
        self.run_count += 1
        self.running += 1
        self.max_running = max(self.max_running, self.running)
        try:
            return await self._run_task(task, event_listener)
        finally:
            self.running -= 1

    async def _run_task(self, task: str, event_listener=None) -> BrainResult:
        if self.is_interrupted:
            return BrainResult("", success=False, interrupted=True)
            
        await asyncio.sleep(self.delay)
        
        if self.is_interrupted:
            return BrainResult("", success=False, interrupted=True)
            
        if event_listener:
            event_listener("tool_start", "123", "fake_tool", {})

        if self.next_result is not None:
            return self.next_result
            
        return BrainResult(self.result_text, success=True)

    def is_available(self) -> bool:
        return True

    def interrupt(self, reason: str = "") -> None:
        self.is_interrupted = True


class TestHermesAdapterConfig(unittest.TestCase):
    def test_parse_csv_env_strips_empty_items_and_deduplicates(self):
        from src.adapters.brain import hermes_adapter as hermes_module

        with patch.dict(os.environ, {"TEST_TOOLSETS": " web, file ; web ,,terminal "}):
            self.assertEqual(
                hermes_module._parse_csv_env("TEST_TOOLSETS"),
                ["web", "file", "terminal"],
            )

    def test_hermes_adapter_passes_toolset_config_to_aiagent(self):
        from src.adapters.brain import hermes_adapter as hermes_module

        class FakeAIAgent:
            kwargs = None

            def __init__(self, **kwargs):
                type(self).kwargs = kwargs
                self._skill_nudge_interval = 1

        env = {
            "HERMES_ENABLED_TOOLSETS": "web,file,terminal",
            "HERMES_DISABLED_TOOLSETS": "spotify;discord",
            "HERMES_PLATFORM": "cli",
            "USER_NAME": "Camilo",
            "HERMES_LOAD_SOUL_IDENTITY": "1",
            "HERMES_SKIP_CONTEXT_FILES": "0",
            "HERMES_SKIP_MEMORY": "0",
            "HERMES_PASS_SESSION_ID": "1",
        }

        with (
            patch.dict(os.environ, env),
            patch.object(hermes_module, "AIAgent", FakeAIAgent),
            patch.object(hermes_module, "start_proxy", return_value=8765),
        ):
            adapter = hermes_module.HermesAdapter(["k1"], "gemini-test")

        self.assertTrue(adapter.is_available())
        self.assertEqual(adapter.hermes_agent._skill_nudge_interval, 0)
        self.assertEqual(FakeAIAgent.kwargs["enabled_toolsets"], ["web", "file", "terminal"])
        self.assertEqual(FakeAIAgent.kwargs["disabled_toolsets"], ["spotify", "discord"])
        self.assertEqual(FakeAIAgent.kwargs["platform"], "cli")
        self.assertEqual(FakeAIAgent.kwargs["user_name"], "Camilo")
        self.assertTrue(FakeAIAgent.kwargs["load_soul_identity"])
        self.assertFalse(FakeAIAgent.kwargs["skip_context_files"])
        self.assertFalse(FakeAIAgent.kwargs["skip_memory"])
        self.assertTrue(FakeAIAgent.kwargs["pass_session_id"])

    def test_runtime_config_uses_platform_toolsets_when_no_explicit_enabled_list(self):
        from src.adapters.brain import hermes_adapter as hermes_module

        env = {
            "HERMES_ENABLED_TOOLSETS": "",
            "HERMES_DISABLED_TOOLSETS": "spotify",
            "HERMES_PLATFORM": "cli",
            "USER_NAME": "Camilo",
        }

        with (
            patch.dict(os.environ, env),
            patch.object(hermes_module, "_resolve_platform_toolsets", return_value=["web", "file"]) as resolver,
        ):
            config = hermes_module._read_runtime_config()

        resolver.assert_called_once_with("cli")
        self.assertEqual(config["enabled_toolsets"], ["web", "file"])
        self.assertEqual(config["disabled_toolsets"], ["spotify"])
        self.assertEqual(config["platform"], "cli")


class TestSynapseAndRouter(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.synapse = Synapse()
        self.synapse.attach_loop(asyncio.get_running_loop())
        self.brain = FakeBrain()
        self.action_router = ActionRouter(
            brain_adapter=self.brain,
            synapse=self.synapse,
            get_session_callback=lambda: None,
            is_busy_callback=lambda: False
        )
        self.action_router._delivery_idle_seconds = 0.01
        self.action_router._delivery_poll_seconds = 0.01
        self.action_router._delivery_log_seconds = 60.0
        self.action_router._delivery_max_wait_seconds = 60.0

    async def test_synapse_creates_turns(self):
        turn = self.synapse.create_turn("Hola")
        self.assertIsNotNone(turn.turn_id)
        self.assertEqual(self.synapse.active_turn, turn)
        self.assertEqual(turn.state, TurnState.LISTENING)

    async def test_synapse_event_routing(self):
        event_data = []
        
        def on_event(t, old, new):
            event_data.append(new)
            
        self.synapse.subscribe("turn_state_changed", on_event)
        
        turn = self.synapse.create_turn("Test")
        self.synapse.change_state(TurnState.THINKING, turn_id=turn.turn_id)
        
        await asyncio.sleep(0.01)
        self.assertIn(TurnState.THINKING, event_data)

    async def test_synapse_ignores_old_turn(self):
        turn1 = self.synapse.create_turn("Old")
        turn2 = self.synapse.create_turn("New")
        
        self.synapse.change_state(TurnState.COMPLETED, turn_id=turn1.turn_id)
        
        self.assertEqual(self.synapse.active_turn, turn2)
        self.assertEqual(self.synapse.active_turn.state, TurnState.LISTENING)
        self.assertEqual(turn1.state, TurnState.COMPLETED)

    async def test_action_router_cooperative_cancellation(self):
        self.brain.delay = 0.2
        task1 = asyncio.create_task(
            self.action_router.run_hermes("1", "test", "Prueba larga")
        )
        
        await asyncio.sleep(0.05)
        self.assertIn(self.action_router.synapse.active_turn.state, [TurnState.THINKING, TurnState.ACKNOWLEDGING, TurnState.BRAIN_RUNNING])
        
        await self.action_router.interrupt_active_turn("Nuevo user input")
        
        await task1
            
        self.assertEqual(self.action_router.synapse.active_turn.state, TurnState.INTERRUPTED)
        self.assertTrue(self.brain.is_interrupted)

    async def test_action_router_interruption_timeout(self):
        self.brain.delay = 10.0
        
        original_wait_for = asyncio.wait_for
        async def mock_wait_for(aw, timeout):
            return await original_wait_for(aw, timeout=0.1)
        
        import src.kernel.action_router as ar_module
        ar_module.asyncio.wait_for = mock_wait_for
        
        task1 = asyncio.create_task(
            self.action_router.run_hermes("1", "test", "Prueba timeout")
        )
        
        await asyncio.sleep(0.05)
        await self.action_router.interrupt_active_turn("Timeout provocado")
        
        await task1
            
        self.assertEqual(self.action_router.synapse.active_turn.state, TurnState.STALE)
        ar_module.asyncio.wait_for = original_wait_for

    async def test_action_router_success_flow(self):
        self.brain.delay = 0.05
        
        session_mock = AsyncMock()
        self.action_router.get_session = lambda: session_mock
        
        await self.action_router.run_hermes("1", "test", "Prueba rápida")
        
        self.assertEqual(self.action_router.synapse.active_turn.state, TurnState.COMPLETED)
        self.assertIsNotNone(self.action_router.synapse.active_turn.brain_result)
        self.assertEqual(self.action_router.synapse.active_turn.brain_result.text, "Éxito")
        session_mock.send_client_content.assert_called_once()

    async def test_result_delivery_waits_for_natural_idle_slot(self):
        self.brain.delay = 0.01
        busy = {"value": True}
        recent_voice = {"value": True}
        session_mock = AsyncMock()
        self.action_router.get_session = lambda: session_mock
        self.action_router.is_busy = lambda: busy["value"]
        self.action_router.has_recent_voice = lambda window=None: recent_voice["value"]
        self.action_router._delivery_idle_seconds = 0.03

        task = asyncio.create_task(
            self.action_router.run_hermes("1", "test", "Prueba con entrega diferida")
        )

        for _ in range(20):
            if self.action_router.synapse.active_turn and self.action_router.synapse.active_turn.state == TurnState.INJECTING_RESULT:
                break
            await asyncio.sleep(0.01)

        self.assertEqual(self.action_router.synapse.active_turn.state, TurnState.INJECTING_RESULT)
        session_mock.send_client_content.assert_not_called()

        busy["value"] = False
        await asyncio.sleep(0.06)
        session_mock.send_client_content.assert_not_called()

        recent_voice["value"] = False
        await task

        session_mock.send_client_content.assert_called_once()
        self.assertEqual(self.action_router.synapse.active_turn.state, TurnState.COMPLETED)

    async def test_result_delivery_forces_after_max_wait_when_voice_stays_recent(self):
        self.brain.delay = 0.01
        session_mock = AsyncMock()
        self.action_router.get_session = lambda: session_mock
        self.action_router.is_busy = lambda: False
        self.action_router.has_recent_voice = lambda window=None: True
        self.action_router._delivery_max_wait_seconds = 0.04

        await asyncio.wait_for(
            self.action_router.run_hermes("1", "test", "Prueba con voz reciente pegada"),
            timeout=1.0,
        )

        session_mock.send_client_content.assert_called_once()
        self.assertEqual(self.action_router.synapse.active_turn.state, TurnState.COMPLETED)

    async def test_busy_tool_call_is_acknowledged_without_second_brain_run(self):
        self.brain.delay = 0.2
        session_mock = AsyncMock()
        self.action_router.get_session = lambda: session_mock

        self.assertTrue(self.action_router.reserve_tool_call())
        task1 = asyncio.create_task(
            self.action_router.run_hermes("1", "test", "Prueba larga")
        )

        await asyncio.sleep(0.05)
        self.assertFalse(self.action_router.can_accept_tool_call())
        await self.action_router.reject_busy_tool_call("2", "test")
        await task1

        self.assertEqual(self.brain.run_count, 1)
        self.assertLessEqual(self.brain.max_running, 1)
        self.assertGreaterEqual(session_mock.send_tool_response.call_count, 2)
        busy_response = session_mock.send_tool_response.call_args_list[-1].kwargs["function_responses"][0].response
        self.assertIn("Puedo atender cosas simples", busy_response["mensaje"])
        self.assertEqual(self.action_router.synapse.active_turn.state, TurnState.COMPLETED)
        self.assertFalse(self.brain.is_interrupted)

    async def test_busy_hermes_tool_call_can_be_queued_without_parallel_brain_run(self):
        ledger = TaskLedger()
        self.action_router.task_ledger = ledger
        self.brain.delay = 0.05
        session_mock = AsyncMock()
        self.action_router.get_session = lambda: session_mock

        self.assertTrue(self.action_router.reserve_tool_call())
        task1 = asyncio.create_task(
            self.action_router.run_hermes("1", "test", "Primera tarea larga")
        )

        for _ in range(20):
            if self.action_router.synapse.active_turn and self.action_router.synapse.active_turn.state == TurnState.BRAIN_RUNNING:
                break
            await asyncio.sleep(0.01)

        queued = await self.action_router.queue_hermes_tool_call("2", "test", "Segunda tarea en cola")
        self.assertTrue(queued)
        self.assertEqual(len(ledger.pending_tasks("hermes")), 1)

        await task1
        for _ in range(40):
            if self.brain.run_count >= 2 and ledger.recent_tasks(2)[-1].status == TaskStatus.COMPLETED:
                break
            await asyncio.sleep(0.01)

        self.assertEqual(self.brain.run_count, 2)
        self.assertLessEqual(self.brain.max_running, 1)
        self.assertEqual([task.status for task in ledger.recent_tasks(2)], [TaskStatus.COMPLETED, TaskStatus.COMPLETED])
        self.assertEqual(ledger.recent_tasks(2)[1].prompt, "Segunda tarea en cola")
        queued_response = session_mock.send_tool_response.call_args_list[1].kwargs["function_responses"][0].response
        self.assertEqual(queued_response["status"], "en_cola")

    async def test_task_status_payload_reports_running_and_pending_queue(self):
        ledger = TaskLedger()
        self.action_router.task_ledger = ledger
        running = ledger.create_task("hermes", "Primera tarea")
        queued = ledger.create_task("hermes", "Segunda tarea")
        ledger.mark_running(running, turn_id="turn-1")

        payload = self.action_router.task_status_payload()

        self.assertEqual(payload["status"], "running")
        self.assertTrue(payload["active"])
        self.assertEqual(payload["pending"], 1)
        self.assertEqual(queued.status, TaskStatus.PENDING)
        self.assertIn("Sigo trabajando", payload["message"])

    async def test_task_status_tool_call_responds_without_brain_run(self):
        ledger = TaskLedger()
        self.action_router.task_ledger = ledger
        ledger.create_task("hermes", "Tarea pendiente")
        session_mock = AsyncMock()
        self.action_router.get_session = lambda: session_mock

        await self.action_router.send_task_status_tool_call("status-1", "consultar_estado_tareas")

        self.assertEqual(self.brain.run_count, 0)
        session_mock.send_tool_response.assert_called_once()
        response = session_mock.send_tool_response.call_args.kwargs["function_responses"][0].response
        self.assertEqual(response["status"], "queued")
        self.assertEqual(response["pending"], 1)

    async def test_today_summary_tool_call_uses_local_state_and_agenda(self):
        ledger = TaskLedger()
        self.action_router.task_ledger = ledger
        ledger.create_task("hermes", "Tarea pendiente")
        session_mock = AsyncMock()
        self.action_router.get_session = lambda: session_mock

        with tempfile.TemporaryDirectory() as tmp:
            today = self.action_router._today_iso()
            agenda_path = os.path.join(tmp, "agenda.txt")
            with open(agenda_path, "w", encoding="utf-8") as handle:
                handle.write(f"{today} reunion de prueba\n")
            with patch.dict(os.environ, {"JARVIS_AGENDA_FILE": agenda_path}):
                await self.action_router.send_today_summary_tool_call("today-1", "consultar_resumen_hoy")

        self.assertEqual(self.brain.run_count, 0)
        session_mock.send_tool_response.assert_called_once()
        response = session_mock.send_tool_response.call_args.kwargs["function_responses"][0].response
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["task_status"]["pending"], 1)
        self.assertIn("reunion de prueba", response["agenda_items"][0])

    async def test_cancel_tool_call_interrupts_active_brain_run(self):
        self.brain.delay = 0.2
        session_mock = AsyncMock()
        self.action_router.get_session = lambda: session_mock

        self.assertTrue(self.action_router.reserve_tool_call())
        task1 = asyncio.create_task(
            self.action_router.run_hermes("1", "test", "Prueba larga")
        )

        await asyncio.sleep(0.05)
        await self.action_router.cancel_active_tool_call("cancel-1", "cancelar_tarea_hermes")
        await task1

        self.assertEqual(self.brain.run_count, 1)
        self.assertTrue(self.brain.is_interrupted)
        self.assertEqual(self.action_router.synapse.active_turn.state, TurnState.INTERRUPTED)
        self.assertGreaterEqual(session_mock.send_tool_response.call_count, 2)

    async def test_cancel_tool_call_cancels_pending_task_when_no_active_work(self):
        ledger = TaskLedger()
        self.action_router.task_ledger = ledger
        pending = ledger.create_task("hermes", "Tarea pendiente")
        session_mock = AsyncMock()
        self.action_router.get_session = lambda: session_mock

        await self.action_router.cancel_active_tool_call("cancel-1", "cancelar_tarea_hermes")

        self.assertEqual(pending.status, TaskStatus.INTERRUPTED)
        self.assertEqual(self.brain.run_count, 0)
        session_mock.send_tool_response.assert_called_once()
        response = session_mock.send_tool_response.call_args.kwargs["function_responses"][0].response
        self.assertEqual(response["status"], "cancelada_pendiente")

    async def test_reservation_blocks_second_tool_call_before_turn_exists(self):
        session_mock = AsyncMock()
        self.action_router.get_session = lambda: session_mock

        self.assertTrue(self.action_router.reserve_tool_call())
        self.assertFalse(self.action_router.can_accept_tool_call())
        self.assertFalse(self.action_router.reserve_tool_call())

        await self.action_router.reject_busy_tool_call("2", "test")

        self.assertEqual(self.brain.run_count, 0)
        session_mock.send_tool_response.assert_called_once()

    async def test_stale_running_task_blocks_new_tool_call(self):
        turn = self.synapse.create_turn("Stale draining")
        turn.brain_task = asyncio.create_task(asyncio.sleep(60))
        self.synapse.change_state(TurnState.STALE, turn_id=turn.turn_id)

        self.assertTrue(self.action_router.has_unfinished_brain_task())
        self.assertFalse(self.action_router.can_accept_tool_call())
        self.assertFalse(self.action_router.reserve_tool_call())

        turn.brain_task.cancel()
        try:
            await turn.brain_task
        except asyncio.CancelledError:
            pass

        self.assertFalse(self.action_router.has_unfinished_brain_task())
        self.assertTrue(self.action_router.can_accept_tool_call())

    async def test_run_hermes_does_not_start_over_stale_running_task(self):
        session_mock = AsyncMock()
        self.action_router.get_session = lambda: session_mock
        turn = self.synapse.create_turn("Stale draining")
        turn.brain_task = asyncio.create_task(asyncio.sleep(60))
        self.synapse.change_state(TurnState.STALE, turn_id=turn.turn_id)

        await self.action_router.run_hermes("2", "test", "Nueva orden")

        self.assertEqual(self.synapse.active_turn, turn)
        self.assertEqual(turn.state, TurnState.STALE)
        self.assertEqual(self.brain.run_count, 0)
        session_mock.send_tool_response.assert_called_once()

        turn.brain_task.cancel()
        try:
            await turn.brain_task
        except asyncio.CancelledError:
            pass

    async def test_interrupt_acknowledging_without_brain_task_does_not_hang(self):
        turn = self.synapse.create_turn("Ack")
        self.synapse.change_state(TurnState.ACKNOWLEDGING, turn_id=turn.turn_id)

        await self.action_router.interrupt_active_turn("Interrupción durante ACK")

        self.assertEqual(turn.state, TurnState.INTERRUPTED)
        self.assertTrue(self.brain.is_interrupted)

    async def test_interrupt_injecting_result_without_brain_task_does_not_hang(self):
        turn = self.synapse.create_turn("Inject")
        self.synapse.change_state(TurnState.INJECTING_RESULT, turn_id=turn.turn_id)

        await self.action_router.interrupt_active_turn("Interrupción durante inyección")

        self.assertEqual(turn.state, TurnState.INTERRUPTED)
        self.assertTrue(self.brain.is_interrupted)

    async def test_failed_brain_result_is_not_injected_as_normal_result(self):
        self.brain.delay = 0.01
        self.brain.next_result = BrainResult("", success=False, error="boom")
        session_mock = AsyncMock()
        self.action_router.get_session = lambda: session_mock

        await self.action_router.run_hermes("1", "test", "Falla controlada")

        self.assertEqual(self.action_router.synapse.active_turn.state, TurnState.FAILED)
        session_mock.send_client_content.assert_called_once()
        sent_text = session_mock.send_client_content.call_args.kwargs["turns"][0].parts[0].text
        self.assertIn("[Fallo de tarea interna]", sent_text)
        self.assertNotIn("[Resultado de tu búsqueda interna]", sent_text)

    def test_hermes_prompt_guides_music_requests_to_local_youtube_script(self):
        prompt = self.action_router._build_hermes_prompt("pon C.R.E.A.M. de Wu-Tang Clan en YouTube")

        self.assertIn("CAPACIDAD LOCAL - MUSICA/YOUTUBE", prompt)
        self.assertIn("play_yt.py", prompt)
        self.assertIn("herramienta terminal", prompt)
        self.assertIn("No uses memory, todo ni session_search", prompt)
        self.assertIn("Listo, lo abri en YouTube", prompt)

    def test_hermes_prompt_does_not_add_youtube_guidance_for_normal_tasks(self):
        prompt = self.action_router._build_hermes_prompt("lista de pendientes para hoy")

        self.assertNotIn("CAPACIDAD LOCAL - MUSICA/YOUTUBE", prompt)
        self.assertNotIn("play_yt.py", prompt)

    def test_live_prompt_keeps_voice_barge_in_separate_from_cancel(self):
        context_manager = ContextManager("JARVIS", "Usuario", "Aoede")
        instruction = context_manager.get_base_instruction()

        self.assertIn("responder preguntas simples", instruction)
        self.assertIn("Una interrupción de voz NO significa cancelar", instruction)
        self.assertIn("Solo usa 'cancelar_tarea_hermes'", instruction)
        self.assertIn("NO respondas el contenido", instruction)
        self.assertIn("IDENTIDAD, MEMORIA Y APRENDIZAJE", instruction)
        self.assertIn("cerebro principal", instruction)
        self.assertIn("No asumas que una pausa breve", instruction)
        self.assertIn("consultar_estado_tareas", instruction)
        self.assertIn("consultar_resumen_hoy", instruction)
        self.assertIn("dejara en cola", instruction)

    def test_live_config_uses_less_aggressive_voice_endpointing(self):
        context_manager = ContextManager("JARVIS", "Usuario", "Aoede")
        config = context_manager.get_live_config()

        realtime_config = config.realtime_input_config
        activity_detection = realtime_config.automatic_activity_detection

        self.assertEqual(activity_detection.silence_duration_ms, 1400)
        self.assertEqual(activity_detection.prefix_padding_ms, 300)
        self.assertEqual(
            activity_detection.start_of_speech_sensitivity,
            types.StartSensitivity.START_SENSITIVITY_HIGH,
        )
        self.assertEqual(
            activity_detection.end_of_speech_sensitivity,
            types.EndSensitivity.END_SENSITIVITY_LOW,
        )
        self.assertEqual(
            realtime_config.activity_handling,
            types.ActivityHandling.START_OF_ACTIVITY_INTERRUPTS,
        )

    def test_live_config_omits_direct_music_tool_when_disabled(self):
        with patch.dict(os.environ, {"ENABLE_MUSIC_TOOL": "0"}):
            context_manager = ContextManager("JARVIS", "Usuario", "Aoede")
            config = context_manager.get_live_config()
            instruction = context_manager.get_base_instruction()

        function_names = [
            declaration.name
            for tool in config.tools
            for declaration in tool.function_declarations
        ]

        self.assertIn("ejecutar_hermes_core", function_names)
        self.assertIn("cancelar_tarea_hermes", function_names)
        self.assertIn("consultar_estado_tareas", function_names)
        self.assertIn("consultar_resumen_hoy", function_names)
        self.assertNotIn("reproducir_musica_youtube", function_names)
        self.assertIn("herramienta directa de YouTube está desactivada", instruction)
        self.assertIn("delega a 'ejecutar_hermes_core'", instruction)

    def test_hermes_context_injection_is_bounded_and_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            memories_dir = os.path.join(tmp, "memories")
            skills_dir = os.path.join(tmp, "skills")
            os.makedirs(memories_dir)
            os.makedirs(os.path.join(skills_dir, "alpha"))
            os.makedirs(os.path.join(skills_dir, "beta"))
            with open(os.path.join(tmp, "SOUL.md"), "w", encoding="utf-8") as f:
                f.write("Soy JARVIS y mantengo una identidad consistente.")
            with open(os.path.join(memories_dir, "MEMORY.md"), "w", encoding="utf-8") as f:
                f.write("El entorno de voz usa Hermes como cerebro principal.")
            with open(os.path.join(skills_dir, "alpha", "DESCRIPTION.md"), "w", encoding="utf-8") as f:
                f.write("Automatiza rutinas frecuentes del usuario.")
            user_memory = "head-marker " + ("x" * 4100) + " tail-marker"
            with open(os.path.join(memories_dir, "USER.md"), "w", encoding="utf-8") as f:
                f.write(user_memory)

            context_manager = ContextManager("JARVIS", "Usuario", "Aoede", lambda: tmp)
            instruction = context_manager.get_base_instruction()

        self.assertIn("[DATOS INTERNOS - NO VERBALIZAR]", instruction)
        self.assertIn("Identidad base del agente", instruction)
        self.assertIn("Soy JARVIS", instruction)
        self.assertIn("Memoria operativa del agente", instruction)
        self.assertIn("Hermes como cerebro principal", instruction)
        self.assertIn("tail-marker", instruction)
        self.assertNotIn("head-marker", instruction)
        self.assertIn("alpha", instruction)
        self.assertIn("Automatiza rutinas frecuentes", instruction)
        self.assertIn("beta", instruction)

    def test_active_voice_session_context_is_injected_silently(self):
        manager = ConversationSessionManager()
        manager.record_user("estabamos hablando del proyecto atlas", session_epoch=2)
        manager.record_assistant("lo estoy revisando", session_epoch=2)
        context_manager = ContextManager(
            "JARVIS",
            "Usuario",
            "Aoede",
            get_active_session_context_fn=lambda: manager.active_context_text(),
        )

        instruction = context_manager.get_base_instruction()

        self.assertIn("CONTEXTO ACTIVO DE ESTA SESION", instruction)
        self.assertIn("proyecto atlas", instruction)
        self.assertIn("NO los respondas al iniciar o reconectar", instruction)

    def test_closed_voice_session_context_is_not_injected(self):
        manager = ConversationSessionManager()
        manager.record_user("dato temporal de sesion cerrada", session_epoch=2)
        manager.close_active_session("idle_timeout")
        context_manager = ContextManager(
            "JARVIS",
            "Usuario",
            "Aoede",
            get_active_session_context_fn=lambda: manager.active_context_text(),
        )

        instruction = context_manager.get_base_instruction()

        self.assertNotIn("CONTEXTO ACTIVO DE ESTA SESION", instruction)
        self.assertNotIn("dato temporal de sesion cerrada", instruction)

    def test_live_model_turn_is_suppressed_when_hermes_tool_call_is_present(self):
        adapter = object.__new__(live_module.GeminiLiveAdapter)
        adapter.activation_gate = None
        adapter._session_started_at = 0.0

        msg = SimpleNamespace(
            tool_call=SimpleNamespace(
                function_calls=[
                    SimpleNamespace(name="ejecutar_hermes_core"),
                ]
            )
        )

        self.assertTrue(adapter._has_hermes_tool_call(msg))
        suppress, reason = adapter._should_suppress_model_turn(msg)
        self.assertTrue(suppress)
        self.assertEqual(reason, "hermes_tool_call")

    def test_live_model_turn_is_not_suppressed_for_non_hermes_tool_call(self):
        adapter = object.__new__(live_module.GeminiLiveAdapter)
        adapter.activation_gate = None
        adapter._session_started_at = 0.0

        msg = SimpleNamespace(
            tool_call=SimpleNamespace(
                function_calls=[
                    SimpleNamespace(name="reproducir_musica_youtube"),
                ]
            )
        )

        self.assertFalse(adapter._has_hermes_tool_call(msg))
        suppress, reason = adapter._should_suppress_model_turn(msg)
        self.assertFalse(suppress)
        self.assertEqual(reason, "")

    def test_live_claiming_response_for_hermes_flushes_playback(self):
        class Playback:
            def __init__(self):
                self.flushed = False

            def flush(self):
                self.flushed = True

        adapter = object.__new__(live_module.GeminiLiveAdapter)
        adapter.playback = Playback()

        adapter._claim_response_for_hermes("haz una tarea compleja")

        self.assertTrue(adapter.playback.flushed)

    def test_hermes_transcript_gate_requires_new_user_speech(self):
        adapter = object.__new__(live_module.GeminiLiveAdapter)
        adapter.cognitive_policy = CognitivePolicy()
        adapter.conversation_sessions = None
        adapter.session_epoch = 0
        adapter._hermes_speech_revision = 0
        adapter._last_hermes_speech_revision = 0

        decision = adapter._evaluate_hermes_transcript_gate()
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "sin_transcripcion_nueva")

        adapter._record_user_text("haz una presentacion", kind="speech")
        decision = adapter._evaluate_hermes_transcript_gate()
        self.assertTrue(decision.allowed)

        adapter._mark_hermes_transcript_consumed()
        decision = adapter._evaluate_hermes_transcript_gate()
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "sin_transcripcion_nueva")

    def test_hermes_tool_prompt_does_not_count_as_new_user_speech(self):
        adapter = object.__new__(live_module.GeminiLiveAdapter)
        adapter.cognitive_policy = CognitivePolicy()
        adapter.conversation_sessions = None
        adapter.session_epoch = 0
        adapter._hermes_speech_revision = 0
        adapter._last_hermes_speech_revision = 0

        adapter._record_user_text("haz una presentacion", kind="speech")
        adapter._mark_hermes_transcript_consumed()
        adapter._record_user_text("crear una presentacion", kind="hermes_tool_call")

        decision = adapter._evaluate_hermes_transcript_gate()
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "sin_transcripcion_nueva")

    def test_music_tool_requires_explicit_recent_music_intent(self):
        with patch.dict(os.environ, {"ENABLE_MUSIC_TOOL": "1"}):
            policy = CognitivePolicy()

            policy.record_user_utterance("hola")
            decision = policy.evaluate_tool_call(
                "reproducir_musica_youtube",
                {"cancion": "C.R.E.A.M. Wu-Tang Clan"},
                has_recent_voice=True,
            )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "musica_sin_intencion_explicita")

    def test_music_tool_accepts_explicit_recent_music_intent(self):
        with patch.dict(os.environ, {"ENABLE_MUSIC_TOOL": "1"}):
            policy = CognitivePolicy()

            policy.record_user_utterance("pon C.R.E.A.M. de Wu-Tang Clan en YouTube")
            decision = policy.evaluate_tool_call(
                "reproducir_musica_youtube",
                {"cancion": "C.R.E.A.M. Wu-Tang Clan"},
                has_recent_voice=True,
            )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "musica_confirmada")

    def test_music_tool_rejects_stale_music_intent(self):
        with patch.dict(os.environ, {"ENABLE_MUSIC_TOOL": "1"}):
            policy = CognitivePolicy()
            policy.record_user_utterance(
                "pon musica",
                now=time.monotonic() - live_module.MUSIC_TOOL_INTENT_WINDOW_SECONDS - 1.0,
            )

            decision = policy.evaluate_tool_call(
                "reproducir_musica_youtube",
                {"cancion": "otra cancion"},
                has_recent_voice=True,
            )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "musica_sin_intencion_explicita")

    def test_disabled_music_tool_routes_music_request_to_hermes(self):
        with patch.dict(os.environ, {"ENABLE_MUSIC_TOOL": "0"}):
            policy = CognitivePolicy()
            policy.record_user_utterance("pon C.R.E.A.M. de Wu-Tang Clan en YouTube")

            direct_decision = policy.evaluate_tool_call(
                "reproducir_musica_youtube",
                {"cancion": "C.R.E.A.M. Wu-Tang Clan"},
                has_recent_voice=True,
            )
            hermes_decision = policy.evaluate_tool_call(
                "ejecutar_hermes_core",
                {"prompt": "reproducir C.R.E.A.M. de Wu-Tang Clan en YouTube"},
                has_recent_voice=True,
            )

        self.assertFalse(direct_decision.allowed)
        self.assertEqual(direct_decision.reason, "musica_tool_desactivada")
        self.assertTrue(hermes_decision.allowed)
        self.assertEqual(hermes_decision.reason, "delegacion_hermes")

    def test_disabled_music_tool_blocks_negative_music_request_to_hermes(self):
        with patch.dict(os.environ, {"ENABLE_MUSIC_TOOL": "0"}):
            policy = CognitivePolicy()
            policy.record_user_utterance("no pongas musica")

            decision = policy.evaluate_tool_call(
                "ejecutar_hermes_core",
                {"prompt": "reproducir musica"},
                has_recent_voice=True,
            )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "musica_negada")

    def test_cognitive_policy_rejects_tool_without_recent_voice(self):
        policy = CognitivePolicy()
        policy.record_user_utterance("pon musica")

        decision = policy.evaluate_tool_call(
            "reproducir_musica_youtube",
            {"cancion": "algo"},
            has_recent_voice=False,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "sin_voz_reciente")

    def test_cognitive_policy_accepts_hermes_delegation_with_recent_voice(self):
        policy = CognitivePolicy()
        policy.record_user_utterance("revisa mis archivos")

        decision = policy.evaluate_tool_call(
            "ejecutar_hermes_core",
            {"prompt": "revisa mis archivos"},
            has_recent_voice=True,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "delegacion_hermes")

    def test_cognitive_policy_allows_hermes_delegation_for_simple_greeting_by_default(self):
        policy = CognitivePolicy()
        policy.record_user_utterance("hola")

        decision = policy.evaluate_tool_call(
            "ejecutar_hermes_core",
            {"prompt": "buscar informacion compleja que el usuario no pidio"},
            has_recent_voice=True,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "delegacion_hermes")

    def test_cognitive_policy_strict_hermes_gate_can_reject_simple_greeting(self):
        with patch.dict(os.environ, {"STRICT_HERMES_INTENT_GATE": "1"}):
            policy = CognitivePolicy()
            policy.record_user_utterance("hola")

            decision = policy.evaluate_tool_call(
                "ejecutar_hermes_core",
                {"prompt": "buscar informacion compleja que el usuario no pidio"},
                has_recent_voice=True,
            )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "hermes_sin_intencion_explicita")

    def test_cognitive_policy_accepts_hermes_for_memory_identity_question(self):
        policy = CognitivePolicy()
        policy.record_user_utterance("como me llamo")

        decision = policy.evaluate_tool_call(
            "ejecutar_hermes_core",
            {"prompt": "consultar memoria del usuario"},
            has_recent_voice=True,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "delegacion_hermes")

    def test_cognitive_policy_accepts_hermes_for_pptx_creation(self):
        policy = CognitivePolicy()
        policy.record_user_utterance("haz un pptx")

        decision = policy.evaluate_tool_call(
            "ejecutar_hermes_core",
            {"prompt": "crear una presentacion pptx"},
            has_recent_voice=True,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "delegacion_hermes")

    def test_cognitive_policy_accepts_hermes_for_presentation_creation(self):
        policy = CognitivePolicy()
        policy.record_user_utterance("haz una presentacion")

        decision = policy.evaluate_tool_call(
            "ejecutar_hermes_core",
            {"prompt": "crear una presentacion"},
            has_recent_voice=True,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "delegacion_hermes")

    def test_cognitive_policy_rejects_cancel_without_explicit_cancel_intent(self):
        policy = CognitivePolicy()
        policy.record_user_utterance("hola")

        decision = policy.evaluate_tool_call(
            "cancelar_tarea_hermes",
            {"motivo": ""},
            has_recent_voice=True,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "cancelacion_sin_intencion_explicita")

    def test_cognitive_policy_accepts_explicit_cancel_intent(self):
        policy = CognitivePolicy()
        policy.record_user_utterance("cancela la tarea de fondo")

        decision = policy.evaluate_tool_call(
            "cancelar_tarea_hermes",
            {"motivo": "usuario pidio cancelar"},
            has_recent_voice=True,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "cancelacion_confirmada")

    def test_cognitive_policy_accepts_explicit_task_status_request(self):
        policy = CognitivePolicy()
        policy.record_user_utterance("como va la tarea")

        decision = policy.evaluate_tool_call(
            "consultar_estado_tareas",
            {},
            has_recent_voice=True,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "estado_tareas_confirmado")

    def test_cognitive_policy_rejects_task_status_without_explicit_status_intent(self):
        policy = CognitivePolicy()
        policy.record_user_utterance("hola")

        decision = policy.evaluate_tool_call(
            "consultar_estado_tareas",
            {},
            has_recent_voice=True,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "estado_tareas_sin_intencion_explicita")

    def test_cognitive_policy_accepts_explicit_today_summary_request(self):
        policy = CognitivePolicy()
        policy.record_user_utterance("que tenemos hoy")

        decision = policy.evaluate_tool_call(
            "consultar_resumen_hoy",
            {},
            has_recent_voice=True,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "resumen_hoy_confirmado")

    def test_cognitive_policy_rejects_hermes_for_local_today_summary(self):
        policy = CognitivePolicy()
        policy.record_user_utterance("que tenemos hoy")

        decision = policy.evaluate_tool_call(
            "ejecutar_hermes_core",
            {"prompt": "consultar que tenemos hoy"},
            has_recent_voice=True,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "resumen_hoy_debe_ser_local")

    def test_cognitive_policy_allows_current_news_today_to_hermes(self):
        policy = CognitivePolicy()
        policy.record_user_utterance("busca noticias de hoy")

        decision = policy.evaluate_tool_call(
            "ejecutar_hermes_core",
            {"prompt": "buscar noticias de hoy"},
            has_recent_voice=True,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "delegacion_hermes")

    def test_cognitive_policy_does_not_match_cancel_inside_other_words(self):
        policy = CognitivePolicy()
        policy.record_user_utterance("prepara el resumen")

        decision = policy.evaluate_tool_call(
            "cancelar_tarea_hermes",
            {"motivo": ""},
            has_recent_voice=True,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "cancelacion_sin_intencion_explicita")

    def test_reconnect_memory_is_silent_context_not_resume_instruction(self):
        context_manager = ContextManager("JARVIS", "Usuario", "Aoede")
        context_manager.add_memory("El usuario preguntó por una tarea pasada.")

        config = context_manager.get_live_config()
        instruction = config.system_instruction.parts[0].text

        self.assertNotIn("MEMORIA RECIENTE INTERNA", instruction)
        self.assertNotIn("El usuario pregunt", instruction)
        self.assertNotIn("pregunta pasada", instruction)
        self.assertNotIn("retomar la conversación", instruction)

    def test_live_tool_gate_blocks_during_reconnect_grace(self):
        class CaptureWithRecentVoice:
            def has_recent_voice(self, window_seconds=None):
                return True

        adapter = object.__new__(live_module.GeminiLiveAdapter)
        adapter.capture = CaptureWithRecentVoice()
        adapter._session_started_at = time.monotonic()

        original_grace = live_module.VOICE_TOOL_RECONNECT_GRACE_SECONDS
        try:
            live_module.VOICE_TOOL_RECONNECT_GRACE_SECONDS = 30.0
            self.assertFalse(adapter._has_recent_user_voice())
            self.assertTrue(adapter._should_suppress_reconnect_output())

            adapter._session_started_at = time.monotonic() - 31.0
            self.assertTrue(adapter._has_recent_user_voice())
            self.assertFalse(adapter._should_suppress_reconnect_output())
        finally:
            live_module.VOICE_TOOL_RECONNECT_GRACE_SECONDS = original_grace

    def test_activation_gate_controls_reconnect_sleep_and_delivery(self):
        gate = ActivationGate(idle_sleep_seconds=0.01)

        epoch = gate.start_live_session("test_reconnect")

        self.assertEqual(epoch, 1)
        self.assertEqual(gate.state, ActivationState.SILENT_RECONNECT)
        self.assertFalse(gate.allows_model_output())
        self.assertFalse(gate.allows_user_tool_call())

        gate.mark_user_voice("test_voice")
        self.assertEqual(gate.state, ActivationState.ACTIVE)
        self.assertTrue(gate.allows_model_output())
        self.assertTrue(gate.allows_user_tool_call())

        gate.last_user_voice_at = time.monotonic() - 1.0
        self.assertTrue(gate.sleep_if_idle())
        self.assertEqual(gate.state, ActivationState.DORMANT)
        self.assertFalse(gate.allows_model_output())

        wake = gate.request_wake("hermes", "task_completed", turn_id="turn-1")
        gate.begin_delivery(wake)
        self.assertEqual(gate.state, ActivationState.DELIVERING)
        self.assertTrue(gate.allows_model_output())
        self.assertFalse(gate.allows_user_tool_call())
        self.assertFalse(gate.sleep_if_idle())

        gate.mark_user_voice("barge_in")
        self.assertEqual(gate.state, ActivationState.ACTIVE)

        gate.force_sleep("quota")
        self.assertEqual(gate.state, ActivationState.DORMANT)
        self.assertFalse(gate.allows_model_output())

    def test_live_quota_error_is_not_normal_recycle(self):
        adapter = object.__new__(live_module.GeminiLiveAdapter)

        quota_error = Exception("1011 Resource has been exhausted (e.g. check quota).")
        goaway_error = Exception("GoAway received 1008 policy violation")

        self.assertTrue(adapter._is_live_quota_error(quota_error))
        self.assertFalse(adapter._is_session_recycle_error(quota_error))
        self.assertFalse(adapter._is_live_quota_error(goaway_error))
        self.assertTrue(adapter._is_session_recycle_error(goaway_error))

    async def test_hermes_delivery_wakes_activation_gate(self):
        gate = ActivationGate(idle_sleep_seconds=0.01)
        self.action_router.activation_gate = gate
        self.brain.delay = 0.01
        session_mock = AsyncMock()
        self.action_router.get_session = lambda: session_mock

        gate.start_live_session("test_reconnect")
        self.assertFalse(gate.allows_model_output())

        await self.action_router.run_hermes("1", "test", "Tarea con entrega")

        self.assertEqual(gate.state, ActivationState.DELIVERING)
        self.assertTrue(gate.allows_model_output())
        session_mock.send_client_content.assert_called_once()
        self.assertEqual(len(gate.pending_wake_requests), 0)

    async def test_conversation_session_close_consolidates_memory(self):
        consolidator = SessionMemoryConsolidator(self.brain)
        consolidator.min_chars = 1
        consolidator.defer_seconds = 0.0
        manager = ConversationSessionManager(consolidator)

        manager.record_user("Mi nombre es Camilo y prefiero respuestas directas.", session_epoch=7)
        closed = manager.close_active_session("idle_timeout")

        self.assertIsNotNone(closed)
        for _ in range(20):
            if self.brain.run_count:
                break
            await asyncio.sleep(0.01)

        self.assertEqual(self.brain.run_count, 1)
        self.assertIn("CONSOLIDACION DE MEMORIA", self.brain.tasks[0])
        self.assertIn("prefiero respuestas directas", self.brain.tasks[0])

    async def test_session_memory_review_enables_skill_review_on_learning_signal(self):
        class ReviewBrain(FakeBrain):
            def __init__(self):
                super().__init__()
                self.review_calls = []

            async def review_session_memory(self, messages, review_skills=False):
                self.review_calls.append((messages, review_skills))
                return BrainResult("ok", success=True)

        brain = ReviewBrain()
        consolidator = SessionMemoryConsolidator(brain)
        consolidator.min_chars = 1
        consolidator.defer_seconds = 0.0
        manager = ConversationSessionManager(consolidator)

        manager.record_user("Prefiero que me respondas directo y sin vueltas.", session_epoch=7)
        manager.close_active_session("idle_timeout")

        for _ in range(20):
            if brain.review_calls:
                break
            await asyncio.sleep(0.01)

        self.assertEqual(len(brain.review_calls), 1)
        self.assertTrue(brain.review_calls[0][1])

    async def test_session_memory_review_skips_skill_review_without_learning_signal(self):
        class ReviewBrain(FakeBrain):
            def __init__(self):
                super().__init__()
                self.review_calls = []

            async def review_session_memory(self, messages, review_skills=False):
                self.review_calls.append((messages, review_skills))
                return BrainResult("ok", success=True)

        brain = ReviewBrain()
        consolidator = SessionMemoryConsolidator(brain)
        consolidator.min_chars = 1
        consolidator.defer_seconds = 0.0
        manager = ConversationSessionManager(consolidator)

        manager.record_user("Busca informacion sobre el clima de manana.", session_epoch=7)
        manager.close_active_session("idle_timeout")

        for _ in range(20):
            if brain.review_calls:
                break
            await asyncio.sleep(0.01)

        self.assertEqual(len(brain.review_calls), 1)
        self.assertFalse(brain.review_calls[0][1])

    async def test_task_ledger_tracks_hermes_completion(self):
        ledger = TaskLedger()
        self.action_router.task_ledger = ledger
        self.brain.delay = 0.01
        session_mock = AsyncMock()
        self.action_router.get_session = lambda: session_mock

        await self.action_router.run_hermes("1", "test", "Tarea registrada")

        task = ledger.recent_tasks(1)[0]
        self.assertEqual(task.kind, "hermes")
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(task.result, self.brain.result_text)
        self.assertEqual(task.turn_id, self.synapse.active_turn.turn_id)
