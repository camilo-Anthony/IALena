import bpy

# Crear silla simple
def crear_silla():
    # Limpiar escena
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # Asiento
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.5))
    asiento = bpy.context.object
    asiento.scale = (1, 1, 0.1)

    # Patas
    posiciones = [(0.4, 0.4, 0), (0.4, -0.4, 0), (-0.4, 0.4, 0), (-0.4, -0.4, 0)]
    for x, y, z in posiciones:
        bpy.ops.mesh.primitive_cube_add(size=0.15, location=(x, y, 0.2))
        pata = bpy.context.object
        pata.scale = (1, 1, 3)

    # Respaldo
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.4, 1))
    respaldo = bpy.context.object
    respaldo.scale = (1, 0.1, 1.5)

crear_silla()
