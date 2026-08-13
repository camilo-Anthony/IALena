"""
key_rotator.py — Proxy local de rotación de API keys para Hermes.

Hermes hace peticiones de "discovery" (Ollama-style) para detectar el servidor.
Este proxy:
  - Intercepta esas rutas y devuelve respuestas mock para no spamear Google.
  - Solo reenvía a Google las rutas reales (/v1/chat/completions, etc.)
    rotando la API key en cada llamada.

Arquitectura:
              Hermes
                │
                ▼
     http://localhost:8765
          │              │
     Discovery paths    Real LLM paths
     (mock 200 OK)     /v1/chat/completions
                              │
                    Rota entre Key-1, Key-2...
                              │
                    Google Gemini API
"""
import itertools
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib import request as urllib_request
from urllib.error import HTTPError

PROXY_PORT   = 8765
GOOGLE_BASE  = "https://generativelanguage.googleapis.com/v1beta/openai"
_CLIENT_DISCONNECT_ERRORS = (ConnectionAbortedError, BrokenPipeError, ConnectionResetError)

# Rutas que SÍ se reenvían a Google (llamadas LLM reales)
_REAL_PATHS = {
    "/v1/chat/completions",
    "/v1/embeddings",
    "/v1/completions",
    "/chat/completions",       # sin prefijo /v1
}

import os

# Modelo que reportamos en las respuestas de discovery
_MODEL_ID = os.getenv("MODEL_BRAIN", "gemini-3.1-flash-lite")


def _mock_models():
    return json.dumps({
        "object": "list",
        "data": [{"id": _MODEL_ID, "object": "model", "owned_by": "google"}]
    }).encode()


# Respuestas mock por ruta de discovery
_MOCK_RESPONSES: dict[str, bytes] = {
    "/v1/models":       _mock_models(),
    "/api/v1/models":   _mock_models(),
    "/api/tags":        json.dumps({"models": [{"name": _MODEL_ID}]}).encode(),
    "/version":         json.dumps({"version": "0.1.0"}).encode(),
    "/api/version":     json.dumps({"version": "0.1.0"}).encode(),
    "/v1/props":        json.dumps({"status": "ok"}).encode(),
    "/props":           json.dumps({"status": "ok"}).encode(),
    "/api/show":        json.dumps({"name": _MODEL_ID}).encode(),
}


