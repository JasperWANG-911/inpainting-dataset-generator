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
        Load images from impainting_dataset_generator/reviewing_images
        Images are named: top.png, front.png, back.png, left.png, right.png
        Convert them to Base64 and return as message format.
        """
        base_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "impainting_dataset_generator", "reviewing_images")
        )
        images = []
        for pos in ["top", "front", "back", "left", "right"]:
            img_path = os.path.join(base_dir, f"{pos}.png")
            if not os.path.isfile(img_path):
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
            "text": """

Please:
1. Judge whether this step succeeded (output "ok": true) or failed ("ok": false).
2. Provide a concise but actionable "comment" based on this step's edit hint. The edit hint is {edit_hint}
3. Respond with a JSON object ONLY, for example:
   {
     "ok": true,
     "comment": "The object tree1 should be scale by a factor of 2"
   }"""
        })
        
        return [{"role": "user", "content": content}]

    def review(self, step: int, description: str) -> dict:
        """
        Call Claude API to review the step and return {"ok": bool, "comment": str}.
        """
        messages = self._build_messages(step, description)
        
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
            if not isinstance(result, dict) or "ok" not in result:
                raise ValueError("Invalid format")
            return result
            
        except json.JSONDecodeError as e:
            return {"ok": False, "comment": f"Failed to parse JSON response: {text}"}
        except Exception as e:
            return {"ok": False, "comment": f"API call failed: {str(e)}"}