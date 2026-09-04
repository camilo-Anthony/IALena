"""
MemoryConsolidator - Motor de Auto-Consolidación Pasiva de Memoria
Analiza las interacciones recientes cuando JARVIS está en reposo (dormant)
y extrae automáticamente preferencias, reglas y hechos personales a USER.md.
"""

import asyncio
import os
import re
import time
from typing import Any, List, Optional
from pathlib import Path

# Patrones para detectar hechos relevantes del usuario sin llamadas forzadas
_FACT_EXTRACTION_PATTERNS = [
    # Preferencias explícitas
    (
        r"(?:prefiero|me gusta más|me encanta|suelo|acostumbro a|mi preferencia es)\s+([^\.\n,]+)",
        "preferencia_personal",
        "Prefiere {match}",
    ),
    # Negaciones / Aversiones
    (
        r"(?:no me gusta|odio|detesto|evita|nunca use?s?|no use?s?)\s+([^\.\n,]+)",
        "preferencia_personal",
        "Evitar {match}",
    ),
    # Reglas condicionales
    (
        r"(?:cuando te pida|cuando te diga|siempre que pida|a partir de ahora|cada vez que)\s+([^,]+),\s*([^.\n]+)",
        "regla_comportamiento",
        "Cuando {match0}: {match1}",
    ),
    # Proyectos y trabajo
    (
        r"(?:estoy trabajando en|mi proyecto es|desarrollo en|trabajo con|estoy programando en)\s+([^\.\n,]+)",
        "contexto_profesional",
        "Trabaja en {match}",
    ),
    # Hechos personales / Familia / Ubicación
    (
        r"(?:tengo un|tengo una|mi hijo|mi hija|mi esposa|mi hermano|vivo en|soy de)\s+([^\.\n,]+)",
        "dato_usuario",
        "{match}",
    ),
]


class MemoryConsolidator:
    """
    Motor de consolidación pasiva de memoria.
    Observa el flujo conversacional y consolida recuerdos duraderos en USER.md.
    """

    def __init__(
        self,
        synapse: Optional[Any] = None,
        get_hermes_home_fn: Optional[Any] = None,
        idle_delay_seconds: float = 30.0,
    ):
        self.synapse = synapse
        self.get_hermes_home = get_hermes_home_fn
        self.idle_delay_seconds = idle_delay_seconds

        self._pending_utterances: List[str] = []
        self._last_utterance_time = 0.0
        self._running = False
        self._consolidator_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """Inicia el worker de consolidación pasiva."""
        if self._running:
            return
        self._running = True

        if self.synapse:
            self.synapse.subscribe("user_voice_received", self._on_user_voice)
            self.synapse.subscribe("activation_state_changed", self._on_state_changed)

        target_loop = loop or asyncio.get_event_loop()
        self._consolidator_task = target_loop.create_task(self._consolidation_loop())
        print("\033[32m[MemoryConsolidator]\033[0m Motor de auto-aprendizaje pasivo iniciado.")

    def stop(self) -> None:
        self._running = False
        if self._consolidator_task:
            self._consolidator_task.cancel()

    def record_user_text(self, text: str) -> None:
        """Registra texto del usuario para consolidación posterior."""
        clean = (text or "").strip()
        if len(clean) >= 5 and clean not in self._pending_utterances:
            self._pending_utterances.append(clean)
            self._last_utterance_time = time.monotonic()
            if len(self._pending_utterances) > 50:
                self._pending_utterances.pop(0)

    def _on_user_voice(self, payload: Any = None) -> None:
        if isinstance(payload, dict):
            text = payload.get("text", "")
            if text:
                self.record_user_text(text)

    def _on_state_changed(self, state: str) -> None:
        # Si pasa a dormant, el loop de consolidación se encargará al pasar idle_delay
        pass

    async def _consolidation_loop(self) -> None:
        """Bucle en segundo plano que consolida cuando hay silencio prolongado."""
        while self._running:
            try:
                await asyncio.sleep(5.0)
                now = time.monotonic()

                # Consolidar solo si han pasado al menos idle_delay_seconds desde la última frase
                if (
                    self._pending_utterances
                    and self._last_utterance_time > 0
                    and (now - self._last_utterance_time) >= self.idle_delay_seconds
                ):
                    await self.consolidate_now()

            except asyncio.CancelledError:
                break
            except Exception as exc:
                print(f"[MemoryConsolidator] Error en bucle de consolidación: {exc}")
                await asyncio.sleep(10.0)

    async def consolidate_now(self) -> int:
        """Extrae y persiste hechos encontrados en las frases acumuladas."""
        async with self._lock:
            if not self._pending_utterances:
                return 0

            texts_to_process = list(self._pending_utterances)
            self._pending_utterances.clear()
            self._last_utterance_time = 0.0

            facts_extracted: List[tuple[str, str]] = []

            for text in texts_to_process:
                # 1. Comprobar contra patrones de extracción de hechos
                for pattern, category, template in _FACT_EXTRACTION_PATTERNS:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        groups = match.groups()
                        if len(groups) == 1:
                            fact_text = template.format(match=groups[0].strip())
                        elif len(groups) >= 2:
                            fact_text = template.format(match0=groups[0].strip(), match1=groups[1].strip())
                        else:
                            fact_text = text.strip()

                        if len(fact_text) > 6:
                            facts_extracted.append((category, fact_text))

            if not facts_extracted:
                return 0

            # 2. Persistir en USER.md
            saved_count = 0
            user_md_path = self._get_user_md_path()
            if not user_md_path:
                return 0

            existing_content = ""
            if os.path.exists(user_md_path):
                try:
                    with open(user_md_path, "r", encoding="utf-8") as f:
                        existing_content = f.read()
                except Exception:
                    pass

            for category, fact in facts_extracted:
                entry = f"- [{category}] {fact}"
                if fact.lower() not in existing_content.lower():
                    try:
                        with open(user_md_path, "a", encoding="utf-8") as f:
                            if existing_content and not existing_content.endswith("\n"):
                                f.write("\n")
                            f.write(f"\n§\n{entry}\n")
                        existing_content += f"\n§\n{entry}\n"
                        saved_count += 1
                        print(f"\033[96m[MemoryConsolidator]\033[0m Aprendizaje pasivo guardado en USER.md: {entry}")
                    except Exception as w_exc:
                        print(f"[MemoryConsolidator] Error escribiendo memoria: {w_exc}")

            if saved_count > 0 and self.synapse:
                try:
                    self.synapse.emit("memory_updated", {"type": "passive_consolidation", "count": saved_count})
                except Exception:
                    pass

            return saved_count

    def _get_user_md_path(self) -> Optional[str]:
        try:
            if self.get_hermes_home:
                home = self.get_hermes_home()
            else:
                from hermes_constants import get_hermes_home
                home = get_hermes_home()
        except Exception:
            home = os.path.expanduser("~/.hermes")

        memories_dir = os.path.join(str(home), "memories")
        os.makedirs(memories_dir, exist_ok=True)
        return os.path.join(memories_dir, "USER.md")
