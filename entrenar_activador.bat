@echo off
chcp 65001 >nul
title Entrenar Activador Personalizado (JARVIS / Tess)
cls
echo ====================================================================
echo   🧠 ENTRENAMIENTO LOCAL DE ACTIVADOR PERSONALIZADO (openWakeWord)
echo ====================================================================
echo.

set "VENV_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%VENV_PYTHON%" (
    echo [ERROR] No se encontro el interprete Python del proyecto en:
    echo %VENV_PYTHON%
    echo Ejecuta: python -m venv .venv
    pause
    exit /b 1
)

echo [INFO] Ejecutando entrenamiento neuronal con tus grabaciones...
"%VENV_PYTHON%" scripts\train_local_wake_word.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Ocurrio un error durante el entrenamiento.
    pause
    exit /b 1
)

echo.
echo ====================================================================
echo   🎉 ¡ENTRENAMIENTO COMPLETADO CON ÉXITO!
echo   El modelo 'models/tess.onnx' está listo para usar con JARVIS.
echo ====================================================================
echo.
pause
