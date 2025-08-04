from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List
from core import CodingAgent

app = FastAPI(title="Coding Agent")
agent = CodingAgent()

class GenerateCodeRequest(BaseModel):
    step: int
    task_description: str
    review_result: Optional[dict] = None

class GenerateCodeResponse(BaseModel):
    success: bool
    message: str
    code_path: str
    fixed_steps: Optional[List[int]] = None
    used_function: Optional[str] = None

@app.post("/generate-code", response_model=GenerateCodeResponse)
async def generate_code(req: GenerateCodeRequest):
    try:
        result = agent.generate_code(
            step=req.step,
            task_description=req.task_description,
            review_result=req.review_result
        )
        return GenerateCodeResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "healthy", "agent": "coding"}

@app.get("/status")
async def status():
    """Get current status of the coding agent"""
    return {
        "fixed_steps": list(agent.fixed_steps),
        "execution_code_exists": agent.execution_code_path.exists(),
        "workflow_loaded": bool(agent.workflow_config)
    }