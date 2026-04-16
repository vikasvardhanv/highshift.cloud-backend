from fastapi import APIRouter, Depends, HTTPException
from app.utils.auth import get_current_user, AuthUser
from app.db.postgres import fetch_user_by_id, update_user

router = APIRouter(prefix="/brand", tags=["BrandKit"])

@router.get("")
async def get_brand_settings(
    user: AuthUser = Depends(get_current_user)
):
    user_row = await fetch_user_by_id(user.id)
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    
    brand = user_row.get("brand_kit") or {
        "company_name": "",
        "industry": "",
        "website": "",
        "tone": "Professional",
        "description": "",
        "keywords": []
    }
    return {"brand": brand}

@router.post("")
async def update_brand_settings(
    payload: dict,
    user: AuthUser = Depends(get_current_user)
):
    brand_kit = {
        "company_name": payload.get("company_name", ""),
        "industry": payload.get("industry", ""),
        "website": payload.get("website", ""),
        "tone": payload.get("tone", "Professional"),
        "description": payload.get("description", ""),
        "keywords": payload.get("keywords", [])
    }
    await update_user(user.id, {"brand_kit": brand_kit})
    return {"brand": brand_kit, "message": "Brand settings saved"}
