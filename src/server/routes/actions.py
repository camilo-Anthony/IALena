import os
import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from src.server.kernel_bridge import get_kernel, append_log

router = APIRouter(prefix="/actions", tags=["Actions"])


@router.post("/cancel-task")
async def cancel_task():
    kernel = get_kernel()
    if not kernel:
        raise HTTPException(status_code=503, detail="Kernel no registrado")
    try:
        # Cancelar tarea en el action_router
        await kernel.action_router.interrupt_active_turn("Cancelado desde UI")
        append_log("INFO", "Tarea cancelada desde UI", source="api")
        return {"status": "ok", "message": "Tarea cancelada exitosamente"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/mute")
def toggle_mute():
    kernel = get_kernel()
    if not kernel:
        raise HTTPException(status_code=503, detail="Kernel no registrado")
    try:
        mic = kernel.audio_capture
        if hasattr(mic, "muted"):
            mic.muted = not mic.muted
            state = "silenciado" if mic.muted else "activo"
            append_log("INFO", f"Micrófono {state} desde UI", source="api")
            return {"status": "ok", "muted": mic.muted}
        return {"status": "error", "message": "El capturador no soporta silenciado dinámico"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/wake")
def request_wake():
    kernel = get_kernel()
    if not kernel:
        raise HTTPException(status_code=503, detail="Kernel no registrado")
    try:
        kernel.activation_gate.request_wake("ui", "Despertado desde UI")
        state = kernel.activation_gate.state.value
        append_log("INFO", f"Wake solicitado desde UI. Estado: {state}", source="api")
        return {"status": "ok", "state": state}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/sleep")
def force_sleep():
    kernel = get_kernel()
    if not kernel:
        raise HTTPException(status_code=503, detail="Kernel no registrado")
    try:
        kernel.activation_gate.force_sleep("ui")
        state = kernel.activation_gate.state.value
        append_log("INFO", f"Sleep forzado desde UI. Estado: {state}", source="api")
        return {"status": "ok", "state": state}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/restart-voice")
def restart_voice():
    """Reconecta el adaptador de voz Live de forma segura sin colisiones de event loop."""
    kernel = get_kernel()
    if not kernel:
        raise HTTPException(status_code=503, detail="Kernel no registrado")
    try:
        va = kernel.voice_assistant
        if va is None:
            raise HTTPException(status_code=503, detail="Voice assistant no instanciado")
        append_log("INFO", "Reinicio de voz solicitado desde UI", source="api")
        if hasattr(va, "restart_session"):
            va.restart_session()
        else:
            setattr(va, "_reconnect_requested", True)
        return {"status": "ok", "message": "Reconexión de voz iniciada de forma segura"}
    except HTTPException:
        raise
    except Exception as exc:
        append_log("ERROR", f"Error reiniciando voz: {exc}", source="api")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/shutdown")
def shutdown_kernel():
    """Apaga el kernel de forma ordenada. Operación irreversible."""
    kernel = get_kernel()
    if not kernel:
        raise HTTPException(status_code=503, detail="Kernel no registrado")
    try:
        append_log("WARNING", "Shutdown solicitado desde UI", source="api")
        kernel.shutdown()
        return {"status": "ok", "message": "Kernel apagado"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/test-live")
async def test_live():
    """Verifica conectividad con la API Live de Gemini."""
    kernel = get_kernel()
    if not kernel:
        raise HTTPException(status_code=503, detail="Kernel no registrado")
    try:
        va = kernel.voice_assistant
        connected = va is not None and getattr(va, "session", None) is not None
        status = "connected" if connected else "disconnected"
        append_log("INFO", f"Test Live: {status}", source="api")
        return {"status": status, "live_connected": connected}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/test-hermes-slow")
async def test_hermes_slow():
    """Envía una tarea mínima al carril SLOW de Hermes para verificar disponibilidad."""
    kernel = get_kernel()
    if not kernel:
        raise HTTPException(status_code=503, detail="Kernel no registrado")
    try:
        brain = kernel.brain
        if brain is None or not brain.is_available():
            return {"status": "unavailable", "message": "Hermes SLOW no disponible"}
        append_log("INFO", "Test Hermes SLOW iniciado desde UI", source="api")
        result = await brain.run_task("Responde solo con la palabra: OK")
        success = result.success and bool(result.text)
        append_log(
            "INFO" if success else "ERROR",
            f"Test Hermes SLOW: {'OK' if success else result.error}",
            source="api",
        )
        return {
            "status": "ok" if success else "error",
            "text": (result.text or "")[:200],
            "error": result.error,
        }
    except Exception as exc:
        append_log("ERROR", f"Test Hermes SLOW falló: {exc}", source="api")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/test-hermes-fast")
async def test_hermes_fast():
    """Envía una tarea mínima al carril FAST de Hermes para verificar disponibilidad."""
    kernel = get_kernel()
    if not kernel:
        raise HTTPException(status_code=503, detail="Kernel no registrado")
    try:
        brain_fast = kernel.brain_fast
        if brain_fast is None or not brain_fast.is_available():
            return {"status": "unavailable", "message": "Hermes FAST no disponible"}
        append_log("INFO", "Test Hermes FAST iniciado desde UI", source="api")
        result = await brain_fast.run_task("Responde solo con la palabra: OK")
        success = result.success and bool(result.text)
        append_log(
            "INFO" if success else "ERROR",
            f"Test Hermes FAST: {'OK' if success else result.error}",
            source="api",
        )
        return {
            "status": "ok" if success else "error",
            "text": (result.text or "")[:200],
            "error": result.error,
        }
    except Exception as exc:
        append_log("ERROR", f"Test Hermes FAST falló: {exc}", source="api")
        raise HTTPException(status_code=500, detail=str(exc))
