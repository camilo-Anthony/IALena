"""
local_tts.py — Motor de Síntesis de Voz Local Híbrido y Resiliente para JARVIS.

Proporciona capacidad de habla autónoma cuando:
  1. La conexión de Gemini Live se ha desconectado o cerrado (1006 / 1011).
  2. Gemini Live está en cuota agotada (429) o en reposo (DORMANT).
  3. El Centinela Autónomo o el Scheduler de Hermes emiten una notificación proactiva.

Motor Híbrido:
  - Primario: edge-tts con voz neuronal en español de alta fidelidad (ej. es-ES-AlvaroNeural).
  - Respaldo: Windows SAPI (SAPI.SpVoice) 100% offline y sin latencia si no hay internet.
"""
from __future__ import annotations

import asyncio
import os
import re
import tempfile
import threading
from typing import Optional

try:
    import pygame
    _PYGAME_AVAILABLE = True
except ImportError:
    _PYGAME_AVAILABLE = False

try:
    import win32com.client
    _SAPI_AVAILABLE = True
except ImportError:
    _SAPI_AVAILABLE = False


def _clean_text_for_speech(text: str) -> str:
    """Elimina etiquetas internas, markdown y caracteres especiales para locución natural."""
    if not text:
        return ""
    # Quitar cabeceras internas de JARVIS
    text = re.sub(r"\[JARVIS INTERNAL DELIVERY[^\]]*\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[Resultado[^\]]*\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[Fallo[^\]]*\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[[^\]]+\]", "", text)
    # Quitar formato markdown
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"```[\s\S]*?```", "código omitido", text)
    text = re.sub(r"https?://\S+", "enlace web", text)
    text = re.sub(r"[\r\n]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class LocalTTS:
    """Motor de voz local para JARVIS con reproducción asíncrona."""

    def __init__(
        self,
        voice: Optional[str] = None,
        rate: str = "+0%",
        volume: str = "+0%",
    ):
        self.voice = voice or os.getenv("LOCAL_TTS_VOICE", "es-ES-AlvaroNeural")
        self.rate = rate
        self.volume = volume
        self._lock = asyncio.Lock()
        self._thread_lock = threading.Lock()
        self._is_speaking = False

        if _PYGAME_AVAILABLE:
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
            except Exception as e:
                print(f"[LocalTTS] Advertencia al inicializar pygame.mixer: {e}")

    @property
    def is_busy(self) -> bool:
        if self._is_speaking:
            return True
        if _PYGAME_AVAILABLE and pygame.mixer.get_init():
            try:
                return pygame.mixer.music.get_busy()
            except Exception:
                pass
        return False

    async def speak(self, text: str, non_blocking: bool = False) -> bool:
        """Sintetiza y reproduce el texto mediante edge-tts con fallback a SAPI."""
        clean_text = _clean_text_for_speech(text)
        if not clean_text:
            return False

        if non_blocking:
            asyncio.create_task(self._speak_internal(clean_text))
            return True
        return await self._speak_internal(clean_text)

    async def _speak_internal(self, text: str) -> bool:
        async with self._lock:
            self._is_speaking = True
            try:
                # 1. Intentar con edge-tts (voz neuronal de alta fidelidad)
                success = await self._speak_edge_tts(text)
                if success:
                    return True

                # 2. Fallback a Windows SAPI si edge-tts falló o no hay internet
                print("[LocalTTS] Usando fallback offline de Windows SAPI...")
                return await asyncio.to_thread(self._speak_sapi, text)
            finally:
                self._is_speaking = False

    async def _speak_edge_tts(self, text: str) -> bool:
        tmp_path = None
        try:
            import edge_tts

            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=self.rate,
                volume=self.volume,
            )

            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
                tmp_path = f.name

            # Generar audio con timeout de 6s
            await asyncio.wait_for(communicate.save(tmp_path), timeout=6.0)

            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
                return False

            # Reproducir mediante pygame.mixer
            if _PYGAME_AVAILABLE:
                await asyncio.to_thread(self._play_file_sync, tmp_path)
                return True
            return False

        except Exception as exc:
            # print(f"[LocalTTS] edge-tts error: {exc}")
            return False
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def _play_file_sync(self, file_path: str) -> None:
        """Reproduce un archivo mp3 de forma síncrona en un hilo de trabajo."""
        with self._thread_lock:
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                pygame.mixer.music.load(file_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(20)
            except Exception as e:
                print(f"[LocalTTS] Error reproduciendo audio local: {e}")

    def _speak_sapi(self, text: str) -> bool:
        """Habla de forma nativa a través de SAPI (Speech API) de Windows."""
        if not _SAPI_AVAILABLE:
            return False
        try:
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            # Flag 0 = SVSFDefault (síncrono dentro de este hilo de trabajo)
            speaker.Speak(text, 0)
            return True
        except Exception as e:
            print(f"[LocalTTS] Error en Windows SAPI: {e}")
            return False


# Instancia singleton accesible globalmente
local_tts = LocalTTS()
