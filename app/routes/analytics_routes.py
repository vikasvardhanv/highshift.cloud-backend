from fastapi import APIRouter, Depends, Query
from app.services.analytics_service import get_account_analytics
from app.utils.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/{accountId}")
async def get_analytics(
    accountId: str, 
    days: int = Query(30, ge=1, le=90),
    user: User = Depends(get_current_user)
):
    result = await get_account_analytics(str(user.id), account_id=accountId, days=days)
    return result

@router.get("/dashboard/summary")
async def get_dashboard_analytics(
    user: User = Depends(get_current_user)
):
    from app.services.analytics_dashboard_service import get_dashboard_summary
    return await get_dashboard_summary(user)
