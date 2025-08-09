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

# Function to place all objects randomly around the house for occlusion
# Debug version to test in system
# Function to place all objects randomly around the house for occlusion
def place_objects_around_house(excluded_objects=["ground", "house"], 
                               min_distance=2.0, 
                               max_distance=15.0, 
                               cluster_probability=0.3,
                               max_attempts_per_object=50):
    """
    Place all objects randomly around the house for creating occlusion datasets.
    
    Args:
        excluded_objects: List of object names to exclude from repositioning
        min_distance: Minimum distance from house center (meters)
        max_distance: Maximum distance from house center (meters)
        cluster_probability: Probability that an object will be placed near another object
        max_attempts_per_object: Maximum placement attempts per object
    """
    import math
    
    # Get house and ground references
    house = bpy.data.objects.get("house")
    ground = bpy.data.objects.get("ground")
    
    if not house or not ground:
        print("Error: House or ground not found in scene")
        return False
    
    # Get house bounding box and center
    house_bbox = [house.matrix_world @ Vector(v) for v in house.bound_box]
    house_center = sum(house_bbox, Vector()) / len(house_bbox)
    house_center.z = 0  # Project to ground level
    
    # Calculate house dimensions for better placement
    house_min = Vector([min([v[i] for v in house_bbox]) for i in range(3)])
    house_max = Vector([max([v[i] for v in house_bbox]) for i in range(3)])
    house_width = house_max.x - house_min.x
    house_depth = house_max.y - house_min.y
    
    # Adjust min distance based on house size
    actual_min_distance = min_distance + max(house_width, house_depth) / 2
    
    # Get all objects to reposition
    objects_to_place = []
    for obj in bpy.context.scene.objects:
        if (obj.type == 'MESH' and 
            obj.name not in excluded_objects):
            objects_to_place.append(obj)
    
    if not objects_to_place:
        print("No objects to place around house")
        return True
    
    # Shuffle objects for random placement order
    random.shuffle(objects_to_place)
    
    # Track placed objects for clustering
    placed_objects = []
    
    # Place each object
    for obj in objects_to_place:
        placed = False
        
        for attempt in range(max_attempts_per_object):
            # Decide if this object should cluster near another
            if placed_objects and random.random() < cluster_probability:
                # Choose a random already-placed object to cluster near
                target_obj = random.choice(placed_objects)
                
                # Place near the target object
                angle_offset = random.uniform(0, 2 * math.pi)
                distance_offset = random.uniform(1.0, 3.0)  # Distance from target object
                
                x = target_obj.location.x + distance_offset * math.cos(angle_offset)
                y = target_obj.location.y + distance_offset * math.sin(angle_offset)
            else:
                # Place randomly around house
                # Use polar coordinates for even distribution
                angle = random.uniform(0, 2 * math.pi)
                distance = random.uniform(actual_min_distance, max_distance)
                
                # Calculate position
                x = house_center.x + distance * math.cos(angle)
                y = house_center.y + distance * math.sin(angle)
            
            # Add some randomness to make placement more natural
            x += random.uniform(-1.0, 1.0)
            y += random.uniform(-1.0, 1.0)
            
            # Set temporary location
            obj.location = Vector((x, y, ground.location.z))
            
            # Get object bounding box at new location
            obj_bbox = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
            obj_min = Vector([min([v[i] for v in obj_bbox]) for i in range(3)])
            obj_max = Vector([max([v[i] for v in obj_bbox]) for i in range(3)])
            
            # Check if object is within acceptable distance range
            dist_to_house = (Vector((x, y, 0)) - house_center).length
            if dist_to_house < actual_min_distance or dist_to_house > max_distance:
                continue
            
            # Check for collisions with other objects
            collision_found = False
            for other_obj in placed_objects:
                if other_obj == obj:
                    continue
                
                # Get other object's bounding box
                other_bbox = [other_obj.matrix_world @ Vector(v) for v in other_obj.bound_box]
                other_min = Vector([min([v[i] for v in other_bbox]) for i in range(3)])
                other_max = Vector([max([v[i] for v in other_bbox]) for i in range(3)])
                
                # Check for overlap
                if not (obj_max.x < other_min.x or obj_min.x > other_max.x or
                        obj_max.y < other_min.y or obj_min.y > other_max.y):
                    collision_found = True
                    break
            
            # Also check collision with house
            if not collision_found:
                if not (obj_max.x < house_min.x or obj_min.x > house_max.x or
                        obj_max.y < house_min.y or obj_min.y > house_max.y):
                    collision_found = True
            
            if not collision_found:
                # Finalize position
                stick_object_to_ground(obj.name)
                
                # Add random rotation for variety
                obj.rotation_euler.z = random.uniform(0, 2 * math.pi)
                
                placed_objects.append(obj)
                placed = True
                print(f"Placed {obj.name} at distance {dist_to_house:.2f}m from house")
                break
        
        if not placed:
            print(f"Warning: Could not find valid placement for {obj.name} after {max_attempts_per_object} attempts")
    
    print(f"Successfully placed {len(placed_objects)}/{len(objects_to_place)} objects around house")
    return True


