@echo off
chcp 65001 >nul
echo Iniciando grabador de muestras de voz para activador personalizado...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\record_wake_word_samples.py
) else (
    python scripts\record_wake_word_samples.py
)
pause