class _RotatingProxy(BaseHTTPRequestHandler):
    """Reenvía peticiones reales a Google rotando la API key."""

    _keys: list[str] = []
    _key_cycle: itertools.cycle | None = None
    _call_counter: int = 0
    _lock = threading.Lock()

    def log_message(self, format, *args):
        # Silenciar logs normales; solo mostrar errores reales de Google
        pass

    def do_POST(self):
        self._handle("POST")

    def do_GET(self):
        self._handle("GET")

    def _client_disconnected(self, method: str, path: str):
        print(f"[KeyRotator] Cliente cerro conexion para {method} {path}; respuesta descartada.")

    def _handle(self, method: str):
        path = self.path.split("?")[0]

        # ── Discovery / probe: respuesta mock inmediata ───────────────────
        if path in _MOCK_RESPONSES:
            body = _MOCK_RESPONSES[path]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except _CLIENT_DISCONNECT_ERRORS:
                self._client_disconnected(method, path)
            return

        # ── Ruta desconocida → OK genérico ───────────────────────────────
        if not any(path.endswith(r.lstrip("/")) for r in _REAL_PATHS):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            try:
                self.wfile.write(b"{}")
            except _CLIENT_DISCONNECT_ERRORS:
                self._client_disconnected(method, path)
            return

        # ── Ruta LLM real: reenviar a Google rotando claves ───────────────
        # Construir URL destino (quitar /v1/ duplicado)
        clean_path = path.lstrip("/")
        if clean_path.startswith("v1/"):
            clean_path = clean_path[3:]
        target_url = f"{GOOGLE_BASE}/{clean_path}"

        length = int(self.headers.get("Content-Length", 0))
        body_in = self.rfile.read(length) if length else None
        content_type = self.headers.get("Content-Type", "application/json")

        # Obtener todas las claves del pool para iterar sobre ellas
        with _RotatingProxy._lock:
            keys = list(_RotatingProxy._keys)
            start_idx = _RotatingProxy._call_counter % len(keys)
            _RotatingProxy._call_counter += 1

        # ── Retry transparente: prueba cada key antes de devolver error ───
        # Hermes NUNCA verá un 429 mientras haya al menos una key con cuota.
        last_body_err = None
        last_code = 429
        for i in range(len(keys)):
            api_key = keys[(start_idx + i) % len(keys)]
            headers = {
                "Content-Type":  content_type,
                "Authorization": f"Bearer {api_key}",
            }
            req = urllib_request.Request(
                target_url, data=body_in, headers=headers, method=method
            )
            try:
                with urllib_request.urlopen(req, timeout=120) as resp:
                    body_out = resp.read()
                    self.send_response(resp.status)
                    for h, v in resp.headers.items():
                        if h.lower() not in ("transfer-encoding", "connection"):
                            self.send_header(h, v)
                    self.end_headers()
                    try:
                        self.wfile.write(body_out)
                    except _CLIENT_DISCONNECT_ERRORS:
                        self._client_disconnected(method, path)
                        return
                    print(f"[KeyRotator] ✅ {method} {path} → Key-{(start_idx+i)%len(keys)+1} (...{api_key[-6:]})")
                    return  # éxito — salir

            except HTTPError as e:
                last_body_err = e.read()
                last_code = e.code
                if e.code in (429, 503):
                    print(f"[KeyRotator] ↩ Key-{(start_idx+i)%len(keys)+1} agotada ({e.code}), probando siguiente…")
                    continue   # rotar a la siguiente key
                # Error distinto a cuota → devolver de inmediato
                self.send_response(e.code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(last_body_err)))
                self.end_headers()
                try:
                    self.wfile.write(last_body_err)
                except _CLIENT_DISCONNECT_ERRORS:
                    self._client_disconnected(method, path)
                return

            except _CLIENT_DISCONNECT_ERRORS:
                self._client_disconnected(method, path)
                return

            except Exception as e:
                print(f"[KeyRotator] ❌ Error de red: {e}")
                try:
                    self.send_response(502)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode())
                except _CLIENT_DISCONNECT_ERRORS:
                    self._client_disconnected(method, path)
                return

        # Todas las keys agotadas → devolver el último error al cliente
        print(f"[KeyRotator] ⚠️  Todas las keys agotadas para {path}")
        try:
            self.send_response(last_code)
            self.send_header("Content-Type", "application/json")
            if last_body_err:
                self.send_header("Content-Length", str(len(last_body_err)))
            self.end_headers()
            self.wfile.write(last_body_err or b"{}")
        except _CLIENT_DISCONNECT_ERRORS:
            self._client_disconnected(method, path)


_active_proxy_port = None

def start_proxy(keys: list[str], port: int = PROXY_PORT) -> int:
    """
    Inicia el proxy en un hilo daemon. Devuelve el puerto en uso.
    Prueba puertos sucesivos si el inicial está ocupado.
    Reutiliza la instancia del proxy si ya está iniciada.
    """
    global _active_proxy_port
    if not keys:
        raise ValueError("Se necesita al menos una API key en el pool")

    _RotatingProxy._keys = list(keys)
    _RotatingProxy._key_cycle = itertools.cycle(keys)
    _RotatingProxy._call_counter = 0

    if _active_proxy_port is not None:
        key_shorts = [f"...{k[-6:]}" for k in keys]
        print(f"\033[33m[KeyRotator]\033[0m Pool de llaves actualizado en proxy activo (puerto {_active_proxy_port}, {len(keys)} clave(s): {key_shorts})")
        return _active_proxy_port

    current_port = port
    max_attempts = 20
    server = None

    for attempt in range(max_attempts):
        try:
            server = HTTPServer(("127.0.0.1", current_port), _RotatingProxy)
            break
        except OSError as e:
            print(f"\033[33m[KeyRotator]\033[0m Puerto {current_port} ocupado. Probando el siguiente...")
            current_port += 1

    if not server:
        raise OSError(f"No se pudo iniciar el proxy de claves en ningún puerto del {port} al {port + max_attempts - 1}")

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    _active_proxy_port = current_port
    key_shorts = [f"...{k[-6:]}" for k in keys]
    print(f"\033[33m[KeyRotator]\033[0m Proxy iniciado en http://127.0.0.1:{current_port}")
    print(f"\033[33m[KeyRotator]\033[0m Pool de {len(keys)} clave(s): {key_shorts}")
    return current_port
