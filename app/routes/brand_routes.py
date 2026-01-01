from fastapi import APIRouter, Depends, HTTPException
from app.models.user import User
from app.models.brand_kit import BrandKit
from app.utils.auth import get_current_user, get_api_key_user
import uuid

# Check if DB is ready
async def ensure_db():
    from main import ensure_beanie_initialized
    await ensure_beanie_initialized()

router = APIRouter(prefix="/brand", tags=["BrandKit"], dependencies=[Depends(ensure_db)])

@router.get("")
async def get_brand_settings(
    user: User = Depends(get_api_key_user)
):
    brand = await BrandKit.find_one(BrandKit.user_id == user.id)
    if not brand:
        # Return default structure if no brand kit exists
        return {"brand": {
            "company_name": "",
            "industry": "",
            "website": "",
            "tone": "Professional",
            "description": "",
            "keywords": []
        }}
    return {"brand": brand}

@router.post("")
async def update_brand_settings(
    payload: dict,
    user: User = Depends(get_api_key_user)
):
    brand = await BrandKit.find_one(BrandKit.user_id == user.id)
    
    if not brand:
        brand = BrandKit(
            user_id=user.id,
            company_name=payload.get("company_name", ""),
            industry=payload.get("industry", ""),
            website=payload.get("website", ""),
            tone=payload.get("tone", "Professional"),
            description=payload.get("description", ""),
            keywords=payload.get("keywords", [])
        )
        await brand.insert()
    else:
        brand.company_name = payload.get("company_name", brand.company_name)
        brand.industry = payload.get("industry", brand.industry)
        brand.website = payload.get("website", brand.website)
        brand.tone = payload.get("tone", brand.tone)
        brand.description = payload.get("description", brand.description)
        brand.keywords = payload.get("keywords", brand.keywords)
        await brand.save()
        
    return {"brand": brand, "message": "Brand settings saved"}
