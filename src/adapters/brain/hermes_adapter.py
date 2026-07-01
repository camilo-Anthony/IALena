import os
import sys

# Asegurar que Hermes-Agent está en el path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
_HERMES_DIR = os.path.join(_PROJECT_ROOT, "Hermes-Agent")
if _HERMES_DIR not in sys.path:
    sys.path.append(_HERMES_DIR)

from src.core.interfaces.brain import IAgentBrain

# Importaciones seguras de Hermes
try:
    from run_agent import AIAgent  # type: ignore
except ImportError:
    AIAgent = None

from src.adapters.brain.key_rotator import start_proxy # Asumimos que key_rotator sigue existiendo temporalmente, o lo moveremos después.


class HermesAdapter(IAgentBrain):
    """Adaptador que envuelve al sistema AIAgent de Hermes para actuar como Cerebro de J.A.R.V.I.S."""
    
    def __init__(self, api_keys: list, model_brain: str):
        self.hermes_agent = None
        
        if not AIAgent:
            print("[HermesAdapter] ERROR: No se encontró el módulo Hermes Agent en el path.")
            return
            
        try:
            # Iniciamos el proxy de llaves local
            proxy_port = start_proxy(api_keys)
            proxy_base_url = f"http://127.0.0.1:{proxy_port}/v1/"
            
            print(f"[HermesAdapter] Inicializando Hermes Core ({len(api_keys)} clave(s) en rotación)…")
            
            self.hermes_agent = AIAgent(
                base_url=proxy_base_url,
                api_key="proxy-managed",
                model=model_brain,
                quiet_mode=True,
                save_trajectories=True,
            )
            
            # Llamada de calentamiento en background
            import threading
            def _warmup_hermes():
                try:
                    self.hermes_agent.chat("ping - responde ok")
                except: pass
            threading.Thread(target=_warmup_hermes, daemon=True).start()
            
            print("[HermesAdapter] Hermes Core listo (rotación activa).")
        except Exception as exc:
            print(f"[HermesAdapter] Error al inicializar: {exc}")

    def chat(self, prompt: str) -> str:
        """Envía una instrucción al agente Hermes subyacente."""
        if not self.is_available():
            raise Exception("Hermes Core no está disponible o no se inicializó correctamente.")
        
        return self.hermes_agent.chat(prompt)
        
    def is_available(self) -> bool:
        """Retorna True si el agente se inicializó correctamente."""
        return self.hermes_agent is not None
