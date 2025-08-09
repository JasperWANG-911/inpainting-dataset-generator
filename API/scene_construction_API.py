import bpy
import os
import math
import random
import mathutils
from mathutils import Vector



# Function to clear the current scene
def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

# Function to add ground plane. Object called "ground" will be created.
def add_ground(size=50):
    # create a plane
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.name = "ground"
    
    # add rigid body physics to the ground
    bpy.ops.rigidbody.object_add()
    ground.rigid_body.type = 'PASSIVE'  
    ground.rigid_body.collision_shape = 'MESH' 

    # Set friction and restitution - these can be adjusted as needed
    ground.rigid_body.friction = 0.5  # Affects how the object slides on the ground
    ground.rigid_body.restitution = 0.1  # Affects how the object bounces when dropped

    # Material - purely visual, optional
    mat = bpy.data.materials.new(name="GroundMaterial")
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs[0].default_value = (0.5, 0.5, 0.5, 1.0)
    ground.data.materials.append(mat)
    
    return ground

# Function to import objects
def import_object(filepath, object_name=None):
    """Import 3D object from file with optional renaming"""
    # Ensure file exists
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}")
        return
    
    # get the file extension
    ext = os.path.splitext(filepath)[1].lower()
    
    # Store list of objects before import
    objects_before = set(bpy.data.objects)
    
    # import based on file type
    try:
        if ext == '.obj':
            # Enable OBJ import addon if not enabled
            if 'import_scene.obj' not in dir(bpy.ops):
                bpy.ops.preferences.addon_enable(module='io_scene_obj')
            bpy.ops.import_scene.obj(filepath=filepath)
        elif ext == '.fbx':
            # Enable FBX import addon if not enabled
            if 'import_scene.fbx' not in dir(bpy.ops):
                bpy.ops.preferences.addon_enable(module='io_scene_fbx')
            bpy.ops.import_scene.fbx(filepath=filepath)
        elif ext == '.gltf' or ext == '.glb':
            # Enable glTF import addon if not enabled
            if 'import_scene.gltf' not in dir(bpy.ops):
                bpy.ops.preferences.addon_enable(module='io_scene_gltf2')
            bpy.ops.import_scene.gltf(filepath=filepath)
        elif ext == '.blend':
            # For .blend files, we need to append objects
            with bpy.data.libraries.load(filepath) as (data_from, data_to):
                data_to.objects = data_from.objects[:]
            
            # Link objects to the scene
            for obj in data_to.objects:
                if obj is not None:
                    bpy.context.collection.objects.link(obj)
        else:
            print(f"Unsupported file type: {ext}")
            return
            
        print(f"Successfully imported: {filepath}")
        
        # Get newly imported objects
        objects_after = set(bpy.data.objects)
        new_objects = objects_after - objects_before
        
        # If object_name is provided and we have new objects, rename them
        if object_name and new_objects:
            if len(new_objects) == 1:
                # Single object - rename it directly
                obj = list(new_objects)[0]
                obj.name = object_name
                print(f"Renamed imported object to: {object_name}")
            else:
                # Multiple objects - rename with suffixes
                for i, obj in enumerate(new_objects):
                    if i == 0:
                        obj.name = object_name
                    else:
                        obj.name = f"{object_name}.{i:03d}"
                print(f"Renamed {len(new_objects)} imported objects with base name: {object_name}")
        
    except Exception as e:
        print(f"Error during import of {filepath}: {str(e)}")
        raise

# Function to stick object to the ground
def stick_object_to_ground(object):
    # obtain the ground object
    ground = bpy.data.objects.get("ground")

    # object to stick
    obj = bpy.data.objects.get(object)

    # stick the object to the ground
    constraint = obj.constraints.new('SHRINKWRAP')
    constraint.target = ground
    constraint.shrinkwrap_type = 'NEAREST_SURFACE'
    constraint.use_track_normal = True
    constraint.track_axis = 'TRACK_Z'

