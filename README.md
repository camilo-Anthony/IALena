# J.A.R.V.I.S. - Speech-to-Speech AI Assistant

J.A.R.V.I.S. es un asistente de voz en tiempo real impulsado por la API **Gemini Live Multimodal** de Google (carril rápido para baja latencia) y **Hermes Agent** (carril lento para ejecutar tareas complejas, automatizar el navegador, leer archivos y usar la terminal).

Al separar la conversación fluida (Gemini Live) de la ejecución de tareas pesadas (Hermes), IALena puede escucharte y responderte al instante, y al mismo tiempo investigar o ejecutar tareas complejas en segundo plano.

## 🚀 Características
* **Comunicación Speech-to-Speech (S2S):** Habla con IALena de forma natural. Sin botones de grabar, te escucha en tiempo real.
* **Hermes Agent Integrado:** Cuando le pides algo complejo (ej. "Abre YouTube y pon música", "Busca las últimas noticias", "Resume este PDF"), delega la tarea a su agente interno.
* **Transparencia Anti-Silencios:** Mientras Hermes trabaja, IALena te avisará inmediatamente ("Entendido, estoy procesando...") para que no haya silencios incómodos.
* **Rotador Automático de APIs:** Para evadir el error HTTP 429 (Límite de solicitudes de la capa gratuita), el sistema cuenta con un proxy local inteligente que rota automáticamente entre múltiples API Keys de distintos proyectos, haciéndolo 100% transparente.

## 📋 Requisitos
* **Python 3.10 o superior**
* **Micrófono y Altavoces** conectados a la computadora (Windows/Mac/Linux).
* Múltiples [Google Gemini API Keys](https://aistudio.google.com/app/apikey) (Recomendado tener al menos 2 creadas en proyectos de Google Cloud distintos para evadir límites de Rate Limit).

## 🛠️ Instalación y Configuración

### 1. Clonar el repositorio
```bash
git clone https://github.com/tu-usuario/IALena.git
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
# IALena Voz (Gemini Live - Carril Rápido)
GEMINI_API_KEY=tu_api_key_gemini_aqui

# Hermes Agent (Carril Lento)
# Puedes usar 1 o múltiples keys de distintos proyectos de Google Cloud.
# El proxy local rotará entre ellas automáticamente si una se agota (Rate Limit).
HERMES_API_KEY_1=tu_api_key_proyecto_1
HERMES_API_KEY_2=tu_api_key_proyecto_2
```

## 🎙️ Cómo usar a IALena

Para iniciar el asistente, simplemente haz doble clic en:
`start.bat`

Verás en la consola que se inicia el Rotador de Keys local, se conecta a Gemini Live y comenzará a capturar audio.

¡Simplemente háblale!

**Ejemplos de lo que puedes pedir:**
* *"Busca en internet el clima en Tokio para mañana."* (Usará búsqueda web)
* *"Abre YouTube y pon el video musical más reciente de The Weeknd."* (Usará automatización del navegador)
* *"Crea un archivo de texto en mi escritorio con una lista de compras."* (Usará la terminal)

## 🏗️ Arquitectura del Sistema
* `src/voice/s2s_client.py`: Maneja el socket en tiempo real con Gemini Live y delega herramientas.
* `src/voice/key_rotator.py`: Proxy local (puerto 8765) que engaña al Agente haciéndole creer que usa una sola Key, pero rota entre el pool de `.env` internamente.
* `src/voice/audio_capture.py` y `audio_playback.py`: Manejo asíncrono no-bloqueante de PyAudio.
* `Hermes-Agent/`: Submódulo del agente autómata especializado en ejecución de código.
