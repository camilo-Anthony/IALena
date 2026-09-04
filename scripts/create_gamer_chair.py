import bpy

def create_gamer_chair():
    # Limpiar escena
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    # Base (Silla Gamer)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.5))
    seat = bpy.context.active_object
    seat.scale = (1, 1, 0.2)
    seat.name = "Seat"

    # Respaldo
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.4, 1.2))
    backrest = bpy.context.active_object
    backrest.scale = (0.8, 0.2, 1)
    backrest.name = "Backrest"

    # Patas (Simplificado)
    for x in [-0.4, 0.4]:
        for y in [-0.4, 0.4]:
            bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=0.5, location=(x, y, 0.1))

    return "Gamer chair created."

print(create_gamer_chair())
