import bpy

def create_chair():
    # Clear existing mesh objects
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    # 1. Create Seat
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
    seat = bpy.context.active_object
    seat.name = "Seat"
    seat.scale = (1, 1, 0.1)

    # 2. Create Legs
    leg_offset = 0.8
    leg_height = 1.0
    leg_thickness = 0.1
    
    leg_positions = [
        (leg_offset, leg_offset, 0.5),
        (-leg_offset, leg_offset, 0.5),
        (leg_offset, -leg_offset, 0.5),
        (-leg_offset, -leg_offset, 0.5)
    ]

    for i, pos in enumerate(leg_positions):
        bpy.ops.mesh.primitive_cube_add(size=2, location=pos)
        leg = bpy.context.active_object
        leg.name = f"Leg_{i+1}"
        leg.scale = (leg_thickness, leg_thickness, 0.5)

    # 3. Create Backrest
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, leg_offset, 2))
    backrest = bpy.context.active_object
    backrest.name = "Backrest"
    backrest.scale = (1, 0.1, 1)

    # 4. Add Camera
    bpy.ops.object.camera_add(location=(5, -5, 5), rotation=(1.1, 0, 0.785))
    bpy.context.scene.camera = bpy.context.active_object

    # 5. Add Light
    bpy.ops.object.light_add(type='POINT', location=(5, 5, 5))
    light = bpy.context.active_object
    light.data.energy = 1000

    # Final cleanup: select none
    bpy.ops.object.select_all(action='DESELECT')
    
    # Save the file
    bpy.ops.wm.save_as_mainfile(filepath="C:/Users/hp/Documents/PROYECTOS/JARVIS/chair.blend")
    
    # Render the image
    bpy.context.scene.render.filepath = "C:/Users/hp/Documents/PROYECTOS/JARVIS/chair.png"
    bpy.ops.render.render(write_still=True)

if __name__ == "__main__":
    create_chair()
