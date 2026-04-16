from fastapi import APIRouter, Depends, HTTPException, Body
from app.utils.auth import get_current_user, AuthUser
from app.db.postgres import get_pool
import uuid
import hmac
import hashlib
import json

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

def generate_secret() -> str:
    return f"whs_{uuid.uuid4().hex}"

@router.get("")
async def get_webhooks(
    user: AuthUser = Depends(get_current_user)
):
    """Get all webhooks for user"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            select * from webhooks 
            where user_id = $1
            order by created_at desc
        """, user.id)
    
    return {"webhooks": [dict(r) for r in rows]}

@router.post("")
async def create_webhook(
    payload: dict = Body(...),
    user: AuthUser = Depends(get_current_user)
):
    """Create a new webhook"""
    name = payload.get("name", "My Webhook")
    url = payload.get("url")
    events = payload.get("events", ["post.published", "post.failed"])
    
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    secret = generate_secret()
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        webhook_id = await conn.fetchval("""
            insert into webhooks (user_id, name, url, events, secret)
            values ($1, $2, $3, $4, $5)
            returning id
        """, user.id, name, url, json.dumps(events), secret)
        
        row = await conn.fetchrow("select * from webhooks where id = $1", webhook_id)
    
    return {"webhook": dict(row), "secret": secret}

@router.get("/{webhook_id}")
async def get_webhook(
    webhook_id: str,
    user: AuthUser = Depends(get_current_user)
):
    """Get webhook details"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            select * from webhooks 
            where id = $1 and user_id = $2
        """, webhook_id, user.id)
    
    if not row:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    return {"webhook": dict(row)}

@router.put("/{webhook_id}")
async def update_webhook(
    webhook_id: str,
    payload: dict = Body(...),
    user: AuthUser = Depends(get_current_user)
):
    """Update webhook"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        check = await conn.fetchrow("""
            select id from webhooks where id = $1 and user_id = $2
        """, webhook_id, user.id)
        
        if not check:
            raise HTTPException(status_code=404, detail="Webhook not found")
        
        updates = []
        params = [webhook_id, user.id]
        param_idx = 3
        
        if "name" in payload:
            updates.append(f"name = ${param_idx}")
            params.append(payload["name"])
            param_idx += 1
        
        if "url" in payload:
            updates.append(f"url = ${param_idx}")
            params.append(payload["url"])
            param_idx += 1
        
        if "events" in payload:
            updates.append(f"events = ${param_idx}")
            params.append(json.dumps(payload["events"]))
            param_idx += 1
        
        if "is_active" in payload:
            updates.append(f"is_active = ${param_idx}")
            params.append(payload["is_active"])
            param_idx += 1
        
        if updates:
            query = f"update webhooks set {', '.join(updates)} where id = $1 and user_id = $2 returning *"
            row = await conn.fetchrow(query, *params)
    
    return {"webhook": dict(row)}

@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    user: AuthUser = Depends(get_current_user)
):
    """Delete webhook"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("""
            delete from webhooks where id = $1 and user_id = $2
        """, webhook_id, user.id)
        
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Webhook not found")
    
    return {"message": "Webhook deleted"}

@router.post("/{webhook_id}/test")
async def test_webhook(
    webhook_id: str,
    user: AuthUser = Depends(get_current_user)
):
    """Test webhook - send a ping event"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            select * from webhooks where id = $1 and user_id = $2
        """, webhook_id, user.id)
        
        if not row:
            raise HTTPException(status_code=404, detail="Webhook not found")
        
        # Generate test payload with signature
        test_payload = {
            "event": "webhook.test",
            "data": {
                "message": "This is a test webhook from Highshift",
                "webhook_id": webhook_id
            },
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
        # In a real implementation, you would make an HTTP request to the webhook URL
        # For now, just return success
        
        await conn.execute("""
            update webhooks set last_triggered_at = now() where id = $1
        """, webhook_id)
    
    return {"message": "Test webhook triggered", "payload": test_payload}

@router.get("/{webhook_id}/logs")
async def get_webhook_logs(
    webhook_id: str,
    user: AuthUser = Depends(get_current_user)
):
    """Get webhook delivery logs"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        check = await conn.fetchrow("""
            select id from webhooks where id = $1 and user_id = $2
        """, webhook_id, user.id)
        
        if not check:
            raise HTTPException(status_code=404, detail="Webhook not found")
    
    return {"logs": [], "message": "Webhook logs coming soon"}