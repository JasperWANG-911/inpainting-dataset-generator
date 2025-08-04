import os
import json
from pathlib import Path
from typing import Dict, List, Optional
from anthropic import Anthropic


class CodingAgent:
    """
    Coding Agent: Generate and manage Blender Python code for scene construction.
    Maintains execution_code.py with step-by-step code generation.
    """
    
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("Missing ANTHROPIC_API_KEY environment variable")
        
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-opus-4-20250514"   # change model name if needed
        
        # Path to execution_code.py in project root
        self.project_root = Path(__file__).parent.parent.parent
        self.execution_code_path = self.project_root / "execution_code.py" # Path to the execution code file
        
        # Track fixed steps
        self.fixed_steps = set()
        
        # Load API reference and workflow config
        self.api_reference = self._load_api_reference()
        self.workflow_config = self._load_workflow_config()
    
    def _load_api_reference(self) -> str:
        """Load scene construction API reference."""
        api_path = self.project_root / "API/scene_construction_API.py" # Path to the API reference file
        if api_path.exists():
            with open(api_path, 'r', encoding='utf-8') as f:
                return f.read()
        return ""
    
    def _load_workflow_config(self) -> dict:
        """Load workflow configuration."""
        config_path = self.project_root / "workflow_config.json" # Path to the workflow config file
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"steps": {}}
    
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
    
    def _parse_code_sections(self, code: str) -> Dict[int, str]:
        """Parse code into sections by step number."""
        sections = {}
        current_step = None
        current_lines = []
        
        for line in code.split('\n'):
            if line.strip().startswith('# Step ') and ':' in line:
                # Save previous section
                if current_step is not None:
                    sections[current_step] = '\n'.join(current_lines)
                
                # Start new section
                try:
                    current_step = int(line.split('Step ')[1].split(':')[0])
                    current_lines = [line]
                except:
                    current_lines.append(line)
            else:
                current_lines.append(line)
        
        # Save last section
        if current_step is not None:
            sections[current_step] = '\n'.join(current_lines)
        
        return sections
    
    def _generate_step_code(self, step: int, task_description: str, review_comment: Optional[str] = None) -> str:
        """Generate code for a specific step using Claude."""
        
        # Get step info from workflow config
        step_info = self.workflow_config.get("steps", {}).get(str(step), {})
        func_name = step_info.get("func", "")
        params = step_info.get("editable_params", {})
        hints = step_info.get("edit_hints", "")
        
        prompt = f"""Generate Blender Python code for Step {step} of scene construction.

Task: {task_description}
Function to use: {func_name}
Parameters: {json.dumps(params)}
Hints: {hints}


{f"Previous review comment: {review_comment}" if review_comment else ""}

Available API functions:
```python
{self.api_reference}

Requirements:

1. Use the specified function: {func_name}
2. Import the functions from scene_construction_API first
3. Apply the given parameters: {params}
4. Include error handling
5. Add brief comments explaining the logic
6. Start with comment: # Step {step}: {task_description}
7. Only write code for this specific step

Output only the Python code for this step, no explanations.

Alawys add the following code to the end:
........

"""
        
        response = self.client.messages.create(
        model=self.model,
        max_tokens=1000,
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}]
    )
    
        return response.content[0].text.strip()

    def generate_code(self, step: int, task_description: str, review_result: Optional[dict] = None) -> dict:
        """
        Generate or update code based on step and review results.
        
        Args:
            step: Current step number
            task_description: Description of what this step should do
            review_result: {"ok": bool, "comment": str} from reviewing agent
            
        Returns:
            {"success": bool, "message": str, "code_path": str}
        """
        try:
            current_code = self._read_current_code()
            sections = self._parse_code_sections(current_code)
            
            # Handle review results
            if review_result:
                if review_result.get("ok", False):
                    # Step passed - mark as fixed
                    self.fixed_steps.add(step)
                    return {
                        "success": True,
                        "message": f"Step {step} passed review and marked as fixed",
                        "code_path": str(self.execution_code_path)
                    }
                else:
                    # Step failed - need to regenerate this step only
                    if step in self.fixed_steps:
                        return {
                            "success": False,
                            "message": f"Step {step} is already fixed and cannot be modified",
                            "code_path": str(self.execution_code_path)
                        }
            
            # Generate new code for this step
            new_step_code = self._generate_step_code(
                step, 
                task_description, 
                review_result.get("comment") if review_result else None
            )
            
            # Update sections
            sections[step] = new_step_code
            
            # Rebuild complete code with proper imports
            complete_code = "import bpy\nimport math\nimport random\nfrom mathutils import Vector\n"
            complete_code += "import sys\nimport os\n\n"
            complete_code += "# Add API path and import functions\n"
            complete_code += f"sys.path.append(r'{self.project_root}')\n"
            complete_code += "from scene_construction_API import *\n\n"
            
            for step_num in sorted(sections.keys()):
                complete_code += sections[step_num] + "\n\n"
            
            # Write updated code
            self._write_code(complete_code)
            
            return {
                "success": True,
                "message": f"Generated code for step {step}",
                "code_path": str(self.execution_code_path),
                "fixed_steps": list(self.fixed_steps),
                "used_function": step_info.get("func", "")
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error generating code: {str(e)}",
                "code_path": str(self.execution_code_path)
            }