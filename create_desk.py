import bpy

def create_desk():
    # Limpiar escena
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # Superficie del escritorio
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.75))
    desk_top = bpy.context.active_object
    desk_top.scale = (1.5, 0.8, 0.05)
    
    # Patas
    for x, y in [(-0.7, -0.35), (0.7, -0.35), (-0.7, 0.35), (0.7, 0.35)]:
        bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=0.7, location=(x, y, 0.35))
    
    # Cajones
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.6))
    drawers = bpy.context.active_object
    drawers.scale = (0.6, 0.7, 0.25)
    
    # Material simple (Color marrón)
    mat = bpy.data.materials.new(name="Wood")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs[0].default_value = (0.5, 0.3, 0.1, 1)
    
    for obj in [desk_top, drawers]:
        obj.data.materials.append(mat)

create_desk()
