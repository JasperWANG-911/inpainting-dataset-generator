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
        self.model = "claude-opus-4-20250514"   # change model name if needed

    def _load_reviewing_images_as_messages(self) -> list:
        """
        Load images from reviewing_images directory
        Images are named: top.png, front.png, back.png, left.png, right.png
        Convert them to Base64 and return as message format.
        """
        # Fix the path - remove extra "impainting_dataset_generator" 
        base_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "impainting_dataset_generator", "reviewing_images")
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
    2. Provide a concise but actionable "comment" based on this step's edit hint. The edit hint is: {edit_hint}
    3. Respond with a JSON object ONLY, for example:
    {{"ok": true, "comment": "The object tree1 should be scale by a factor of 2"}}
    
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