from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.ai_service import generate_post_content
from app.utils.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/ai", tags=["AI"])

class GenerateRequest(BaseModel):
    topic: str
    platform: str = "all"
    tone: Optional[str] = None

class InstantPublishRequest(BaseModel):
    email: str
    postTopic: str
    targetAudience: str
    date: str
    system: Optional[str] = "social_raven"
    apiKey: Optional[str] = None
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    twitter: Optional[str] = None
    linkedin: Optional[str] = None

@router.post("/generate")
async def generate_ai_post(req: GenerateRequest, user: User = Depends(get_current_user)):
    result = await generate_post_content(
        user_id=str(user.id),
        topic=req.topic,
        platform=req.platform,
        tone=req.tone
    )
    return result

@router.post("/instant-publish")
async def instant_publish(req: InstantPublishRequest, user: User = Depends(get_current_user)):
    from app.services.ai_service import trigger_instant_publish
    result = await trigger_instant_publish(
        email=req.email,
        topic=req.postTopic,
        audience=req.targetAudience,
        date=req.date,
        system=req.system,
        api_key=req.apiKey,
        instagram=req.instagram,
        facebook=req.facebook,
        twitter=req.twitter,
        linkedin=req.linkedin
    )
    return result
