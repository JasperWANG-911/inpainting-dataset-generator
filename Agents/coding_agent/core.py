import os
import json
from pathlib import Path
from typing import Dict, List, Optional
from anthropic import Anthropic


class CodingAgent:
    """
    Coding Agent: Generate and manage Blender Python code for scene construction.
    Can intelligently generate all necessary steps based on combination data,
    including smart scaling based on object proportions.
    """
    
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("Missing ANTHROPIC_API_KEY environment variable")
        
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-opus-4-20250514"
        
        # Path to execution_code.py in project root
        self.project_root = Path(__file__).parent.parent.parent
        self.execution_code_path = self.project_root / "execution_code.py"
        
        # Track fixed steps
        self.fixed_steps = set()
        
        # Store combination data
        self.current_combination = None
        
        # Load API reference
        self.api_reference = self._load_api_reference()
        
        # Store generated code and step info
        self.generated_code = ""
        self.step_descriptions = {}
    
    def _load_api_reference(self) -> str:
        """Load scene construction API reference."""
        api_path = self.project_root / "API/scene_construction_API.py"
        if api_path.exists():
            with open(api_path, 'r', encoding='utf-8') as f:
                return f.read()
        return ""
    
    def set_combination_data(self, combination: Dict):
        """Set the current combination data for intelligent code generation"""
        self.current_combination = combination
        self.fixed_steps.clear()  # Reset fixed steps for new combination
        self.step_descriptions.clear()
    
    def _generate_complete_scene_code(self) -> str:
        """Generate complete scene construction code based on combination data"""
        if not self.current_combination:
            raise RuntimeError("No combination data set")
        
        # Fix file paths to be absolute
        fixed_combination = self.current_combination.copy()
        fixed_combination["objects"] = []
        
        for obj in self.current_combination["objects"]:
            fixed_obj = obj.copy()
            # Convert relative path to absolute path
            if not os.path.isabs(obj["file_path"]):
                fixed_obj["file_path"] = str(self.project_root / obj["file_path"])
            # Ensure backslashes are properly escaped for Windows
            fixed_obj["file_path"] = fixed_obj["file_path"].replace("\\", "\\\\")
            fixed_combination["objects"].append(fixed_obj)
        
        # Build prompt for Claude with emphasis on intelligent scaling
        prompt = f"""Generate complete Blender Python code to construct a scene with the following objects:

{json.dumps(fixed_combination, indent=2)}

Available API functions:
{self.api_reference}

Requirements:
1. Start by clearing the scene and adding a ground plane (size 100)
2. Import the house first (if present) and stick it to the ground
3. For each other object:
   - Import it
   - INTELLIGENTLY SCALE it based on common sense proportions relative to the house
   - Place it using place_object_avoiding_collision
4. Use object instance_ids as names in Blender
5. End by capturing scene views

IMPORTANT SCALING GUIDELINES:
- Analyze the house's approximate size (typical house is 10-15 meters)
- Scale trees to be realistic relative to the house (typically 0.5x to 1.5x house height)
- Scale cars to be realistic (typically 1/3 to 1/2 house length)
- Scale smaller objects appropriately (trash cans ~1m, benches ~1.5m, etc.)
- Add a dedicated scaling step after importing each object type
- Use the scale_object() function from the API

Include clear step comments like:
# Step 1: Clear scene
# Step 2: Add ground
# Step 3: Import house
# Step 4: Stick house to ground
# Step 5: Import tree_1
# Step 6: Scale tree_1 appropriately
# Step 7: Place tree_1
etc.

Output only the Python code without markdown formatting."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=3000,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )
        
        generated_code = response.content[0].text.strip()
        
        # Clean any markdown formatting
        import re
        if generated_code.startswith('```') and generated_code.endswith('```'):
            generated_code = re.sub(r'^```(?:python)?\n?', '', generated_code)
            generated_code = re.sub(r'\n?```$', '', generated_code)
        
        # Parse step descriptions from the generated code
        self._parse_step_descriptions(generated_code)
        
        return generated_code
    
    def _parse_step_descriptions(self, code: str):
        """Parse step descriptions from the code"""
        lines = code.split('\n')
        for line in lines:
            if line.strip().startswith('# Step ') and ':' in line:
                try:
                    parts = line.split(':', 1)
                    step_num = int(parts[0].split('Step ')[1])
                    description = parts[1].strip()
                    self.step_descriptions[step_num] = description
                except:
                    pass
    
    def get_step_info(self, step: int) -> dict:
        """Get information about a specific step"""
        return {
            "step": step,
            "description": self.step_descriptions.get(step, f"Step {step}"),
            "is_scale_step": "scale" in self.step_descriptions.get(step, "").lower()
        }
    
    def _extract_step_from_code(self, code: str, step_num: int) -> Optional[str]:
        """Extract a specific step from the complete code"""
        lines = code.split('\n')
        step_start = None
        step_lines = []
        
        for i, line in enumerate(lines):
            if f'# Step {step_num}:' in line:
                step_start = i
                step_lines = [line]
            elif step_start is not None:
                if line.strip().startswith('# Step ') and ':' in line:
                    # Found next step
                    break
                else:
                    step_lines.append(line)
        
        if step_lines:
            return '\n'.join(step_lines)
        return None
    
    def generate_code(self, step: int, task_description: str, review_result: Optional[dict] = None) -> dict:
        """
        Generate or update code based on step and review results.
        If step is 1, generate complete code. Otherwise, extract/update specific step.
        """
        try:
            # Check if we have combination data
            if not self.current_combination:
                return {
                    "success": False,
                    "message": "No combination data set. Please set combination data first.",
                    "code_path": str(self.execution_code_path)
                }
            
            # Handle review results
            if review_result:
                if review_result.get("ok", False):
                    self.fixed_steps.add(step)
                    return {
                        "success": True,
                        "message": f"Step {step} passed review and marked as fixed",
                        "code_path": str(self.execution_code_path)
                    }
            
            # For step 1, generate complete code
            if step == 1:
                complete_code = self._generate_complete_scene_code()
                self.generated_code = complete_code
                
                # Add imports
                final_code = "import bpy\nimport math\nimport random\nfrom mathutils import Vector\n"
                final_code += "import sys\nimport os\n\n"
                final_code += "# Add API path and import functions\n"
                final_code += f"sys.path.append(r'{self.project_root}')\n"
                final_code += "from API.scene_construction_API import *\n\n"
                final_code += complete_code
                
                self._write_code(final_code)
                
                # Count total steps in generated code
                total_steps = len(self.step_descriptions)
                
                return {
                    "success": True,
                    "message": f"Generated complete scene code with {total_steps} steps",
                    "code_path": str(self.execution_code_path),
                    "total_steps": total_steps
                }
            
            # For other steps, extract from existing code or regenerate if needed
            current_code = self._read_current_code()
            
            if review_result and not review_result.get("ok", False):
                # Need to fix this step based on review comment
                step_code = self._fix_step_code(step, task_description, review_result["comment"])
                
                # Replace the step in the code
                updated_code = self._replace_step_in_code(current_code, step, step_code)
                self._write_code(updated_code)
                
                return {
                    "success": True,
                    "message": f"Fixed step {step} based on review feedback",
                    "code_path": str(self.execution_code_path)
                }
            
            # Extract and execute the specific step
            step_code = self._extract_step_from_code(current_code, step)
            if step_code:
                return {
                    "success": True,
                    "message": f"Ready to execute step {step}",
                    "code_path": str(self.execution_code_path)
                }
            else:
                return {
                    "success": False,
                    "message": f"Step {step} not found in generated code",
                    "code_path": str(self.execution_code_path)
                }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error generating code: {str(e)}",
                "code_path": str(self.execution_code_path)
            }
    
    def _fix_step_code(self, step: int, task_description: str, review_comment: str) -> str:
        """Generate fixed code for a specific step based on review feedback"""
        current_code = self._read_current_code()
        current_step_code = self._extract_step_from_code(current_code, step)
        
        # Check if this is a scaling step
        is_scale_step = "scale" in task_description.lower()
        
        prompt = f"""Fix the following Blender Python code based on the review feedback:

