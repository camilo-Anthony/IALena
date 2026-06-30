"""
J.A.R.V.I.S. — Configuración central
Arquitectura: Speech-to-Speech (Gemini Live) + Hermes Agent
"""

import os
from pathlib import Path
# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings
# pyrefly: ignore [missing-import]
from pydantic import Field


class IALenaSettings(BaseSettings):
    """Configuración para el sistema S2S + Hermes."""

    # ── Paths ──────────────────────────────────────────────
    base_dir: Path = Field(default_factory=lambda: Path(__file__).parent)
    data_dir: Path = Field(default_factory=lambda: Path(__file__).parent / "data")
    db_path:  Path = Field(default_factory=lambda: Path(__file__).parent / "data" / "ialena.db")
    log_dir:  Path = Field(default_factory=lambda: Path(__file__).parent / "data" / "logs")

    # ── API Keys ───────────────────────────────────────────
    google_api_key: str = ""
    gemini_api_key: str = ""

    # ── Gemini Live ────────────────────────────────────────
    model_live:  str = "gemini-2.5-flash-native-audio-latest"
    model_brain: str = "gemini-2.5-flash-lite"   # Hermes (Carril Lento)
    voice_name:  str = "Aoede"
    input_rate:  int = 16_000
    output_rate: int = 24_000

    # ── Budget tracking ────────────────────────────────────
    daily_budget:   float = 5.0
    monthly_budget: float = 50.0

    # ── Personalidad ──────────────────────────────────────
    assistant_name: str = "IALena"
    user_name:      str = "Señor"
    language:       str = "es"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    def ensure_directories(self):
        """Crea los directorios necesarios si no existen."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


# Instancia global
settings = IALenaSettings()
settings.ensure_directories()
