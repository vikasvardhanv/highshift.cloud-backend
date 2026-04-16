from fastapi import APIRouter, Depends, HTTPException
from app.utils.auth import get_current_user, AuthUser
from app.db.postgres import list_scheduled_posts

router = APIRouter(prefix="/posts", tags=["History"])

@router.get("/history")
async def get_post_history(
    user: AuthUser = Depends(get_current_user)
):
    posts = await list_scheduled_posts(str(user.id))
    return {"posts": posts}
