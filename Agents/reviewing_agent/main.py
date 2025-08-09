from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from core import ReviewingAgent

app = FastAPI(title="Reviewing Agent")
agent = ReviewingAgent()

class ReviewRequest(BaseModel):
    step: int
    description: str
    edit_hint: str

class ReviewResponse(BaseModel):
    ok: bool
    comment: str

# In reviewing_agent/main.py

@app.post("/review", response_model=ReviewResponse)
async def review(req: ReviewRequest):
    try:
        result = agent.review(req.step, req.description, req.edit_hint)
        
        # Ensure result has correct format
        if not isinstance(result, dict):
            return ReviewResponse(
                ok=False,
                comment=f"Invalid result format from review agent: {type(result)}"
            )
        
        # Ensure 'ok' field exists and is boolean
        ok = result.get("ok", False)
        if not isinstance(ok, bool):
            ok = bool(ok)
        
        # Ensure 'comment' field exists
        comment = result.get("comment", "No comment provided")
        
        return ReviewResponse(ok=ok, comment=comment)
        
    except Exception as e:
        # Always return a valid ReviewResponse even on error
        return ReviewResponse(
            ok=False,
            comment=f"Review agent error: {str(e)}"
        )