"""
desktop_vision.py — Módulo de captura y análisis visual del escritorio Windows.

Permite a JARVIS tomar capturas de pantalla del escritorio o la ventana activa
y enviarlas como base64 para análisis multimodal por Hermes/Gemini.
"""
import base64
import io
import os
import sys
import time


def capture_screenshot(active_window_only: bool = False, max_width: int = 1280) -> dict:
    """
    Captura la pantalla completa o la ventana activa en Windows.
    
    Retorna un dict con:
      - image_base64: str (PNG en base64)
      - width: int
      - height: int
      - window_title: str (si active_window_only)
      - timestamp: float
      - error: str | None
    """
    result = {
        "image_base64": "",
        "width": 0,
        "height": 0,
        "window_title": "",
        "timestamp": time.time(),
        "error": None,
    }
    
    try:
        from PIL import ImageGrab, Image
    except ImportError:
        try:
            import mss
        except ImportError:
            result["error"] = "Ni PIL (Pillow) ni mss están instalados. Instala con: pip install Pillow"
            return result
        # Fallback: usar mss
        return _capture_with_mss(max_width, result)
    
    try:
        if active_window_only and sys.platform == "win32":
            img, title = _capture_active_window_win32()
            result["window_title"] = title or "Ventana desconocida"
        else:
            img = ImageGrab.grab()
            result["window_title"] = "Pantalla completa"
        
        if img is None:
            result["error"] = "No se pudo capturar la pantalla."
            return result
        
        # Redimensionar si es demasiado grande para optimizar tokens
        if img.width > max_width:
            ratio = max_width / img.width
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        
        result["width"] = img.width
        result["height"] = img.height
        
        # Convertir a PNG base64
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        result["image_base64"] = base64.b64encode(buffer.getvalue()).decode("utf-8")
        
    except Exception as exc:
        result["error"] = f"Error capturando pantalla: {exc}"
    
    return result


def _capture_active_window_win32():
    """Captura solo la ventana activa en Windows usando Win32 API."""
    try:
        import ctypes
        from ctypes import wintypes
        from PIL import ImageGrab, Image
        
        user32 = ctypes.windll.user32
        
        # Obtener handle de la ventana activa
        hwnd = user32.GetForegroundWindow()
        
        # Obtener título
        length = user32.GetWindowTextLengthW(hwnd)
        title_buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title_buf, length + 1)
        title = title_buf.value
        
        # Obtener coordenadas de la ventana
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        
        bbox = (rect.left, rect.top, rect.right, rect.bottom)
        # Evitar coordenadas negativas (ventanas minimizadas)
        if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            return ImageGrab.grab(), title
        
        img = ImageGrab.grab(bbox=bbox)
        return img, title
        
    except Exception:
        from PIL import ImageGrab
        return ImageGrab.grab(), "Ventana (fallback)"


def _capture_with_mss(max_width: int, result: dict) -> dict:
    """Fallback usando mss si PIL no está disponible."""
    try:
        import mss
        from PIL import Image
        
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # Monitor principal
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        
        if img.width > max_width:
            ratio = max_width / img.width
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        
        result["width"] = img.width
        result["height"] = img.height
        result["window_title"] = "Pantalla completa (mss)"
        
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        result["image_base64"] = base64.b64encode(buffer.getvalue()).decode("utf-8")
        
    except Exception as exc:
        result["error"] = f"Error con mss: {exc}"
    
    return result


def format_for_hermes(capture: dict) -> str:
    """Formatea la captura para incluirla como contexto en un prompt de Hermes."""
    if capture.get("error"):
        return f"[Error de captura de pantalla: {capture['error']}]"
    
    return (
        f"[Captura de pantalla del escritorio: {capture['window_title']} "
        f"({capture['width']}x{capture['height']}px) "
        f"tomada a las {time.strftime('%H:%M:%S', time.localtime(capture['timestamp']))}]"
    )


def save_screenshot(capture: dict, dest_path: str = "") -> str:
    """Guarda la captura en disco y retorna la ruta del archivo."""
    if not capture.get("image_base64"):
        return ""
    if not dest_path:
        os.makedirs("data/captures", exist_ok=True)
        dest_path = f"data/captures/screen_{int(capture['timestamp'])}.png"
    else:
        parent = os.path.dirname(os.path.abspath(dest_path))
        os.makedirs(parent, exist_ok=True)
    
    img_data = base64.b64decode(capture["image_base64"])
    with open(dest_path, "wb") as f:
        f.write(img_data)
    return dest_path


async def analyze_screenshot(
    capture: dict,
    prompt: str = "",
    api_key: str = "",
    model: str = "gemini-2.5-flash",
) -> str:
    """
    Analiza visualmente la captura con Gemini multimodal.
    Retorna la descripción textual de lo que se observa.
    """
    if capture.get("error"):
        return f"Error en captura: {capture['error']}"
    if not capture.get("image_base64"):
        return "No hay imagen disponible para analizar."

    api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        return "Falta clave de API (GEMINI_API_KEY) para análisis visual."

    prompt_text = prompt or "Describe lo que ves en la pantalla del usuario, enfocándote en ventanas activas, código o errores si los hay."

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        img_bytes = base64.b64decode(capture["image_base64"])

        response = await client.aio.models.generate_content(
            model=model,
            contents=[
                types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                (
                    f"El usuario pregunta sobre lo que está en su pantalla de Windows: '{prompt_text}'. "
                    f"Ventana detectada: '{capture.get('window_title', 'Escritorio')}'. "
                    "Responde directamente, con concisión y precisión en español (máximo 2 a 3 oraciones), "
                    "para que un asistente de voz se lo diga al usuario."
                ),
            ],
        )
        return response.text or "No se pudo generar descripción visual."
    except Exception as exc:
        return f"Error al analizar la pantalla: {exc}"

