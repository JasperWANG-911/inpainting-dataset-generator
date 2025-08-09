import os
import json
from anthropic import Anthropic
import base64

class ReviewingAgent:
    """
    ReviewingAgent, use Claude API to review Blender scene construction and give feedback.
    """

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("Missing ANTHROPIC_API_KEY environment variable")
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-3-haiku-20240307"   # change model name if needed

    def _load_reviewing_images_as_messages(self) -> list:
        """
        Load images from reviewing_images directory
        Images are named: top.png, front.png, back.png, left.png, right.png
        Convert them to Base64 and return as message format.
        """
        # Fix the path - remove extra "imnainting_dataset_generator" 
        base_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "reviewing_images")
        )
        
        # Create directory if it doesn't exist
        os.makedirs(base_dir, exist_ok=True)
        
        images = []
        missing_views = []
        
        for pos in ["top", "front", "back", "left", "right"]:
            img_path = os.path.join(base_dir, f"{pos}.png")
            if not os.path.isfile(img_path):
                missing_views.append(pos)
                continue
            with open(img_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            
            # Add image
            images.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": b64
                }
            })
            # Add label
            images.append({
                "type": "text",
                "text": f"[{pos} view]"
            })
        
        # If no images found, return error message
        if not images:
            print(f"WARNING: No review images found in {base_dir}")
            print(f"Missing views: {missing_views}")
            return [{
                "type": "text",
                "text": f"ERROR: No review images found. Missing views: {', '.join(missing_views)}. Path checked: {base_dir}"
            }]
        
        return images

    def _build_messages(self, step: int, description: str, edit_hint: str) -> list:
        """
        Create messages for Claude Messages API with images
        """
        image_messages = self._load_reviewing_images_as_messages()
        
        content = [
            {
                "type": "text",
                "text": f"""You are a reviewing agent in a multi-agent Blender scene pipeline.

    Step: {step}
    Task description: {description}

    Here are the five views of the current scene:"""
            }
        ]
        
        # Add images
        content.extend(image_messages)
        
        content.append({
            "type": "text",
            "text": f"""
    Please:
    1. Judge whether this step succeeded (output "ok": true) or failed ("ok": false).
    2. If this is a scaling step and the scale is incorrect, provide a specific scaling factor recommendation.
    For example: "The tree is too large compared to the house. Current scale appears to be 2x too big. Recommend scale_object('tree_1', 0.5)". 
    If the object appears 2x too large and was already scaled, recommend the absolute scale from original size. 
    For example: if tree was scaled 2x and is still too big by half, recommend scale_object('tree_1', 1.0) not 0.5
    3. If you cannot see the object, provide a comment like "The tree is not visible in the scene."
    4. Respond with a JSON object ONLY, for example:
    {{"ok": false, "comment": "The tree is 3x too large. Recommend scale_object('tree_1', 0.3)"}}

    Edit hint: {edit_hint}
    Important: Your response must be valid JSON with "ok" (boolean) and "comment" (string) fields."""
        })
        
        return [{"role": "user", "content": content}]
    
    def review(self, step: int, description: str, edit_hint: str) -> dict:
        """
        Call Claude API to review the step and return {"ok": bool, "comment": str}.
        """
        messages = self._build_messages(step, description, edit_hint)
        
        try:
            response = self.client.messages.create(
                model=self.model,
                messages=messages,
                max_tokens=300,
                temperature=0.0,
            )
            
            text = response.content[0].text.strip()
            
            # Parse JSON response
            result = json.loads(text)
            
            # Ensure the response has the required format
            if not isinstance(result, dict):
                raise ValueError("Response is not a dictionary")
            
            # Ensure 'ok' field exists and is boolean
            if "ok" not in result:
                raise ValueError("Missing 'ok' field in response")
            
            # Ensure 'comment' field exists
            if "comment" not in result:
                result["comment"] = "No comment provided"
            
            # Ensure 'ok' is boolean
            result["ok"] = bool(result["ok"])
            
            return result
            
        except json.JSONDecodeError as e:
            return {"ok": False, "comment": f"Failed to parse JSON response: {text}"}
        except ValueError as e:
            return {"ok": False, "comment": f"Invalid response format: {str(e)}"}
        except Exception as e:
            return {"ok": False, "comment": f"API call failed: {str(e)}"}