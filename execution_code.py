import bpy
import math
import random
from mathutils import Vector
import sys
import os

# Add API path and import functions
sys.path.append(r'C:\Users\Jasper\Desktop\inpainting-dataset-generator')
from API.scene_construction_API import *

# Step 1: Clear the scene
clear_scene()

# Step 2: Add ground plane
add_ground(size=100)

# Step 3: Import the house
import_object("C:\\Users\\Jasper\\Desktop\\inpainting-dataset-generator\\Assets\\house\\house1.blend", "house")

# Step 4: Stick house to the ground
stick_object_to_ground("house")

# Step 5: Import first tree
import_object("C:\\Users\\Jasper\\Desktop\\inpainting-dataset-generator\\Assets\\tree\\tree3.blend", "tree_1")

# Step 6: Stick first tree to the ground
stick_object_to_ground("tree_1")

# Step 7: Scale first tree
scale_object("tree.000", 2.0)
# Step 8: Import second tree
import_object("C:\\Users\\Jasper\\Desktop\\inpainting-dataset-generator\\Assets\\tree\\tree2.blend", "tree_2")

# Step 9: Stick second tree to the ground
stick_object_to_ground("tree_2")

# Step 10: Scale second tree
scale_object("tree_2", 1.0)

# Step 11: Place all objects around the house
place_objects_around_house()

# Step 12: Capture scene views
# Set up camera and render settings if needed
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.samples = 128