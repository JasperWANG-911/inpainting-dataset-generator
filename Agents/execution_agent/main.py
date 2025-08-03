from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from core import ExecutionAgent

app = FastAPI(title="Execution Agent")
agent = ExecutionAgent()

class RunScriptRequest(BaseModel):
    script_path: str

class RunScriptResponse(BaseModel):
    ok: bool
    result: dict

@app.post("/run-script", response_model=RunScriptResponse)
async def run_script(req: RunScriptRequest):
    try:
        # use socket to send the script to Blender
        res = agent.execute_codes_file(req.script_path)
        if res is None:
            raise RuntimeError("Execution failed or returned no result")
        return RunScriptResponse(ok=res.get("status")=="success", result=res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
