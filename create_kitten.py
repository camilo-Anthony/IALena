import socket

# Script para crear el gatito básico con primitivas
# Evitamos usar triple comilla dentro del bloque de texto principal para evitar errores de sintaxis
script_gatito = """
import bpy

# Limpiar escena
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Cabeza
bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(0, 0, 0))

# Ojos
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.15, location=(-0.3, -0.7, 0.4))
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.15, location=(0.3, -0.7, 0.4))

# Orejas
bpy.ops.mesh.primitive_cone_add(radius1=0.3, depth=0.6, location=(-0.5, 0, 0.8))
bpy.ops.mesh.primitive_cone_add(radius1=0.3, depth=0.6, location=(0.5, 0, 0.8))

# Cuerpo
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.2, location=(0, 0, -1.8))
# Ajustar cuerpo
bpy.context.object.scale = (0.8, 1, 1.2)

# Cola
bpy.ops.mesh.primitive_cylinder_add(radius=0.1, depth=1.5, location=(0, -1, -2))
bpy.context.object.rotation_euler = (1.5, 0, 0)
"""

def enviar_script_a_blender(script):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', 5250))
        s.send(script.encode('utf-8'))
        s.close()
        return True
    except Exception as e:
        print(f"Error conectando a Blender: {e}")
        return False

if enviar_script_a_blender(script_gatito):
    print("Script de gatito enviado con éxito a Blender.")
else:
    print("Fallo al enviar el script.")
