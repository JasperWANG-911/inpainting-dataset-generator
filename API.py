import bpy
import os
import math
import random
import mathutils
import csv
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree


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

# Function to aid place_object_around_house()
def check_mesh_collision(obj1, obj2, margin=0.5):    
    # Get evaluated depsgraph
    depsgraph = bpy.context.evaluated_depsgraph_get()
    
    try:
        # Create BVH trees for both objects
        bvh1 = BVHTree.FromObject(obj1, depsgraph)
        bvh2 = BVHTree.FromObject(obj2, depsgraph)
        
        if not bvh1 or not bvh2:
            # Fallback to bounding box if BVH creation fails
            return check_bbox_collision(obj1, obj2, margin)
        
        # Check for overlap
        overlap_pairs = bvh1.overlap(bvh2)
        
        if overlap_pairs:
            return True
        
        # If no direct overlap but we want a margin, check distance
        if margin > 0:
            # Sample points on obj1's surface
            # This is a simplified check - for more accuracy, you'd sample more points
            bbox_corners = [obj1.matrix_world @ Vector(corner) for corner in obj1.bound_box]
            
            for corner in bbox_corners:
                location, normal, index, dist = bvh2.find_nearest(corner)
                if location and dist < margin:
                    return True
        
        return False
        
    except Exception as e:
        print(f"Mesh collision check failed: {e}, falling back to bbox")
        return check_bbox_collision(obj1, obj2, margin)

# Function to aid place_object_around_house()
def check_bbox_collision(obj1, obj2, margin=0.5):
    # Get bounding boxes in world space
    bbox1 = [obj1.matrix_world @ Vector(v) for v in obj1.bound_box]
    bbox2 = [obj2.matrix_world @ Vector(v) for v in obj2.bound_box]
    
    # Calculate min/max for each object
    min1 = Vector([min(v[i] for v in bbox1) for i in range(3)])
    max1 = Vector([max(v[i] for v in bbox1) for i in range(3)])
    min2 = Vector([min(v[i] for v in bbox2) for i in range(3)])
    max2 = Vector([max(v[i] for v in bbox2) for i in range(3)])
    
    # Check overlap with margin
    return not (min1.x > max2.x + margin or max1.x < min2.x - margin or
                min1.y > max2.y + margin or max1.y < min2.y - margin or
                min1.z > max2.z + margin or max1.z < min2.z - margin)

# Function to place objects randomly around the house without any collisions/overlap
def place_objects_around_house(excluded_objects=["ground", "house"], 
                               min_distance=2.0, 
                               max_distance=15.0, 
                               cluster_probability=0.3,
                               max_attempts_per_object=50):
    """
    Place objects randomly around the house using mesh-level collision detection.
    
    Args:
        excluded_objects: List of object names to exclude from repositioning
        min_distance: Minimum distance from house (meters)
        max_distance: Maximum distance from house center (meters)
        cluster_probability: Probability that an object will be placed near another object
        max_attempts_per_object: Maximum placement attempts per object
    """
    
    # Get house and ground references
    house = bpy.data.objects.get("house")
    ground = bpy.data.objects.get("ground")
    
    if not house or not ground:
        print("Error: House or ground not found in scene")
        return False
    
    # Get house center and safe placement radius
    house_bbox = [house.matrix_world @ Vector(v) for v in house.bound_box]
    house_center = sum(house_bbox, Vector()) / len(house_bbox)
    house_center.z = 0  # Project to ground level
    
    # Calculate a safe minimum radius based on house size
    # Use local space dimensions for accurate sizing
    local_dims = []
    for i in range(3):
        local_dims.append(max(v[i] for v in house.bound_box) - 
                         min(v[i] for v in house.bound_box))
    
    # Use actual dimensions to calculate safe radius
    house_radius = math.sqrt((local_dims[0]/2)**2 + (local_dims[1]/2)**2)
    min_placement_radius = house_radius + min_distance
    
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
    
    # Track placed objects for clustering and collision detection
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
                distance_offset = random.uniform(1.5, 3.0)
                
                x = target_obj.location.x + distance_offset * math.cos(angle_offset)
                y = target_obj.location.y + distance_offset * math.sin(angle_offset)
            else:
                # Place randomly around house
                angle = random.uniform(0, 2 * math.pi)
                # Distance from house center
                distance = random.uniform(min_placement_radius, max_distance)
                
                # Calculate position
                x = house_center.x + distance * math.cos(angle)
                y = house_center.y + distance * math.sin(angle)
            
            # Add some randomness
            x += random.uniform(-0.5, 0.5)
            y += random.uniform(-0.5, 0.5)
            
            # Set temporary location
            obj.location = Vector((x, y, ground.location.z))
            
            # Update object transform
            bpy.context.view_layer.update()
            
            # Check distance constraint
            dist_to_house_center = (Vector((x, y, 0)) - house_center).length
            if dist_to_house_center > max_distance:
                continue
            
            # Check mesh collision with house
            if check_mesh_collision(obj, house, min_distance):
                continue
            
            # Check collision with other placed objects
            collision_found = False
            for other_obj in placed_objects:
                if other_obj == obj:
                    continue
                
                if check_mesh_collision(obj, other_obj, 0.5):
                    collision_found = True
                    break
            
            if collision_found:
                continue
            
            # If we get here, placement is valid
            # Finalize position
            stick_object_to_ground(obj.name)
            
            # Add random rotation for variety
            obj.rotation_euler.z = random.uniform(0, 2 * math.pi)
            
            placed_objects.append(obj)
            placed = True
            
            # Calculate actual distance for logging (using BVH for accuracy)
            try:
                depsgraph = bpy.context.evaluated_depsgraph_get()
                obj_bvh = BVHTree.FromObject(obj, depsgraph)
                house_bvh = BVHTree.FromObject(house, depsgraph)
                
                # Sample some points on object surface to find minimum distance
                min_dist = float('inf')
                for corner in [obj.matrix_world @ Vector(v) for v in obj.bound_box]:
                    location, normal, index, dist = house_bvh.find_nearest(corner)
                    if location:
                        min_dist = min(min_dist, dist)
                
                print(f"Placed {obj.name} - minimum distance from house: {min_dist:.2f}m")
            except:
                print(f"Placed {obj.name}")
            
            break
        
        if not placed:
            print(f"Warning: Could not find valid placement for {obj.name} after {max_attempts_per_object} attempts")
    
    print(f"Successfully placed {len(placed_objects)}/{len(objects_to_place)} objects around house")
    return True

