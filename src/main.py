import asyncio
from src.voice.s2s_client import S2SClient

def main():
    jarvis = S2SClient()
    try:
        asyncio.run(jarvis.connect())
    except KeyboardInterrupt:
        print("\n[Jarvis] Apagando…")
        jarvis.is_running = False

if __name__ == "__main__":
    main()
