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

@app.post("/review", response_model=ReviewResponse)
async def review(req: ReviewRequest):
    try:
        result = agent.review(req.step, req.description, req.edit_hint)
        return ReviewResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint
@app.get("/health")
async def health():
    return {"status": "healthy", "agent": "reviewing"}