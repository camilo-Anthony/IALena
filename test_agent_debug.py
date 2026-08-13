import sys
import os
import traceback

# Ensure Hermes-Agent is in path
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_HERMES_DIR = os.path.join(_PROJECT_ROOT, "Hermes-Agent")
if _HERMES_DIR not in sys.path:
    sys.path.append(_HERMES_DIR)

print("Python version:", sys.version)
print("PATH:", sys.path)

try:
    from run_agent import AIAgent
    print("Imported AIAgent successfully:", AIAgent)
    
    # Try to instantiate AIAgent like HermesAdapter does
    agent = AIAgent(
        base_url="http://127.0.0.1:8000/v1/",
        api_key="proxy-managed",
        model="test",
        quiet_mode=True,
        save_trajectories=True,
    )
    print("Instantiated AIAgent successfully!")
except Exception as e:
    print("Error during instantiation:")
    traceback.print_exc()
