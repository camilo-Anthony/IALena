# JARVIS - Speech-to-Speech AI Assistant

JARVIS es un asistente de voz en tiempo real impulsado por la API **Gemini Live Multimodal** de Google (carril rápido para baja latencia) y **Hermes Agent** (carril lento para ejecutar tareas complejas, automatizar el navegador, leer archivos y usar la terminal).

Al separar la conversación fluida (Gemini Live) de la ejecución de tareas pesadas (Hermes), JARVIS puede escucharte y responderte al instante, y al mismo tiempo investigar o ejecutar tareas complejas en segundo plano.

## 🚀 Características
* **Comunicación Speech-to-Speech (S2S):** Habla con JARVIS de forma natural. Sin botones de grabar, te escucha en tiempo real.
* **Hermes Agent Integrado:** Cuando le pides algo complejo (ej. "Abre YouTube y pon música", "Busca las últimas noticias", "Resume este PDF"), delega la tarea a su agente interno.
* **Transparencia Anti-Silencios:** Mientras Hermes trabaja, JARVIS te avisará inmediatamente ("Entendido, estoy procesando...") para que no haya silencios incómodos.
* **Rotador Automático de APIs:** Para evadir el error HTTP 429 (Límite de solicitudes de la capa gratuita), el sistema cuenta con un proxy local inteligente que rota automáticamente entre múltiples API Keys de distintos proyectos, haciéndolo 100% transparente.

## 📋 Requisitos
* **Python 3.10 o superior**
* **Micrófono y Altavoces** conectados a la computadora (Windows/Mac/Linux).
* Múltiples [Google Gemini API Keys](https://aistudio.google.com/app/apikey) (Recomendado tener al menos 2 creadas en proyectos de Google Cloud distintos para evadir límites de Rate Limit).

## 🛠️ Instalación y Configuración

### 1. Clonar el repositorio
```bash
git clone https://github.com/camilo-anthony/IALena.git
cd IALena
```

### 2. Ejecutar el Setup Automático (Windows)
En Windows, simplemente haz doble clic en `setup.bat`. Este script se encargará de:
1. Validar tu instalación de Python.
2. Crear un entorno virtual (`.venv`).
3. Instalar todas las dependencias requeridas (incluyendo PyAudio y Google GenAI).
4. Crear la estructura de carpetas necesarias.
5. Generar tu archivo `.env`.

> Si estás en Mac/Linux, puedes hacer lo mismo manualmente:
> `python -m venv .venv` -> `source .venv/bin/activate` -> `pip install -r requirements.txt` -> `cp .env.example .env`

### 3. Configurar tus API Keys
Abre el archivo `.env` que se generó en la carpeta del proyecto y configura tus credenciales:

```env
# JARVIS Voz (Gemini Live - Carril Rápido)
GEMINI_API_KEY=tu_api_key_principal_aqui

# Hermes Agent (Carril Lento)
# Puedes usar 1 o múltiples keys de distintos proyectos de Google Cloud.
# El proxy local rotará entre ellas automáticamente si una se agota (Rate Limit).
HERMES_API_KEY_1=tu_api_key_hermes_1_aqui
HERMES_API_KEY_2=tu_api_key_hermes_2_aqui_opcional
HERMES_API_KEY_3=tu_api_key_hermes_3_aqui_opcional
HERMES_API_KEY_4=tu_api_key_hermes_4_aqui_opcional
```

> Para una referencia completa de **todas** las variables disponibles (Hermes toolsets, VAD, feature flags), consulta el archivo `.env.example`.

## 🎙️ Cómo usar a JARVIS

Para iniciar el asistente, simplemente haz doble clic en:
`start.bat`

Verás en la consola que se inicia el Rotador de Keys local, se conecta a Gemini Live y comenzará a capturar audio.

¡Simplemente háblale!

**Ejemplos de lo que puedes pedir:**
* *"Busca en internet el clima en Tokio para mañana."* (Usará búsqueda web)
* *"Abre YouTube y pon el video musical más reciente de The Weeknd."* (Usará automatización del navegador)
* *"Crea un archivo de texto en mi escritorio con una lista de compras."* (Usará la terminal)

## 🏗️ Arquitectura del Sistema

### Adaptadores (`src/adapters/`)
* `llm/gemini_live_adapter.py`: Maneja el socket en tiempo real con Gemini Live y delega herramientas.
* `llm/play_yt.py`: Herramienta directa para reproducir música de YouTube.
* `brain/hermes_adapter.py`: Adaptador que envuelve al sistema Hermes Agent para actuar como cerebro de JARVIS.
* `brain/key_rotator.py`: Proxy local que rota entre el pool de API Keys de `.env` para evadir límites de cuota.
* `audio/pyaudio_capture.py` y `pyaudio_playback.py`: Manejo asíncrono no-bloqueante de PyAudio.

### Kernel (`src/kernel/`)
* `jarvis_kernel.py`: Orquestador principal del sistema.
* `synapse.py`: Bus de eventos y gestor de estados para coordinar agentes de forma thread-safe con cancelación cooperativa.
* `action_router.py`: Envía peticiones al Cerebro (Hermes) en background coordinando mediante la Synapse.
* `context_manager.py`: Gestión de contexto Live + inyección de identidad, memoria y skills de Hermes.
* `cognitive_policy.py`: Políticas de intención, feature flags (`ENABLE_MUSIC_TOOL`, `STRICT_HERMES_INTENT_GATE`).
* `conversation_session.py`: Gestión de sesiones de conversación persistentes.
* `activation_gate.py`: Gate de activación para filtrar invocaciones a Hermes.
* `task_ledger.py`: Registro y seguimiento de tareas delegadas.

### Submódulo
* `Hermes-Agent/`: Agente autómata especializado en ejecución de tareas complejas.

