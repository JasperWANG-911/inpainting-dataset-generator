import httpx
import json
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Set
import logging
import os

class Orchestrator:
    """Main orchestrator that coordinates all agents"""
    
    def __init__(self, enable_review: bool = True, review_only_steps: Optional[Set[str]] = None):
        self.agents = {
            "execution": "http://localhost:8001",
            "reviewing": "http://localhost:8002", 
            "scene_planning": "http://localhost:8003",
            "coding": "http://localhost:8004"
        }
        self.project_root = Path(__file__).parent
        self.logger = self._setup_logger()
        self.timeout = httpx.Timeout(60, connect=10.0)
        self.current_combination = None
        self.total_steps = 0
        # REMOVED: self.reviewing_images_dir - no longer needed
        
        # Review control
        self.enable_review = enable_review
        # Steps that always need review (even in testing)
        self.review_only_steps = review_only_steps or {"scale"}
        
        # Steps that never need review
        self.skip_review_steps = {"clear_scene", "add_ground", "capture_scene_views", "place_objects_around_house"}
        
    def _setup_logger(self):
        logger = logging.getLogger('Orchestrator')
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger
    
    async def check_agents_health(self):
        """Check if all agents are running"""
        for name, url in self.agents.items():
            # Skip review agent if disabled
            if name == "reviewing" and not self.enable_review:
                self.logger.info(f"✓ {name} agent skipped (review disabled)")
                continue
                
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(f"{url}/health")
                    if response.status_code == 200:
                        self.logger.info(f"✓ {name} agent is healthy")
                    else:
                        self.logger.error(f"✗ {name} agent is unhealthy")
                        return False
            except Exception as e:
                self.logger.error(f"✗ {name} agent is not reachable: {e}")
                return False
        return True
    
    async def plan_scene(self, description: str, assets_csv_path: str, num_combinations: int = 1):
        """Step 1: Use scene planning agent to parse description and generate combinations"""
        self.logger.info("Planning scene...")
        
        # Convert to absolute path
        abs_path = str(Path(assets_csv_path).absolute())
        self.logger.info(f"Using assets CSV at: {abs_path}")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.agents['scene_planning']}/plan-scene",
                json={
                    "description": description,
                    "assets_csv_path": abs_path,
                    "num_combinations": num_combinations
                }
            )
            
        result = response.json()
        if not result["success"]:
            self.logger.error(f"Scene planning failed: {result.get('error', 'Unknown error')}")
            if "missing_assets" in result:
                self.logger.error(f"Missing assets: {result['missing_assets']}")
            return None
            
        self.logger.info(f"Scene planning successful. Generated {result['total_combinations']} combinations")
        return result
    
    async def set_combination_in_coding_agent(self, combination: Dict):
        """Send combination data to coding agent"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.agents['coding']}/set-combination",
                json={"combination": combination}
            )
        
        result = response.json()
        if not result["success"]:
            raise RuntimeError(f"Failed to set combination data: {result.get('message')}")
        
        self.logger.info("Combination data sent to coding agent")
    
    def _should_review_step(self, step_num: int, step_description: str) -> bool:
        """Determine if a step should be reviewed"""
        # If review is globally disabled
        if not self.enable_review:
            # But check if this is a critical step that always needs review
            for critical_step in self.review_only_steps:
                if critical_step.lower() in step_description.lower():
                    self.logger.info(f"Step {step_num} requires review (critical step: {critical_step})")
                    return True
            return False
        
        # If review is enabled, check if this step should be skipped
        for skip_step in self.skip_review_steps:
            if skip_step.lower() in step_description.lower():
                self.logger.info(f"Step {step_num} skipped review (type: {skip_step})")
                return False
        
        return True
        
    async def get_step_info(self, step_num: int) -> Dict:
        """Get information about a specific step from the generated code"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.agents['coding']}/get-step-info",
                json={"step": step_num}
            )
        
        return response.json()
    
    async def execute_workflow_steps(self, combination: Dict):
        """Execute all workflow steps with review loop"""
        # First, send combination data to coding agent
        await self.set_combination_in_coding_agent(combination)
        
        # Generate complete code on step 1
        self.logger.info("Generating complete scene construction code...")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.agents['coding']}/generate-code",
                json={
                    "step": 1,
                    "task_description": "Generate complete scene construction code with intelligent scaling",
                    "review_result": None
                }
            )
        
        code_result = response.json()
        if not code_result["success"]:
            self.logger.error(f"Code generation failed: {code_result['message']}")
            return False
        
        self.total_steps = code_result.get("total_steps", 0)
        self.logger.info(f"Generated code with {self.total_steps} steps")
        
        # Execute each step
        for step_num in range(1, self.total_steps + 1):
            self.logger.info(f"\n--- Executing Step {step_num}/{self.total_steps} ---")
            
            # Get step information
            step_info = await self.get_step_info(step_num)
            step_description = step_info.get("description", f"Step {step_num}")
            
            max_retries = 5
            retry_count = 0
            review_result = None
            
            while retry_count < max_retries:
                # Get the code for this specific step
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.agents['coding']}/get-step-code",
                        json={"step": step_num}
                    )
                
                step_code_result = response.json()
                if not step_code_result["success"]:
                    self.logger.error(f"Failed to get code for step {step_num}")
                    return False
                
                step_code = step_code_result["code"]
                
                # For steps after 1 with failed review, fix the code
                if review_result and not review_result.get("ok", False):
                    self.logger.info(f"Fixing step {step_num} based on review feedback...")
                    
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.post(
                            f"{self.agents['coding']}/generate-code",
                            json={
                                "step": step_num,
                                "task_description": step_description,
                                "review_result": review_result
                            }
                        )
                    
                    code_result = response.json()
                    if not code_result["success"]:
                        self.logger.error(f"Code fix failed: {code_result['message']}")
                        return False
                    
                    # Get the updated step code
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.post(
                            f"{self.agents['coding']}/get-step-code",
                            json={"step": step_num}
                        )
                    
                    step_code_result = response.json()
                    if not step_code_result["success"]:
                        self.logger.error(f"Failed to get updated code for step {step_num}")
                        return False
                    
                    step_code = step_code_result["code"]
                
                # Execute only this step's code in Blender
                self.logger.info(f"Executing step {step_num} code in Blender...")
                
                # Never capture views anymore
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.agents['execution']}/run-step-code",
                        json={
                            "code": step_code,
                            "capture_views": False
                        }
                    )
                
                exec_result = response.json()
                if not exec_result.get("ok", False):
                    error_msg = exec_result.get('error') or exec_result.get('result', {}).get('error', 'Unknown error')
                    self.logger.error(f"Step {step_num} execution failed: {error_msg}")
                    return False
                
                self.logger.info(f"Step {step_num} executed successfully")
                
                # Shorter delay - no image capture needed
                await asyncio.sleep(0.5)
                
                # Determine if this step needs review
                if not self._should_review_step(step_num, step_description):
                    self.logger.info(f"✓ Step {step_num} completed (review skipped)")
                    break
                
                # Review the step using bounding box data
                self.logger.info(f"Reviewing step {step_num}...")

                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.post(
                            f"{self.agents['reviewing']}/review",
                            json={
                                "step": step_num,
                                "description": step_description,
                                "edit_hint": "Check if objects are properly sized relative to the house based on bounding box dimensions."
                            }
                        )
                    
                    # Check if response is valid
                    if response.status_code != 200:
                        self.logger.error(f"Review request failed with status {response.status_code}")
                        review_result = {"ok": False, "comment": f"Review request failed with status {response.status_code}"}
                    else:
                        review_result = response.json()
                        
                        # Validate review result format
                        if not isinstance(review_result, dict):
                            self.logger.error(f"Invalid review result format: {review_result}")
                            review_result = {"ok": False, "comment": "Invalid review result format"}
                        elif "ok" not in review_result:
                            self.logger.error(f"Review result missing 'ok' field: {review_result}")
                            review_result = {"ok": False, "comment": "Review result missing 'ok' field"}
                            
                except Exception as e:
                    self.logger.error(f"Review request failed: {str(e)}")
                    review_result = {"ok": False, "comment": f"Review request failed: {str(e)}"}

                # Now safely check the result
                if review_result.get("ok", False):
                    self.logger.info(f"✓ Step {step_num} passed review")
                    break
                else:
                    retry_count += 1
                    comment = review_result.get("comment", "No comment provided")
                    self.logger.warning(f"✗ Step {step_num} failed review: {comment}")
                    
                    if retry_count < max_retries:
                        self.logger.info(f"Retrying step {step_num} (attempt {retry_count + 1}/{max_retries})")
                    else:
                        self.logger.error(f"Step {step_num} failed after {max_retries} attempts")
                        return False
        
        # If we get here, all steps completed successfully
        return True
    
    # REMOVED: _capture_scene_views method - no longer needed
    
    async def generate_scene_for_combination(self, combination: Dict, combination_num: int):
        """Generate scene for a single combination"""
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"Generating scene for combination {combination_num}")
        self.logger.info(f"Objects in this combination:")
        for obj in combination["objects"]:
            self.logger.info(f"  - {obj['instance_id']}: {obj['file_name']}")
        self.logger.info(f"{'='*60}")
        
        # Clear any existing execution_code.py to start fresh
        execution_code_path = Path("execution_code.py")
        if execution_code_path.exists():
            execution_code_path.unlink()
            self.logger.info("Cleared existing execution_code.py")
        
        # Store combination data
        self.current_combination = combination
        
        # Execute workflow steps with combination data
        success = await self.execute_workflow_steps(combination)
        
        if success:
            self.logger.info(f"\n✓ Successfully generated scene for combination {combination_num}")
        else:
            self.logger.error(f"\n✗ Failed to generate scene for combination {combination_num}")
        
        return success
    
    async def run_workflow(self, description: str, assets_csv_path: str, num_combinations: int = 1):
        """Main workflow execution"""
        self.logger.info("\n" + "="*80)
        self.logger.info("STARTING SCENE GENERATION WORKFLOW")
        self.logger.info("="*80)
        self.logger.info(f"Description: {description}")
        self.logger.info(f"Assets CSV: {assets_csv_path}")
        self.logger.info(f"Number of combinations: {num_combinations}")
        self.logger.info(f"Review enabled: {self.enable_review}")
        if not self.enable_review:
            self.logger.info(f"Review-only steps: {self.review_only_steps}")
        
        # Check all agents are healthy
        self.logger.info("\nChecking agent health...")
        if not await self.check_agents_health():
            self.logger.error("Not all agents are healthy. Aborting.")
            return
        
        # Plan the scene
        self.logger.info("\nStep 1: Scene Planning")
        planning_result = await self.plan_scene(description, assets_csv_path, num_combinations)
        if not planning_result:
            return
        
        # Process each combination
        combinations = planning_result["combinations"]
        successful_combinations = 0
        
        for idx, combination in enumerate(combinations):
            combination_num = combination["combination_id"]
            
            if await self.generate_scene_for_combination(combination, combination_num):
                successful_combinations += 1
                
                # Optionally save/export the scene here
                # You might want to add code to save the .blend file or export images
                
            # Add a delay between combinations if needed
            if idx < len(combinations) - 1:
                self.logger.info("\nWaiting before next combination...")
                await asyncio.sleep(5)
        
        # Final summary
        self.logger.info("\n" + "="*80)
        self.logger.info("WORKFLOW COMPLETED")
        self.logger.info(f"Successfully generated: {successful_combinations}/{len(combinations)} scenes")
        self.logger.info("="*80)

async def main():
    # Create orchestrator with review disabled for testing
    # Only enable review for scaling steps
    orchestrator = Orchestrator(
        enable_review=False,  # Disable general review
        review_only_steps={"scale"}  # Only review scaling/adjustment steps
    )
    
    # Example usage - you can modify these parameters
    description = "A house with 2 trees"
    assets_csv_path = "assets/assets.csv"
    num_combinations = 1
    
    # Verify assets.csv exists
    if not Path(assets_csv_path).exists():
        print(f"Error: {assets_csv_path} not found!")
        print(f"Current directory: {Path.cwd()}")
        return
    
    await orchestrator.run_workflow(description, assets_csv_path, num_combinations)

if __name__ == "__main__":
    # You can also accept command line arguments
    import sys
    if len(sys.argv) > 1:
        # Usage: python orchestrator.py "scene description" "path/to/assets.csv" num_combinations
        asyncio.run(main())
    else:
        asyncio.run(main())