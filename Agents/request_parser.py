import json
import os
from anthropic import Anthropic

class RequestParserAgent:
    """Agent to parse scene descriptions into structured JSON format."""
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.system_prompt = """Extract objects, quantities, and environment from the scene description.

For quantities: 
1. if a number is mentioned, use it;
2. if a number is not menetioned, but a word like 'few', 'several', or 'many' is used, use a reasonable estimate (e.g., 'few' = 3);
3. if no quantity is mentioned, assume 1.

Output JSON format:
{
    "objects": [
        {"name": "house", "quantity": 1},
        {"name": "tree", "quantity": 4}
    ],
    "environment": {
        "lighting": "sunlight",
    }
}

Only include what's explicitly mentioned. Keep it simple."""

    def parse(self, text: str) -> dict:
        response = self.client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=500,
            system=self.system_prompt,
            messages=[{"role": "user", "content": text}]
        )
        
        # Extract JSON from response
        content = response.content[0].text
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0]
        else:
            json_str = content
            
        return json.loads(json_str.strip())

# Example usage
if __name__ == "__main__":
    parser = RequestParserAgent(os.getenv("ANTHROPIC_API_KEY"))
    description = "a house surrounded by a few trees in daylight"
    result = parser.parse(description)
    print(f"Output: {json.dumps(result, indent=2)}")