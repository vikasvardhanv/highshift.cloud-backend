from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.ai_service import generate_post_content
from app.utils.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/ai", tags=["AI"])

class GenerateRequest(BaseModel):
    topic: str
    platform: str
    tone: Optional[str] = None

@router.post("/generate")
async def generate_ai_post(req: GenerateRequest, user: User = Depends(get_current_user)):
    result = await generate_post_content(
        user_id=str(user.id),
        topic=req.topic,
        platform=req.platform,
        tone=req.tone
    )
    return result
