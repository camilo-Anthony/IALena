@echo off
title J.A.R.V.I.S. - Setup
color 0B
echo.
echo        _      _      ____   __     __  ___   ____
echo       ^| ^|    / \    ^|  _ \  \ \   / / ^|_ _^| / ___^|
echo    _  ^| ^|   / _ \   ^| ^|_) ^|  \ \ / /   ^| ^|  \___ \
echo   ^| ^|_^| ^|  / ___ \  ^|  _ ^<    \ V /    ^| ^|   ___) ^|
echo    \___/  /_/   \_\ ^|_^| \_\    \_/    ^|___^| ^|____/
echo.
echo =======================================================
echo          S T A R T I N G   S E T U P
echo =======================================================
echo.

:: Check Python
echo [1/4] Comprobando instalacion de Python...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] ERROR: Python no esta instalado o no esta en el PATH.
    echo [!] Por favor instala Python 3.10+ desde https://python.org
    echo.
    pause
    exit /b 1
)
echo       [+] Python detectado.
echo.

:: Create virtual environment
echo [2/4] Creando entorno virtual aislado (.venv)...
if not exist ".venv" (
    python -m venv .venv
    echo       [+] Entorno virtual creado exitosamente.
) else (
    echo       [+] El entorno virtual ya existe.
)
echo.

:: Activate and install dependencies
echo [3/4] Instalando dependencias de IALena...
call .venv\Scripts\activate.bat
echo       [+] Actualizando pip...
python -m pip install --upgrade pip >nul 2>&1
echo       [+] Instalando requirements.txt...
pip install -r requirements.txt
echo       [+] Dependencias instaladas!
echo.

:: Create .env from template
echo [4/4] Configurando variables de entorno...
if not exist ".env" (
    copy .env.example .env >nul
    echo       [+] Plantilla .env creada.
    echo       [!] MUY IMPORTANTE: Debes editar el archivo .env para poner tus API Keys.
) else (
    echo       [+] El archivo .env ya existe.
)
echo.

echo =======================================================
echo                 S E T U P   L I S T O !
echo =======================================================
echo.
echo Pasos finales:
echo  1. Abre el archivo .env con cualquier block de notas.
echo  2. Pega tus API Keys de Google AI Studio.
echo  3. Haz doble clic en start.bat para iniciar a IALena.
echo.
pause
