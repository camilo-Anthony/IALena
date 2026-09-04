@echo off
title JARVIS - Start
color 0B
echo.
echo        _      _      ____   __     __  ___   ____
echo       ^| ^|    / \    ^|  _ \  \ \   / / ^|_ _^| / ___^|
echo    _  ^| ^|   / _ \   ^| ^|_) ^|  \ \ / /   ^| ^|  \___ \
echo   ^| ^|_^| ^|  / ___ \  ^|  _ ^<    \ V /    ^| ^|   ___) ^|
echo    \___/  /_/   \_\ ^|_^| \_\    \_/    ^|___^| ^|____/
echo.
echo =======================================================
echo     I N I C I A N D O   C O R E   S I S T E M A S
echo =======================================================
echo.

:: Check if setup has been done
if not exist ".venv" (
    echo [!] ERROR: El entorno virtual no existe.
    echo [!] Por favor ejecuta setup.bat primero.
    echo.
    pause
    exit /b 1
)

:: Set PYTHONPATH to include the root folder so 'src' package imports work
set PYTHONPATH=%CD%

:: Activate virtual environment
call .venv\Scripts\activate.bat

:: Check .env exists
if not exist ".env" (
    echo [!] ADVERTENCIA: No se encontro el archivo .env!
    echo [!] Creando plantilla por defecto...
    copy .env.example .env >nul
    echo [!] Abre el archivo .env, pon tus API Keys, y vuelve a correr este archivo.
    echo.
    pause
    exit /b 1
)

:: Check if the user left the default API key template
findstr "tu_api_key_principal_aqui" .env >nul
if %errorlevel%==0 (
    echo [!] ADVERTENCIA: Aún no has configurado tus API Keys en el archivo .env.
    echo [!] Por favor abre el archivo .env, coloca tus keys reales de Google AI Studio,
    echo [!] y luego vuelve a correr start.bat.
    echo.
    pause
    exit /b 1
)

:: Create data dirs if missing
if not exist "data" mkdir data
if not exist "data\logs" mkdir data\logs

echo [+] Modulos cargados y verificados.
echo [+] Levantando Backend FastAPI + Kernel en segundo plano...
start "JARVIS Backend" /Min cmd /c "call .venv\Scripts\activate.bat && python -m src.main"

echo [+] Levantando Hermes Native Renderer en segundo plano...
start "Hermes UI" /Min cmd /c "cd Hermes-Agent\apps\desktop && npm run dev:renderer"

echo [+] Levantando Interfaz de Escritorio Tauri...
cd apps\jarvis-desktop
npm run tauri dev

echo.
echo JARVIS ha sido apagado.
pause
