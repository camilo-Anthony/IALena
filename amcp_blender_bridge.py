import bpy
import socket
import threading

# Ejemplo conceptual de puente AMCP -> Blender
# Este script debe ejecutarse dentro de Blender
def handle_amcp_command(command):
    # Traducción simple de comandos AMCP a API bpy
    # Ejemplo: 'PLAY 1-1 CUBE' -> bpy.ops.mesh.primitive_cube_add()
    print(f"Comando AMCP recibido: {command}")
    if "CUBE" in command:
        bpy.ops.mesh.primitive_cube_add(size=2)
    return "200 OK"

def amcp_server():
    host = '127.0.0.1'
    port = 5250 # Puerto estándar AMCP
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((host, port))
    s.listen(5)
    print(f"AMCP Server listening on {host}:{port}")
    while True:
        conn, addr = s.accept()
        data = conn.recv(1024).decode()
        if data:
            response = handle_amcp_command(data)
            conn.send(response.encode())
        conn.close()

# Ejecutar en hilo separado para no bloquear la UI de Blender
threading.Thread(target=amcp_server, daemon=True).start()