# Alternative function to place a single object around the house
def place_single_object_around_house(object_name, 
                                     min_distance=2.0, 
                                     max_distance=15.0,
                                     preferred_angle=None,
                                     angle_variance=math.pi/4,
                                     max_attempts=50):
    """
    Place a single object around the house at a specific angle or randomly.
    
    Args:
        object_name: Name of the object to place
        min_distance: Minimum distance from house center
        max_distance: Maximum distance from house center
        preferred_angle: Preferred angle in radians (0 = front, pi/2 = left, pi = back, 3*pi/2 = right)
        angle_variance: Random variance around preferred angle
        max_attempts: Maximum placement attempts
    """
    import math
    
    # Get references
    obj = bpy.data.objects.get(object_name)
    house = bpy.data.objects.get("house")
    ground = bpy.data.objects.get("ground")
    
    if not obj or not house or not ground:
        print(f"Error: Required objects not found (obj: {obj}, house: {house}, ground: {ground})")
        return False
    
    # Get house center and dimensions
    house_bbox = [house.matrix_world @ Vector(v) for v in house.bound_box]
    house_center = sum(house_bbox, Vector()) / len(house_bbox)
    house_center.z = 0
    
    house_min = Vector([min([v[i] for v in house_bbox]) for i in range(3)])
    house_max = Vector([max([v[i] for v in house_bbox]) for i in range(3)])
    house_width = house_max.x - house_min.x
    house_depth = house_max.y - house_min.y
    
    # Adjust min distance
    actual_min_distance = min_distance + max(house_width, house_depth) / 2
    
    for attempt in range(max_attempts):
        # Calculate angle
        if preferred_angle is not None:
            angle = preferred_angle + random.uniform(-angle_variance, angle_variance)
        else:
            angle = random.uniform(0, 2 * math.pi)
        
        # Calculate distance
        distance = random.uniform(actual_min_distance, max_distance)
        
        # Calculate position
        x = house_center.x + distance * math.cos(angle)
        y = house_center.y + distance * math.sin(angle)
        
        # Set location
        obj.location = Vector((x, y, ground.location.z))
        
        # Check for collisions
        obj_bbox = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
        obj_min = Vector([min([v[i] for v in obj_bbox]) for i in range(3)])
        obj_max = Vector([max([v[i] for v in obj_bbox]) for i in range(3)])
        
        # Check collision with house
        if not (obj_max.x < house_min.x or obj_min.x > house_max.x or
                obj_max.y < house_min.y or obj_min.y > house_max.y):
            continue
        
        # Check collision with other objects
        collision_found = False
        for other in bpy.context.scene.objects:
            if (other.type == 'MESH' and 
                other.name != object_name and 
                other.name not in ["ground", "house"]):
                
                other_bbox = [other.matrix_world @ Vector(v) for v in other.bound_box]
                other_min = Vector([min([v[i] for v in other_bbox]) for i in range(3)])
                other_max = Vector([max([v[i] for v in other_bbox]) for i in range(3)])
                
                if not (obj_max.x < other_min.x or obj_min.x > other_max.x or
                        obj_max.y < other_min.y or obj_min.y > other_max.y):
                    collision_found = True
                    break
        
        if not collision_found:
            # Finalize position
            stick_object_to_ground(object_name)
            
            # Add random rotation
            obj.rotation_euler.z = random.uniform(0, 2 * math.pi)
            
            print(f"Placed {object_name} at angle {math.degrees(angle):.1f}° and distance {distance:.2f}m")
            return True
    
    print(f"Failed to place {object_name} after {max_attempts} attempts")
    return False