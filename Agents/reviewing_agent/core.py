import os
import json
from anthropic import Anthropic
import socket

class ReviewingAgent:
    """
    ReviewingAgent using bounding box data instead of images to review object scales
    """

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("Missing ANTHROPIC_API_KEY environment variable")
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-3-haiku-20240307"
        
    def _get_scene_bbox_data(self) -> dict:
        """
        Get bounding box data from Blender via socket connection
        """
        # Code to get bounding box data from Blender
        code = """
import bpy
from mathutils import Vector

def get_object_bbox_data(obj_name):
    obj = bpy.data.objects.get(obj_name)
    if not obj:
        return None
    
    # Get bounding box corners in world space
    bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    
    # Calculate dimensions
    min_x = min(corner.x for corner in bbox_corners)
    max_x = max(corner.x for corner in bbox_corners)
    min_y = min(corner.y for corner in bbox_corners)
    max_y = max(corner.y for corner in bbox_corners)
    min_z = min(corner.z for corner in bbox_corners)
    max_z = max(corner.z for corner in bbox_corners)
    
    width = max_x - min_x
    depth = max_y - min_y
    height = max_z - min_z
    
    return {
        'name': obj_name,
        'width': width,
        'depth': depth,
        'height': height,
        'volume': width * depth * height,
        'location': list(obj.location),
        'scale': list(obj.scale)
    }

# Get data for all relevant objects
bbox_data = {}
for obj_name in ['house', 'tree_1', 'tree_2', 'tree_3', 'tree_4', 'tree_5']:
    data = get_object_bbox_data(obj_name)
    if data:
        bbox_data[obj_name] = data

_result = bbox_data
"""
        
        # Connect to Blender and execute
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.settimeout(10)
            client.connect(('localhost', 8089))
            client.send(code.encode('utf-8'))
            
            # Receive response
            response_parts = []
            while True:
                part = client.recv(4096)
                if not part:
                    break
                response_parts.append(part.decode('utf-8'))
                try:
                    json.loads(''.join(response_parts))
                    break
                except json.JSONDecodeError:
                    continue
            
            response = ''.join(response_parts)
            result = json.loads(response)
            
            if result.get('status') == 'success' and result.get('data'):
                return result['data']
            else:
                return {}
                
        except Exception as e:
            print(f"Error getting bbox data: {e}")
            return {}
        finally:
            if 'client' in locals():
                client.close()

    def review(self, step: int, description: str, edit_hint: str) -> dict:
        """
        Review the step using bounding box data instead of images
        """
        
        if "place_objects_around_house" in description.lower():
        # This step doesn't need review - it's just random placement
            return {"ok": True, "comment": "Random placement step - no review needed"}
    
        # Get bounding box data from the scene
        bbox_data = self._get_scene_bbox_data()
        
        if not bbox_data:
            return {"ok": False, "comment": "Failed to get scene data from Blender"}
        
        # Extract the object being reviewed from the description
        import re
        obj_match = re.search(r'[Ss]cale\s+(\w+)', description)
        if not obj_match:
            return {"ok": True, "comment": "Not a scaling step"}
        
        obj_name = obj_match.group(1)
        
        # Check if we have data for this object and the house
        if obj_name not in bbox_data:
            return {"ok": False, "comment": f"Object {obj_name} not found in scene"}
        
        if 'house' not in bbox_data:
            return {"ok": True, "comment": "No house in scene to compare against"}
        
        # Get dimensions
        house_data = bbox_data['house']
        obj_data = bbox_data[obj_name]
        
        # Build prompt for Claude - IMPROVED VERSION with better tolerance
        prompt = f"""You are reviewing the scale of objects in a 3D scene.

Object being reviewed: {obj_name}
Current scale: {obj_data['scale']}
Current dimensions: height={obj_data['height']:.2f}m

House dimensions: height={house_data['height']:.2f}m

Real-world reference:
- House height: typically 6-10 meters (single story: ~3m, two story: ~6-7m)
- Tree height: varies greatly, but for residential scenes:
  - Small ornamental trees: 3-6m
  - Medium trees: 6-12m  
  - Large trees: 12-20m
- Trees near houses are usually kept at 0.5x to 2.0x the house height for aesthetic balance

Current ratio: tree is {obj_data['height']/house_data['height']:.2f}x the house height.

IMPORTANT: Consider that:
1. A tree that's 50-200% of house height looks natural in most scenes
2. Trees can vary greatly in size - there's no single "correct" height
3. If the tree is within a reasonable range (0.5x to 2.0x house height), approve it
4. Only reject if the scale is clearly wrong (e.g., tree is 10cm tall or 50m tall)

Respond with JSON only:
{{"ok": true/false, "comment": "explanation"}}

If scaling is needed, calculate the EXACT scale factor needed from current size.
For example, if tree is currently 10m and should be 5m, recommend scale_object('tree_1', 0.5)"""

        try:
            response = self.client.messages.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.0,
            )
            
            text = response.content[0].text.strip()
            result = json.loads(text)
            
            # Ensure proper format
            if not isinstance(result, dict) or "ok" not in result:
                return {"ok": False, "comment": "Invalid response format"}
            
            result["ok"] = bool(result["ok"])
            if "comment" not in result:
                result["comment"] = "No comment provided"
            
            return result
            
        except Exception as e:
            return {"ok": False, "comment": f"Review failed: {str(e)}"}