from dataclasses import dataclass, field
import time
from enum import Enum
from typing import List, Set, Dict

class TaskCapability(str, Enum):
    WEB = "web"
    FILE = "file"
    TERMINAL = "terminal"
    BROWSER = "browser"
    MEMORY = "memory"
    SKILLS = "skills"
    TODO = "todo"
    CODE_EXECUTION = "code_execution"
    DELEGATION = "delegation"
    CRONJOB = "cronjob"
    SESSION_SEARCH = "session_search"
    VISION = "vision"
    MCP = "mcp"
    HOME_ASSISTANT = "home_assistant"
    COMPUTER_USE = "computer_use"
    IMAGE_GEN = "image_gen"
    TTS = "tts"

@dataclass
class CapabilitySnapshot:
    slow_toolsets: List[str] = field(default_factory=list)
    slow_tools: List[str] = field(default_factory=list)
    fast_toolsets: List[str] = field(default_factory=list)
    fast_tools: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

class CapabilityRegistry:
    def __init__(self):
        self._snapshot = CapabilitySnapshot()

    def update_capabilities(
        self,
        lane: str,
        toolsets: List[str],
        tools: List[str]
    ):
        if lane == "slow":
            self._snapshot.slow_toolsets = list(toolsets)
            self._snapshot.slow_tools = list(tools)
        else:
            self._snapshot.fast_toolsets = list(toolsets)
            self._snapshot.fast_tools = list(tools)
        self._snapshot.timestamp = time.time()

    def has_capability(self, lane: str, capability: TaskCapability) -> bool:
        toolsets = self._snapshot.slow_toolsets if lane == "slow" else self._snapshot.fast_toolsets
        tools = self._snapshot.slow_tools if lane == "slow" else self._snapshot.fast_tools

        # Casos dinámicos especiales
        if capability == TaskCapability.MCP:
            return any(ts.startswith("mcp-") for ts in toolsets) or any(t.startswith("mcp_") for t in tools)
        if capability == TaskCapability.HOME_ASSISTANT:
            return any(ts == "home_assistant" for ts in toolsets) or any(t.startswith("home_assistant") for t in tools)
        if capability == TaskCapability.COMPUTER_USE:
            return any(ts == "computer_use" for ts in toolsets) or any(t.startswith("computer_use") for t in tools)

        # Mapping fiel a las herramientas reales presentes en el codebase de Hermes
        mapping: Dict[TaskCapability, tuple[str, List[str]]] = {
            TaskCapability.WEB: ("web", ["web_search", "web_extract"]),
            TaskCapability.FILE: ("file", ["read_file", "write_file", "patch", "search_files"]),
            TaskCapability.TERMINAL: ("terminal", ["terminal", "process"]),
            TaskCapability.BROWSER: ("browser", [
                "browser_navigate", "browser_snapshot", "browser_click",
                "browser_type", "browser_scroll", "browser_back",
                "browser_press", "browser_get_images", "browser_vision",
                "browser_console", "browser_cdp", "browser_dialog"
            ]),
            TaskCapability.MEMORY: ("memory", ["memory"]),
            TaskCapability.SKILLS: ("skills", ["skills_list", "skill_view", "skill_manage"]),
            TaskCapability.TODO: ("todo", ["todo"]),
            TaskCapability.CODE_EXECUTION: ("code_execution", ["execute_code"]),
            TaskCapability.DELEGATION: ("delegation", ["delegate_task"]),
            TaskCapability.CRONJOB: ("cronjob", ["cronjob"]),
            TaskCapability.SESSION_SEARCH: ("session_search", ["session_search"]),
            TaskCapability.VISION: ("vision", ["browser_vision", "vision_analyse", "vision_analyze"]),
            TaskCapability.IMAGE_GEN: ("image_gen", ["image_generate"]),
            TaskCapability.TTS: ("tts", ["text_to_speech"]),
        }

        if capability not in mapping:
            return False

        tset, tlist = mapping[capability]
        # Habilitado si el toolset está activo o al menos una de las herramientas clave está presente
        return tset in toolsets or any(t in tools for t in tlist)

    def snapshot_payload(self) -> dict:
        return {
            "slow_toolsets": list(self._snapshot.slow_toolsets),
            "slow_tools": list(self._snapshot.slow_tools),
            "fast_toolsets": list(self._snapshot.fast_toolsets),
            "fast_tools": list(self._snapshot.fast_tools),
            "timestamp": self._snapshot.timestamp,
        }

capability_registry = CapabilityRegistry()
