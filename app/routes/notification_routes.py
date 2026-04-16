from fastapi import APIRouter, Depends, HTTPException, Body
from app.utils.auth import get_current_user, AuthUser
from app.db.postgres import get_pool

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.get("")
async def get_notifications(
    limit: int = 20,
    offset: int = 0,
    unread_only: bool = False,
    user: AuthUser = Depends(get_current_user)
):
    """Get user notifications"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        query = """
            select * from notifications 
            where user_id = $1
        """
        params = [user.id]
        
        if unread_only:
            query += " and is_read = false"
        
        query += " order by created_at desc limit $" + str(len(params) + 1) + " offset $" + str(len(params) + 2)
        params.extend([limit, offset])
        
        rows = await conn.fetch(query, *params)
        
        # Get unread count
        unread_count = await conn.fetchval("""
            select count(*) from notifications 
            where user_id = $1 and is_read = false
        """, user.id)
    
    return {
        "notifications": [dict(r) for r in rows],
        "unread_count": unread_count
    }

@router.get("/unread-count")
async def get_unread_count(user: AuthUser = Depends(get_current_user)):
    """Get unread notification count"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval("""
            select count(*) from notifications 
            where user_id = $1 and is_read = false
        """, user.id)
    
    return {"unread_count": count}

@router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    user: AuthUser = Depends(get_current_user)
):
    """Mark a notification as read"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            update notifications set is_read = true 
            where id = $1 and user_id = $2
        """, notification_id, user.id)
    
    return {"message": "Notification marked as read"}

@router.put("/read-all")
async def mark_all_read(user: AuthUser = Depends(get_current_user)):
    """Mark all notifications as read"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            update notifications set is_read = true 
            where user_id = $1 and is_read = false
        """, user.id)
    
    return {"message": "All notifications marked as read"}

@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    user: AuthUser = Depends(get_current_user)
):
    """Delete a notification"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            delete from notifications 
            where id = $1 and user_id = $2
        """, notification_id, user.id)
    
    return {"message": "Notification deleted"}

@router.delete("")
async def delete_all_notifications(user: AuthUser = Depends(get_current_user)):
    """Delete all notifications"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("delete from notifications where user_id = $1", user.id)
    
    return {"message": "All notifications deleted"}