# Function to remove ground plane before rendering
def remove_ground():
    # First, apply all constraints to lock object positions
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH' and obj.name != 'ground':
            # Select the object
            bpy.context.view_layer.objects.active = obj
            
            # Apply all constraints to make positions permanent
            for constraint in obj.constraints:
                if constraint.type == 'SHRINKWRAP':
                    # Store the current location
                    current_loc = obj.location.copy()
                    
                    # Apply the constraint
                    try:
                        bpy.ops.constraint.apply(constraint=constraint.name)
                    except:
                        # If apply fails, just remove the constraint
                        obj.constraints.remove(constraint)
                    
                    # Ensure location is preserved
                    obj.location = current_loc
    
    # Now remove the ground
    ground = bpy.data.objects.get('ground')
    if ground:
        bpy.data.objects.remove(ground, do_unlink=True)
        print("Ground plane removed successfully")
    else:
        print("No ground plane found to remove")
    
    return True

# ========================APIs for Rendering================================
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

# Function to set HDRI environment lighting
def set_hdri_environment(hdri_path, strength=1.0, rotation_z=0.0):
    # Check if file exists
    if not os.path.exists(hdri_path):
        print(f"Error: HDRI file not found: {hdri_path}")
        return False
    
    # Get the world
    world = bpy.context.scene.world
    
    # Enable use of nodes
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    
    # Clear existing nodes
    nodes.clear()
    
    # Add required nodes
    # 1. Texture Coordinate node
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    tex_coord.location = (-800, 300)
    
    # 2. Mapping node for rotation control
    mapping = nodes.new(type='ShaderNodeMapping')
    mapping.location = (-600, 300)
    mapping.inputs['Rotation'].default_value[2] = rotation_z  # Z rotation
    
    # 3. Environment Texture node
    env_texture = nodes.new(type='ShaderNodeTexEnvironment')
    env_texture.location = (-400, 300)
    env_texture.image = bpy.data.images.load(hdri_path)
    env_texture.interpolation = 'Linear'  # Better quality
    
    # 4. Background shader
    background = nodes.new(type='ShaderNodeBackground')
    background.location = (-100, 300)
    background.inputs['Strength'].default_value = strength
    
    # 5. World Output
    output = nodes.new(type='ShaderNodeOutputWorld')
    output.location = (100, 300)
    
    # Connect nodes
    links.new(tex_coord.outputs['Generated'], mapping.inputs['Vector'])
    links.new(mapping.outputs['Vector'], env_texture.inputs['Vector'])
    links.new(env_texture.outputs['Color'], background.inputs['Color'])
    links.new(background.outputs['Background'], output.inputs['Surface'])
    
    # Set viewport shading to use scene world
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.use_scene_world = True
                    space.shading.use_scene_lights = True
    
    print(f"HDRI environment set: {hdri_path}")
    return True

