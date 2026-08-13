import sys
import urllib.request
import urllib.parse
import re
import webbrowser

def play_on_youtube(query: str):
    try:
        # Modificar query para buscar versiones con letra
        if "letras" not in query.lower() and "lyrics" not in query.lower():
            query += " lyrics"

        query_string = urllib.parse.urlencode({"search_query": query})
        url = "https://www.youtube.com/results?" + query_string
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        html_content = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')

        # Buscar videoId en el JSON de respuesta
        match = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', html_content)
        if match:
            video_id = match.group(1)
            video_url = "https://www.youtube.com/watch?v=" + video_id
            print(f"Abriendo {video_url} ...")
            # Cerrar pestañas anteriores antes de abrir la nueva
            import subprocess
            subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe', '/FI', 'WINDOWTITLE eq YouTube*'], capture_output=True)
            webbrowser.open(video_url, new=0)
        else:
            print("No se encontraron videos específicos. Abriendo página de resultados.")
            subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe', '/FI', 'WINDOWTITLE eq YouTube*'], capture_output=True)
            webbrowser.open(url, new=0) # Fallback a la pagina de busqueda
    except Exception as e:
        print(f"Error al buscar en YouTube: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        play_on_youtube(query)
    else:
        print("Uso: python play_yt.py <nombre de la cancion>")
