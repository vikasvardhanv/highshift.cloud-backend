from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.utils.auth import get_current_user
from app.models.user import User
from app.platforms import instagram, twitter, facebook, linkedin
from app.services.token_service import decrypt_token
from app.utils.logger import logger

router = APIRouter(prefix="/post", tags=["Publishing"])

class PostAccount(BaseModel):
    platform: str
    accountId: str

class MultiPostRequest(BaseModel):
    accounts: List[PostAccount]
    content: str
    media: Optional[List[str]] = []

@router.post("/multi")
async def multi_platform_post(req: MultiPostRequest, user: User = Depends(get_current_user)):
    results = []
    
    for target in req.accounts:
        # Find the linked account in user model
        account = next((a for a in user.linked_accounts if a.platform == target.platform and a.account_id == target.accountId), None)
        
        if not account:
            results.append({"platform": target.platform, "status": "failed", "error": "Account not linked"})
            continue
            
        try:
            token = decrypt_token(account.access_token_enc)
            
            if target.platform == "twitter":
                res = await twitter.post_tweet(token, req.content)
                results.append({"platform": "twitter", "status": "success", "id": res.get("data", {}).get("id")})
                
            elif target.platform == "instagram":
                # Instagram requires an image URL
                if not req.media:
                    results.append({"platform": "instagram", "status": "failed", "error": "Media URL required for Instagram"})
                    continue
                res = await instagram.publish_image(token, target.accountId, req.media[0], req.content)
                results.append({"platform": "instagram", "status": "success", "id": res.get("id")})
                
            elif target.platform == "facebook":
                res = await facebook.post_to_page(token, target.accountId, req.content)
                results.append({"platform": "facebook", "status": "success", "id": res.get("id")})
                
            elif target.platform == "linkedin":
                # LinkedIn URN needed, normally stored in rawProfile or as account_id
                res = await linkedin.post_to_profile(token, target.accountId, req.content)
                results.append({"platform": "linkedin", "status": "success", "id": res.get("id")})
                
            else:
                results.append({"platform": target.platform, "status": "failed", "error": "Platform publishing not implemented yet"})
                
        except Exception as e:
            logger.error(f"Failed to post to {target.platform}: {e}")
            results.append({"platform": target.platform, "status": "failed", "error": str(e)})
            
    return {"results": results}