# =======================APIs for ground truth extraction=================================
# Function to export camera intrinsics and extrinsics
def export_camera_parameters(output_path=None):
    
    # Default output path
    if output_path is None:
        if bpy.data.filepath:
            project_dir = os.path.dirname(bpy.data.filepath)
        else:
            project_dir = os.getcwd()
        output_path = os.path.join(project_dir, "results", "intrinsics_and_extrinsics.csv")
    
    # Create directory if needed
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Get all hemisphere cameras
    cameras = [obj for obj in bpy.data.objects if obj.type == 'CAMERA' and 'Camera_Hemisphere' in obj.name]
    
    if not cameras:
        print("No hemisphere cameras found!")
        return
    
    # Prepare CSV data
    csv_data = []
    
    # Get render resolution
    render = bpy.context.scene.render
    width = render.resolution_x
    height = render.resolution_y
    
    for camera in cameras:
        cam_data = camera.data
        
        # Calculate intrinsic parameters
        # Focal length in pixels
        if cam_data.sensor_fit == 'HORIZONTAL':
            sensor_size = cam_data.sensor_width
            fx = (width * cam_data.lens) / sensor_size
            fy = fx  # Assuming square pixels
        else:
            sensor_size = cam_data.sensor_height
            fy = (height * cam_data.lens) / sensor_size
            fx = fy
        
        # Principal point (image center)
        cx = width / 2.0
        cy = height / 2.0
        
        # Get camera transformation matrix
        cam_matrix = camera.matrix_world
        
        

        # Convert to OpenCV coordinate system
        flip = Matrix([
            [1, 0, 0],
            [0, -1, 0],
            [0, 0, -1]
        ])

        # get rotation matrix
        R_blender = cam_matrix.to_3x3()
        R_opencv = flip @ R_blender

        # get translation vector
        t_blender = cam_matrix.translation
        t_opencv = flip @ t_blender
        
        # Flatten rotation matrix for CSV (row-major order)
        r11, r12, r13 = R_opencv[0]
        r21, r22, r23 = R_opencv[1]
        r31, r32, r33 = R_opencv[2]
        tx, ty, tz = t_opencv
        
        # Add row to CSV data
        csv_data.append({
            'camera_name': camera.name,
            'fx': fx,
            'fy': fy,
            'cx': cx,
            'cy': cy,
            'k1': 0.0,  # No distortion in Blender
            'k2': 0.0,
            'k3': 0.0,
            'p1': 0.0,
            'p2': 0.0,
            'r11': r11,
            'r12': r12,
            'r13': r13,
            'r21': r21,
            'r22': r22,
            'r23': r23,
            'r31': r31,
            'r32': r32,
            'r33': r33,
            'tx': tx,
            'ty': ty,
            'tz': tz,
            'width': width,
            'height': height
        })
    
    # Write CSV file
    with open(output_path, 'w', newline='') as csvfile:
        fieldnames = ['camera_name', 'fx', 'fy', 'cx', 'cy', 'k1', 'k2', 'k3', 'p1', 'p2',
                     'r11', 'r12', 'r13', 'r21', 'r22', 'r23', 'r31', 'r32', 'r33',
                     'tx', 'ty', 'tz', 'width', 'height']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_data)
    
    print(f"Camera parameters exported to: {output_path}")
    return output_path

# Function to export scene as OBJ file
def export_obj(filepath=None):
    if filepath is None:
        if bpy.data.filepath:
            project_dir = os.path.dirname(bpy.data.filepath)
        else:
            project_dir = os.getcwd()
        output_dir = os.path.join(project_dir, "results", "models")
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, "scene.obj")
    
    bpy.ops.export_scene.obj(
        filepath=filepath,
        use_selection=False,
        use_animation=False,
        use_mesh_modifiers=True,
        use_edges=True,
        use_smooth_groups=False,
        use_smooth_groups_bitflags=False,
        use_normals=True,
        use_uvs=True,
        use_materials=True,
        use_triangles=False,
        use_nurbs=False,
        use_vertex_groups=False,
        use_blen_objects=True,
        group_by_object=False,
        group_by_material=False,
        keep_vertex_order=False,
        global_scale=1.0,
        axis_forward='-Z',
        axis_up='Y'
    )
    
    print(f"Scene exported to OBJ: {filepath}")
    return filepath
