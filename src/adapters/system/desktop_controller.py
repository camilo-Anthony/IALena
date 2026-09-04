"""
desktop_controller.py — Controlador de escritorio (mouse y teclado) para Windows.

Permite a JARVIS y Hermes interactuar con aplicaciones de escritorio mediante
movimiento de cursor, clics, pulsación de teclas y atajos en Windows.
Incluye protecciones de seguridad y soporte dual (PyAutoGUI con fallback nativo Win32 ctypes).
"""
import sys
import time
import logging
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger("JARVIS.DesktopController")

# Atajos bloqueados por seguridad
BLOCKED_HOTKEYS = {
    ("win", "l"),
    ("ctrl", "alt", "del"),
    ("ctrl", "alt", "delete"),
    ("alt", "f4"),
}


class DesktopController:
    """Controlador de automatización de interfaz de usuario en Windows."""

    def __init__(self):
        self._has_pyautogui = False
        try:
            import pyautogui
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.05
            self._pyautogui = pyautogui
            self._has_pyautogui = True
        except ImportError:
            self._pyautogui = None

    def get_screen_size(self) -> Tuple[int, int]:
        """Retorna (ancho, alto) de la pantalla."""
        if self._has_pyautogui:
            return self._pyautogui.size()
        if sys.platform == "win32":
            import ctypes
            u32 = ctypes.windll.user32
            return u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)
        return (1920, 1080)

    def get_mouse_position(self) -> Tuple[int, int]:
        """Retorna la posición actual (x, y) del cursor."""
        if self._has_pyautogui:
            pos = self._pyautogui.position()
            return pos.x, pos.y
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes
            pt = wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            return pt.x, pt.y
        return (0, 0)

    def move_to(self, x: int, y: int, duration: float = 0.2) -> Dict[str, Any]:
        """Mueve el cursor a las coordenadas (x, y)."""
        w, h = self.get_screen_size()
        x = max(0, min(x, w - 1))
        y = max(0, min(y, h - 1))

        if self._has_pyautogui:
            self._pyautogui.moveTo(x, y, duration=duration)
            return {"status": "ok", "action": "move_to", "x": x, "y": y}
        elif sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.SetCursorPos(x, y)
            return {"status": "ok", "action": "move_to", "x": x, "y": y}
        return {"status": "error", "message": "Plataforma no soportada"}

    def click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: str = "left",
        clicks: int = 1,
    ) -> Dict[str, Any]:
        """Realiza clic en las coordenadas especificadas o en la posición actual."""
        if x is not None and y is not None:
            self.move_to(x, y)

        if self._has_pyautogui:
            self._pyautogui.click(button=button, clicks=clicks)
            return {"status": "ok", "action": "click", "button": button, "clicks": clicks}
        elif sys.platform == "win32":
            import ctypes
            # Constantes de eventos de mouse en Windows
            MOUSEEVENTF_LEFTDOWN = 0x0002
            MOUSEEVENTF_LEFTUP = 0x0004
            MOUSEEVENTF_RIGHTDOWN = 0x0008
            MOUSEEVENTF_RIGHTUP = 0x0010
            MOUSEEVENTF_MIDDLEDOWN = 0x0020
            MOUSEEVENTF_MIDDLEUP = 0x0040

            down, up = {
                "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
                "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
                "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
            }.get(button.lower(), (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP))

            for _ in range(clicks):
                ctypes.windll.user32.mouse_event(down, 0, 0, 0, 0)
                time.sleep(0.02)
                ctypes.windll.user32.mouse_event(up, 0, 0, 0, 0)
                if clicks > 1:
                    time.sleep(0.05)

            return {"status": "ok", "action": "click", "button": button, "clicks": clicks}
        return {"status": "error", "message": "Plataforma no soportada"}

    def type_text(self, text: str, interval: float = 0.02) -> Dict[str, Any]:
        """Escribe texto simulando pulsaciones de teclado."""
        if not text:
            return {"status": "error", "message": "Texto vacío"}

        if self._has_pyautogui:
            self._pyautogui.write(text, interval=interval)
            return {"status": "ok", "action": "type_text", "chars": len(text)}
        elif sys.platform == "win32":
            # Fallback seguro con portapapeles o SendInput para texto en Windows
            import ctypes
            for char in text:
                vk = ctypes.windll.user32.VkKeyScanW(ord(char))
                if vk != -1:
                    ctypes.windll.user32.keybd_event(vk & 0xFF, 0, 0, 0)
                    time.sleep(interval)
                    ctypes.windll.user32.keybd_event(vk & 0xFF, 0, 2, 0)
            return {"status": "ok", "action": "type_text", "chars": len(text)}
        return {"status": "error", "message": "Plataforma no soportada"}

    def press_key(self, key: str) -> Dict[str, Any]:
        """Presiona una tecla específica (ej: 'enter', 'tab', 'esc', 'space')."""
        key_lower = key.strip().lower()

        if self._has_pyautogui:
            self._pyautogui.press(key_lower)
            return {"status": "ok", "action": "press_key", "key": key_lower}
        return {"status": "error", "message": "Requiere PyAutoGUI"}

    def hotkey(self, *keys: str) -> Dict[str, Any]:
        """Ejecuta una combinación de teclas (ej: 'ctrl', 'c'). Valida seguridad."""
        normalized = tuple(k.strip().lower() for k in keys)
        if normalized in BLOCKED_HOTKEYS:
            return {"status": "blocked", "message": f"Atajo bloqueado por seguridad: {keys}"}

        if self._has_pyautogui:
            self._pyautogui.hotkey(*normalized)
            return {"status": "ok", "action": "hotkey", "keys": list(normalized)}
        return {"status": "error", "message": "Requiere PyAutoGUI"}


# Instancia singleton
_controller_instance: Optional[DesktopController] = None


def get_desktop_controller() -> DesktopController:
    global _controller_instance
    if _controller_instance is None:
        _controller_instance = DesktopController()
    return _controller_instance
