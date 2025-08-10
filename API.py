import bpy
import os
import math
import random
import mathutils
from mathutils import Vector

# ==========================APIs for Scene Construction==========================
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
def place_objects_around_house(excluded_objects=["ground", "house"], 
                               min_distance=2.0, 
                               max_distance=15.0, 
                               cluster_probability=0.3,
                               max_attempts_per_object=50):
    """
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

# ========================APIs for Rendering and Camera==========================
# Function to create a hemisphere of cameras around all objects 
def create_hemisphere_cameras(num_cameras=50, camera_height_ratio=1.2):
    """ 
    Args:
        num_cameras: Number of cameras to create (default 50)
        camera_height_ratio: Multiplier for hemisphere radius (default 1.2)
    """
    import math
    import numpy as np
    
    # Get all mesh objects except ground
    objects = []
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH' and obj.name != 'ground':
            objects.append(obj)
    
    if not objects:
        print("No objects found to create hemisphere around")
        return []
    
    # Calculate bounding box of all objects
    min_x = min_y = min_z = float('inf')
    max_x = max_y = max_z = float('-inf')
    
    for obj in objects:
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ Vector(corner)
            min_x = min(min_x, world_corner.x)
            max_x = max(max_x, world_corner.x)
            min_y = min(min_y, world_corner.y)
            max_y = max(max_y, world_corner.y)
            min_z = min(min_z, world_corner.z)
            max_z = max(max_z, world_corner.z)
    
    # Calculate center and radius of minimum enclosing circle (on XY plane)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    
    # Force hemisphere center to be at ground level (z=0)
    center_z = 0
    
    # Calculate radius as distance from center to furthest corner
    # Include both horizontal distance and vertical height
    radius = 0
    max_height = max_z  # Maximum height of objects
    
    for obj in objects:
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ Vector(corner)
            # Horizontal distance from center
            horizontal_dist = math.sqrt((world_corner.x - center_x)**2 + (world_corner.y - center_y)**2)
            # For hemisphere, we need to ensure cameras can see tall objects
            # So we consider both horizontal distance and height
            effective_radius = math.sqrt(horizontal_dist**2 + world_corner.z**2)
            radius = max(radius, horizontal_dist, effective_radius)
    
    # Add some margin to the radius
    hemisphere_radius = radius * camera_height_ratio
    
    # Create collection for cameras
    camera_collection = bpy.data.collections.new("Hemisphere_Cameras")
    bpy.context.scene.collection.children.link(camera_collection)
    
    # Generate camera positions on hemisphere
    cameras = []
    
    # Use golden ratio for better distribution
    golden_ratio = (1 + math.sqrt(5)) / 2
    
    for i in range(num_cameras):
        # Generate points on hemisphere using fibonacci sphere
        theta = 2 * math.pi * i / golden_ratio  # Azimuth angle
        phi = math.acos(1 - i / num_cameras)  # Polar angle (0 to pi/2 for hemisphere)
        
        # Convert spherical to cartesian coordinates
        # Center at (center_x, center_y, 0) instead of origin
        x = center_x + hemisphere_radius * math.sin(phi) * math.cos(theta)
        y = center_y + hemisphere_radius * math.sin(phi) * math.sin(theta)
        z = hemisphere_radius * math.cos(phi)  # z starts from 0 (ground level)
        
        # Create camera
        bpy.ops.object.camera_add(location=(x, y, z))
        camera = bpy.context.active_object
        camera.name = f"Camera_Hemisphere_{i:03d}"
        
        # Point camera to scene center at ground level
        look_at_point = Vector((center_x, center_y, max_height/2))  # Look at middle height of scene
        direction = look_at_point - camera.location
        rot_quat = direction.to_track_quat('-Z', 'Y')
        camera.rotation_euler = rot_quat.to_euler()
        
        # Move camera to the hemisphere collection
        # First ensure it's linked to scene collection
        if camera.name not in bpy.context.scene.collection.objects:
            bpy.context.scene.collection.objects.link(camera)
        
        # Now unlink from scene collection and link to camera collection
        bpy.context.scene.collection.objects.unlink(camera)
        camera_collection.objects.link(camera)
        
        # Set camera properties
        camera.data.lens = 35  # Standard lens
        camera.data.clip_end = hemisphere_radius * 3  # Ensure we can see everything
        
        cameras.append(camera)
    
    # Create empty at scene center for visualization
    bpy.ops.object.empty_add(type='SPHERE', location=(center_x, center_y, 0))
    empty = bpy.context.active_object
    empty.name = "Hemisphere_Center"
    empty.empty_display_size = 0.5
    
    return cameras

# Function to render the scene and export images(default path is "results/images")
def render_all_hemisphere_cameras(output_path=None, file_format="PNG"):
    import os
    
    # If no path specified, use default path relative to the blend file or current directory
    if output_path is None:
        # Try to get the directory of the current blend file
        if bpy.data.filepath:
            project_dir = os.path.dirname(bpy.data.filepath)
        else:
            # If no blend file saved, use current working directory
            project_dir = os.getcwd()
        
        # Create results/images directory
        output_path = os.path.join(project_dir, "results", "images")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_path, exist_ok=True)
    
    # Get all hemisphere cameras
    cameras = [obj for obj in bpy.data.objects if obj.type == 'CAMERA' and 'Camera_Hemisphere' in obj.name]
    
    if not cameras:
        print("No hemisphere cameras found!")
        return
    
    # Store original camera
    original_camera = bpy.context.scene.camera
    
    # Set render settings
    bpy.context.scene.render.image_settings.file_format = file_format
    
    # Render from each camera
    for i, camera in enumerate(cameras):
        print(f"Rendering from {camera.name} ({i+1}/{len(cameras)})")
        
        # Set active camera
        bpy.context.scene.camera = camera
        
        # Set output path
        output_file = os.path.join(output_path, f"{camera.name}.{file_format.lower()}")
        bpy.context.scene.render.filepath = output_file
        
        # Render
        bpy.ops.render.render(write_still=True)
    
    # Restore original camera
    bpy.context.scene.camera = original_camera
    
    print(f"Completed rendering {len(cameras)} views to {output_path}")