Current code:
{current_step_code}

Task description: {task_description}
Review comment: {review_comment}

Available API functions:
{self.api_reference}

{"IMPORTANT: This is a scaling step. Adjust the scale factor based on the review comment to make the object proportional to the house." if is_scale_step else ""}

Generate only the fixed code for this step, maintaining the same comment format.
Output only the Python code without markdown formatting."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )
        
        fixed_code = response.content[0].text.strip()
        
        # Clean markdown if present
        import re
        if fixed_code.startswith('```') and fixed_code.endswith('```'):
            fixed_code = re.sub(r'^```(?:python)?\n?', '', fixed_code)
            fixed_code = re.sub(r'\n?```$', '', fixed_code)
        
        return fixed_code
    
    def _replace_step_in_code(self, full_code: str, step_num: int, new_step_code: str) -> str:
        """Replace a specific step in the full code"""
        lines = full_code.split('\n')
        new_lines = []
        skip_mode = False
        step_found = False
        
        for line in lines:
            if f'# Step {step_num}:' in line:
                skip_mode = True
                step_found = True
                # Add the new step code
                new_lines.extend(new_step_code.split('\n'))
            elif skip_mode and line.strip().startswith('# Step ') and ':' in line:
                # Found next step, stop skipping
                skip_mode = False
                new_lines.append(line)
            elif not skip_mode:
                new_lines.append(line)
        
        return '\n'.join(new_lines)
    
    def _read_current_code(self) -> str:
        """Read current execution_code.py content."""
        if self.execution_code_path.exists():
            with open(self.execution_code_path, 'r', encoding='utf-8') as f:
                return f.read()
        return ""
    
    def _write_code(self, code: str):
        """Write code to execution_code.py."""
        with open(self.execution_code_path, 'w', encoding='utf-8') as f:
            f.write(code)