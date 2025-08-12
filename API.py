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
        min_distance: Minimum distance from house bounding box (meters)
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
    
    # Get house bounding box
    house_bbox = [house.matrix_world @ Vector(v) for v in house.bound_box]
    house_center = sum(house_bbox, Vector()) / len(house_bbox)
    house_center.z = 0  # Project to ground level
    
    # Calculate house bounding box min/max
    house_min = Vector([min([v[i] for v in house_bbox]) for i in range(3)])
    house_max = Vector([max([v[i] for v in house_bbox]) for i in range(3)])
    house_width = house_max.x - house_min.x
    house_depth = house_max.y - house_min.y
    
    # Calculate the actual minimum distance from house center
    # This accounts for the house size + desired margin
    house_half_diagonal = math.sqrt((house_width/2)**2 + (house_depth/2)**2)
    min_distance_from_center = house_half_diagonal + min_distance
    
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
                distance_offset = random.uniform(1.5, 3.0)  # Distance from target object
                
                x = target_obj.location.x + distance_offset * math.cos(angle_offset)
                y = target_obj.location.y + distance_offset * math.sin(angle_offset)
            else:
                # Place randomly around house
                angle = random.uniform(0, 2 * math.pi)
                # Distance from house center, ensuring minimum clearance
                distance = random.uniform(min_distance_from_center, max_distance)
                
                # Calculate position relative to house center
                x = house_center.x + distance * math.cos(angle)
                y = house_center.y + distance * math.sin(angle)
            
            # Add some randomness to make placement more natural
            x += random.uniform(-0.5, 0.5)
            y += random.uniform(-0.5, 0.5)
            
            # Set temporary location
            obj.location = Vector((x, y, ground.location.z))
            
            # Update object transform to get correct bounding box
            bpy.context.view_layer.update()
            
            # Get object bounding box at new location
            obj_bbox = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
            obj_min = Vector([min([v[i] for v in obj_bbox]) for i in range(3)])
            obj_max = Vector([max([v[i] for v in obj_bbox]) for i in range(3)])
            
            # Check if object is too far from house center
            dist_to_house_center = (Vector((x, y, 0)) - house_center).length
            if dist_to_house_center > max_distance:
                continue
            
            # Check collision with house (including min_distance margin)
            house_collision = False
            
            # Calculate minimum required separation
            separation_x = min_distance
            separation_y = min_distance
            
            # Check if object is too close to house
            if (obj_min.x < house_max.x + separation_x and 
                obj_max.x > house_min.x - separation_x and
                obj_min.y < house_max.y + separation_y and 
                obj_max.y > house_min.y - separation_y):
                house_collision = True
                continue
            
            # Check collision with other placed objects
            object_collision = False
            for other_obj in placed_objects:
                if other_obj == obj:
                    continue
                
                # Get other object's bounding box
                other_bbox = [other_obj.matrix_world @ Vector(v) for v in other_obj.bound_box]
                other_min = Vector([min([v[i] for v in other_bbox]) for i in range(3)])
                other_max = Vector([max([v[i] for v in other_bbox]) for i in range(3)])
                
                # Check for overlap (with small margin)
                margin = 0.5  # Small margin between objects
                if (obj_min.x < other_max.x + margin and 
                    obj_max.x > other_min.x - margin and
                    obj_min.y < other_max.y + margin and 
                    obj_max.y > other_min.y - margin):
                    object_collision = True
                    break
            
            if object_collision:
                continue
            
            # If we get here, placement is valid
            # Finalize position
            stick_object_to_ground(obj.name)
            
            # Add random rotation for variety
            obj.rotation_euler.z = random.uniform(0, 2 * math.pi)
            
            placed_objects.append(obj)
            placed = True
            
            # Calculate actual distance from object edge to house edge for logging
            dist_x = max(0, max(house_min.x - obj_max.x, obj_min.x - house_max.x))
            dist_y = max(0, max(house_min.y - obj_max.y, obj_min.y - house_max.y))
            edge_dist = math.sqrt(dist_x**2 + dist_y**2) if (dist_x > 0 or dist_y > 0) else 0
            
            print(f"Placed {obj.name} - edge distance from house: {edge_dist:.2f}m")
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

