import asyncio
import os
import socket
from dotenv import load_dotenv

# pyrefly: ignore [missing-import]
from src.adapters.audio.pyaudio_capture import PyAudioCapture
# pyrefly: ignore [missing-import]
from src.adapters.audio.pyaudio_playback import PyAudioPlayback
# pyrefly: ignore [missing-import]
from src.adapters.brain.hermes_adapter import HermesAdapter
# pyrefly: ignore [missing-import]
from src.adapters.llm.gemini_live_adapter import GeminiLiveAdapter

# pyrefly: ignore [missing-import]
from src.kernel.context_manager import ContextManager
# pyrefly: ignore [missing-import]
from src.kernel.jarvis_kernel import JarvisKernel

# ── Importaciones seguras de constantes ──
try:
    from hermes_constants import get_hermes_home
except ImportError:
    get_hermes_home = None

_INSTANCE_LOCK_SOCKET = None


def _acquire_single_instance_lock() -> bool:
    """Evita dos instancias simultaneas capturando microfono y altavoz."""
    global _INSTANCE_LOCK_SOCKET
    port_raw = os.getenv("JARVIS_INSTANCE_LOCK_PORT", "43187")
    try:
        port = int(port_raw)
    except ValueError:
        port = 43187

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind(("127.0.0.1", port))
        sock.listen(1)
    except OSError:
        sock.close()
        print(
            f"[JARVIS] Ya hay una instancia activa (lock 127.0.0.1:{port}). "
            "No se iniciara otra voz."
        )
        return False

    _INSTANCE_LOCK_SOCKET = sock
    return True

def main():
    if not _acquire_single_instance_lock():
        return

    load_dotenv(encoding="utf-8")

    # 1. Configuración Básica
    INPUT_RATE  = 16_000
    OUTPUT_RATE = 24_000
    MODEL_BRAIN = os.getenv("MODEL_BRAIN", "gemini-3.1-flash-lite")

    bot_name = os.getenv("ASSISTANT_NAME", "JARVIS")
    user_name = os.getenv("USER_NAME", "Señor")
    voice_name = os.getenv("VOICE_NAME", "Aoede")

    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
    _raw_hermes_keys = [os.getenv(f"HERMES_API_KEY_{i}") for i in range(1, 30)]
    hermes_keys = [k for k in _raw_hermes_keys if k] or [gemini_key]

    # 2. Instanciación de Adaptadores (Capa de Infraestructura)
    mic = PyAudioCapture(rate=INPUT_RATE)
    speaker = PyAudioPlayback(rate=OUTPUT_RATE)
    brain = HermesAdapter(api_keys=hermes_keys, model_brain=MODEL_BRAIN, mode="slow")
    brain_fast = HermesAdapter(api_keys=hermes_keys, model_brain=MODEL_BRAIN, mode="fast")

    # 3. Instanciación del Gestor de Contexto (Capa de Kernel)
    context_mgr = ContextManager(bot_name, user_name, voice_name, get_hermes_home)

    # 4. Inyección de Dependencias y Arranque (Capa de Kernel)
    # Pasamos los adaptadores instanciados al Kernel, y le decimos cómo construir la voz.
    kernel = JarvisKernel(
        audio_capture=mic,
        audio_playback=speaker,
        brain=brain,
        brain_fast=brain_fast,
        voice_llm_factory=GeminiLiveAdapter,
        context_manager=context_mgr
    )

    # Registrar en el puente de la API
    from src.server.kernel_bridge import register_kernel
    register_kernel(kernel)

    # Iniciar API local FastAPI en un hilo separado
    def start_api():
        import uvicorn
        uvicorn.run("src.server.app:app", host="127.0.0.1", port=8420, log_level="warning")

    threading.Thread(target=start_api, daemon=True).start()
    print("[JARVIS] API local iniciada en http://127.0.0.1:8420")

    try:
        asyncio.run(kernel.boot())
    except KeyboardInterrupt:
        print("\n[JARVIS] Señal de interrupción recibida.")
        kernel.shutdown()

if __name__ == "__main__":
    import threading
    main()
