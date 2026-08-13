import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from src.server.routes import status, config, actions, logs, hermes
from src.server.events import register, unregister, start_event_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("JARVIS.API")

app = FastAPI(title="JARVIS local API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(status.router)
app.include_router(config.router)
app.include_router(actions.router)
app.include_router(logs.router)
app.include_router(hermes.router)

@app.get("/")
def index():
    return {"message": "JARVIS API local activa"}

@app.websocket("/events")
async def websocket_events(websocket: WebSocket):
    await websocket.accept()
    await register(websocket)
    try:
        while True:
            # Mantener conexión activa y responder a pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        await unregister(websocket)

@app.on_event("startup")
async def startup_event():
    # Iniciar el loop background que transmite eventos del kernel
    asyncio.create_task(start_event_loop())
    logger.info("FastAPI background event loop iniciado.")