# Function to move objects to some random position without collision with existing objects
def place_object_avoiding_collision(new_object_name, excluded_objects=["ground"], max_attempts=100, safety_distance=0.5):
   # internal function to check if a point is inside a bounding box
   def is_point_inside_bbox(point, bbox_min, bbox_max):
       return (bbox_min.x <= point.x <= bbox_max.x and
               bbox_min.y <= point.y <= bbox_max.y and
               bbox_min.z <= point.z <= bbox_max.z)
   
   # obtain the objects
   ground = bpy.data.objects.get("ground")
   new_obj = bpy.data.objects.get(new_object_name)
   house = bpy.data.objects.get("house")

   # obtain the objects to avoid collisions
   obstacles = []
   for obj in bpy.context.scene.objects:
       if (obj.type == 'MESH' and 
           obj.name != new_object_name and 
           obj.name not in excluded_objects):
           obstacles.append(obj)
   
   # obtain the ground's boundary
   ground_min = Vector([min([v[i] for v in ground.bound_box]) for i in range(3)])
   ground_max = Vector([max([v[i] for v in ground.bound_box]) for i in range(3)])
   ground_min = ground.matrix_world @ ground_min
   ground_max = ground.matrix_world @ ground_max
   
   # obtain the house's boundary
   house_min = None
   house_max = None
   if house:
       house_bbox = [house.matrix_world @ Vector(v) for v in house.bound_box]
       house_min = Vector([min([v[i] for v in house_bbox]) for i in range(3)])
       house_max = Vector([max([v[i] for v in house_bbox]) for i in range(3)])
       # expand the house's boundary to avoid collisions
       house_min -= Vector((safety_distance, safety_distance, 0))
       house_max += Vector((safety_distance, safety_distance, 0))

   # obtain the new object's size
   obj_size = Vector([max([v[i] for v in new_obj.bound_box]) - min([v[i] for v in new_obj.bound_box]) for i in range(3)])
   
   # try to place the object
   for attempt in range(max_attempts):
       # random position within the ground's boundary
       x = random.uniform(ground_min.x + obj_size.x/2, ground_max.x - obj_size.x/2)
       y = random.uniform(ground_min.y + obj_size.y/2, ground_max.y - obj_size.y/2)
       
       # if house is present, check if the position is inside the house's bounding box
       if house and is_point_inside_bbox(Vector((x, y, 0)), house_min, house_max):
           continue  # skip this position if it's inside the house's bounding box
       
       # set the new object's location
       new_obj.location = Vector((x, y, ground.location.z))

       # obtain the new object's bounding box
       obj_bbox = [new_obj.matrix_world @ Vector(v) for v in new_obj.bound_box]
       obj_min = Vector([min([v[i] for v in obj_bbox]) for i in range(3)])
       obj_max = Vector([max([v[i] for v in obj_bbox]) for i in range(3)])

       # check if the new object's bounding box overlaps with any obstacles
       collision_found = False
       for obstacle in obstacles:
           # obtain the obstacle's bounding box
           obs_bbox = [obstacle.matrix_world @ Vector(v) for v in obstacle.bound_box]
           obs_min = Vector([min([v[i] for v in obs_bbox]) for i in range(3)])
           obs_max = Vector([max([v[i] for v in obs_bbox]) for i in range(3)])
           
           # check if the bounding boxes overlap
           if not (obj_max.x < obs_min.x or obj_min.x > obs_max.x or
                   obj_max.y < obs_min.y or obj_min.y > obs_max.y):
               collision_found = True
               break
       
       if not collision_found:
           # finalize the position
           stick_object_to_ground(new_object_name)
           return True
   
   return False

# Function to scale an object(must be a mesh)
def scale_object(object_name, scale_factor):
    obj = bpy.data.objects.get(object_name)
    if obj and obj.type == 'MESH':
        # Scale the object
        obj.scale = Vector((scale_factor, scale_factor, scale_factor))
        # Update the object's bounding box
        obj.update_from_editmode()
        return True
    else:
        print(f"Object {object_name} not found or is not a mesh.")
        return False