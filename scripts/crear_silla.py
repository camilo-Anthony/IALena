import bpy

# Script para generar una silla básica mediante bpy
def crear_silla():
    # Limpiar escena
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # Asiento
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 1))
    asiento = bpy.context.active_object
    asiento.scale = (1, 1, 0.2)
    
    # Patas
    offsets = [(-0.4, -0.4), (0.4, -0.4), (-0.4, 0.4), (0.4, 0.4)]
    for x, y in offsets:
        bpy.ops.mesh.primitive_cube_add(size=0.2, location=(x, y, 0.4))
        pata = bpy.context.active_object
        pata.scale = (0.5, 0.5, 4)
        
    # Respaldo
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.4, 1.8))
    respaldo = bpy.context.active_object
    respaldo.scale = (1, 0.2, 1.5)

crear_silla()
print("Silla creada con éxito.")
