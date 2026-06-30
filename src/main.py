import asyncio
from src.voice.s2s_client import S2SClient

def main():
    ialena = S2SClient()
    try:
        asyncio.run(ialena.connect())
    except KeyboardInterrupt:
        print("\n[IALena] Apagando…")
        ialena.is_running = False

if __name__ == "__main__":
    main()
