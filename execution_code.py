import bpy
import math
import random
from mathutils import Vector
import sys
import os

# Add API path and import functions
sys.path.append(r'C:\Users\Jasper\Desktop\inpainting-dataset-generator')
from API.scene_construction_API import *

import bpy
import os
import math
import random
import mathutils
from mathutils import Vector

# Step 1: Clear the scene
clear_scene()

# Step 2: Add ground plane with size 100
add_ground(size=100)

# Step 3: Import the house
house_path = "C:\\Users\\Jasper\\Desktop\\inpainting-dataset-generator\\Assets\\house\\house1.blend"
import_object(house_path, "house")

# Step 4: Stick the house to the ground
stick_object_to_ground("house")

# Step 5: Import tree_1
tree1_path = "C:\\Users\\Jasper\\Desktop\\inpainting-dataset-generator\\Assets\\tree\\tree1.blend"
import_object(tree1_path, "tree_1")

# Step 6: Place tree_1 avoiding collision
place_object_avoiding_collision("tree_1")

# Step 7: Scale tree_1
# Scale tree_1 to be proportional to the house (typical tree height is 0.5-1.5x house height)
# Using scale factor 2.5 to make the tree appropriately sized relative to the house
scale_object("tree_1", 2.5)
# Step 8: Import tree_2
tree2_path = "C:\\Users\\Jasper\\Desktop\\inpainting-dataset-generator\\Assets\\tree\\tree3.blend"
import_object(tree2_path, "tree_2")

# Step 9: Place tree_2 avoiding collision
place_object_avoiding_collision("tree_2")

# Step 10: Scale tree_2
# Starting with scale factor 1.0
scale_object("tree_2", 1.0)

# Step 11: Capture scene views
# Set up camera and render settings for scene capture