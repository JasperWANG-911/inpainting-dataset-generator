import httpx
import json
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
import logging

class Orchestrator:
    """Main orchestrator that coordinates all agents"""
    
    def __init__(self):
        self.agents = {
            "execution": "http://localhost:8001",
            "reviewing": "http://localhost:8002", 
            "scene_planning": "http://localhost:8003",
            "coding": "http://localhost:8004"
        }
        self.workflow_config = self._load_workflow_config()
        self.logger = self._setup_logger()
        self.timeout = httpx.Timeout(30.0, connect=5.0)
        
    def _setup_logger(self):
        logger = logging.getLogger('Orchestrator')
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger
        
    def _load_workflow_config(self):
        with open("workflow_config.json", "r") as f:
            return json.load(f)
    
    async def check_agents_health(self):
        """Check if all agents are running"""
        for name, url in self.agents.items():
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
    
    async def execute_workflow_steps(self, combination: Dict):
        """Execute all workflow steps with review loop"""
        total_steps = len(self.workflow_config["steps"])
        
        for step_num in range(1, total_steps + 1):
            self.logger.info(f"\n--- Executing Step {step_num}/{total_steps} ---")
            
            step_config = self.workflow_config["steps"][str(step_num)]
            task_description = step_config["task_description"]
            
            max_retries = 3
            retry_count = 0
            review_result = None
            
            while retry_count < max_retries:
                # Generate/update code for this step
                self.logger.info(f"Generating code for step {step_num}...")
                
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.agents['coding']}/generate-code",
                        json={
                            "step": step_num,
                            "task_description": task_description,
                            "review_result": review_result
                        }
                    )
                
                code_result = response.json()
                if not code_result["success"]:
                    self.logger.error(f"Code generation failed: {code_result['message']}")
                    return False
                
                self.logger.info(f"Code generated: {code_result['message']}")
                
                # Execute the code in Blender
                self.logger.info("Executing code in Blender...")
                
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.agents['execution']}/run-script",
                        json={"script_path": code_result["code_path"]}
                    )
                
                exec_result = response.json()
                if not exec_result.get("ok", False):
                    error_msg = exec_result.get('error') or exec_result.get('result', {}).get('error', 'Unknown error')
                    self.logger.error(f"Code execution failed: {error_msg}")
                    return False
                
                self.logger.info("Code executed successfully")
                
                # Wait for Blender to update the scene
                await asyncio.sleep(3)
                
                # Review the step
                self.logger.info(f"Reviewing step {step_num}...")
                
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.agents['reviewing']}/review",
                        json={
                            "step": step_num,
                            "description": task_description,
                            "edit_hint": step_config.get("edit_hints", "")
                        }
                    )
                
                review_result = response.json()
                
                if review_result["ok"]:
                    self.logger.info(f"✓ Step {step_num} passed review")
                    break
                else:
                    retry_count += 1
                    self.logger.warning(f"✗ Step {step_num} failed review: {review_result['comment']}")
                    
                    if retry_count < max_retries:
                        self.logger.info(f"Retrying step {step_num} (attempt {retry_count + 1}/{max_retries})")
                    else:
                        self.logger.error(f"Step {step_num} failed after {max_retries} attempts")
                        return False
        
        return True
    
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
        
        # Execute workflow steps
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
    orchestrator = Orchestrator()
    
    # Example usage - you can modify these parameters
    description = "A house with 2 trees"
    assets_csv_path = "assets/assets.csv"  # Updated path to assets folder
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