# Function to set HDRI environment lighting
def set_hdri_environment(hdri_path, strength=1.0, rotation_z=0.0):
    import os
    
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
    import os
    import csv
    from mathutils import Matrix
    
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

# Function to export the entire scene as a point cloud
def export_scene_pointcloud(output_path=None, samples_per_face=10, exclude_objects=["ground"]):
    import os
    import numpy as np
    from mathutils import Vector
    
    # Set default output path
    if output_path is None:
        if bpy.data.filepath:
            project_dir = os.path.dirname(bpy.data.filepath)
        else:
            project_dir = os.getcwd()
        
        output_dir = os.path.join(project_dir, "results", "pointcloud")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "scene.ply")
    
    # Collect all points and colors
    all_points = []
    all_colors = []
    
    # Process each mesh object in the scene
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH' or obj.name in exclude_objects:
            continue
        
        print(f"Processing {obj.name}...")
        
        # Get the evaluated mesh (with modifiers applied)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        obj_eval = obj.evaluated_get(depsgraph)
        mesh = obj_eval.to_mesh()
        
        # Get object color (from first material if exists)
        obj_color = [0.5, 0.5, 0.5]  # Default gray
        if obj.data.materials and obj.data.materials[0]:
            mat = obj.data.materials[0]
            if mat.use_nodes:
                # Try to get base color from Principled BSDF
                for node in mat.node_tree.nodes:
                    if node.type == 'BSDF_PRINCIPLED':
                        obj_color = node.inputs['Base Color'].default_value[:3]
                        break
        
        # Sample points from faces
        for face in mesh.polygons:
            # Calculate face area for weighted sampling
            face_verts = [mesh.vertices[i].co for i in face.vertices]
            
            # Sample points on the face
            for _ in range(samples_per_face):
                # Random barycentric coordinates
                r1, r2 = np.random.random(), np.random.random()
                if r1 + r2 > 1:
                    r1, r2 = 1 - r1, 1 - r2
                r3 = 1 - r1 - r2
                
                # Calculate point position
                if len(face_verts) == 3:  # Triangle
                    point = r1 * face_verts[0] + r2 * face_verts[1] + r3 * face_verts[2]
                elif len(face_verts) == 4:  # Quad - split into triangles
                    if r1 + r2 < 0.5:
                        # First triangle
                        point = (r1*2) * face_verts[0] + (r2*2) * face_verts[1] + (1-r1*2-r2*2) * face_verts[2]
                    else:
                        # Second triangle
                        r1, r2 = r1*2-1, r2*2
                        if r1 + r2 > 1:
                            r1, r2 = 1 - r1, 1 - r2
                        point = r1 * face_verts[2] + r2 * face_verts[3] + (1-r1-r2) * face_verts[0]
                else:
                    # For n-gons, just use center point
                    point = sum(face_verts, Vector()) / len(face_verts)
                
                # Transform to world space
                world_point = obj.matrix_world @ point
                all_points.append(world_point)
                all_colors.append(obj_color)
        
        # Clean up
        obj_eval.to_mesh_clear()
    
    # Convert to numpy arrays
    points = np.array([[p.x, p.y, p.z] for p in all_points], dtype=np.float32)
    colors = np.array(all_colors, dtype=np.float32)
    
    print(f"Total points: {len(points)}")
    
    # Write PLY file
    with open(output_path, 'w') as f:
        # PLY header
        f.write("ply\n")
        f.write("format ascii 1.0\n")
        f.write(f"element vertex {len(points)}\n")
        f.write("property float x\n")
        f.write("property float y\n")
        f.write("property float z\n")
        f.write("property float red\n")
        f.write("property float green\n")
        f.write("property float blue\n")
        f.write("end_header\n")
        
        # Write points
        for i in range(len(points)):
            f.write(f"{points[i][0]:.6f} {points[i][1]:.6f} {points[i][2]:.6f} ")
            f.write(f"{colors[i][0]:.3f} {colors[i][1]:.3f} {colors[i][2]:.3f}\n")
    
    print(f"Exported scene point cloud to: {output_path}")
    return output_path