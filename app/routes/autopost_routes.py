from fastapi import APIRouter, Depends, HTTPException, Body
from app.utils.auth import get_current_user, AuthUser
from app.db.postgres import get_pool
import uuid
import json
import httpx
from datetime import datetime

router = APIRouter(prefix="/autopost", tags=["Autopost"])

@router.get("")
async def get_autopost_configs(
    user: AuthUser = Depends(get_current_user)
):
    """Get all autopost configurations"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            select * from autopost_configs 
            where user_id = $1
            order by created_at desc
        """, user.id)
    
    return {"configs": [dict(r) for r in rows]}

@router.post("")
async def create_autopost_config(
    payload: dict = Body(...),
    user: AuthUser = Depends(get_current_user)
):
    """Create a new autopost configuration from RSS feed"""
    name = payload.get("name", "My RSS Feed")
    feed_url = payload.get("feed_url")
    platforms = payload.get("platforms", [])
    post_template = payload.get("post_template", "{title}\n\n{content}")
    
    if not feed_url:
        raise HTTPException(status_code=400, detail="Feed URL is required")
    
    # Validate feed URL by fetching
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(feed_url)
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Invalid RSS feed URL")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot fetch RSS feed: {str(e)}")
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        config_id = await conn.fetchval("""
            insert into autopost_configs (
                user_id, name, feed_url, platforms, post_template, is_active
            ) values ($1, $2, $3, $4, $5, $6)
            returning id
        """, user.id, name, feed_url, json.dumps(platforms), post_template, True)
        
        row = await conn.fetchrow("select * from autopost_configs where id = $1", config_id)
    
    return {"config": dict(row)}

@router.get("/{config_id}")
async def get_autopost_config(
    config_id: str,
    user: AuthUser = Depends(get_current_user)
):
    """Get autopost config details"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            select * from autopost_configs 
            where id = $1 and user_id = $2
        """, config_id, user.id)
    
    if not row:
        raise HTTPException(status_code=404, detail="Autopost config not found")
    
    return {"config": dict(row)}

@router.put("/{config_id}")
async def update_autopost_config(
    config_id: str,
    payload: dict = Body(...),
    user: AuthUser = Depends(get_current_user)
):
    """Update autopost config"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        check = await conn.fetchrow("""
            select id from autopost_configs where id = $1 and user_id = $2
        """, config_id, user.id)
        
        if not check:
            raise HTTPException(status_code=404, detail="Autopost config not found")
        
        updates = []
        params = [config_id, user.id]
        param_idx = 3
        
        for field in ["name", "feed_url", "platforms", "post_template", "is_active"]:
            if field in payload:
                updates.append(f"{field} = ${param_idx}")
                if field in ["platforms"]:
                    params.append(json.dumps(payload[field]))
                else:
                    params.append(payload[field])
                param_idx += 1
        
        if updates:
            query = f"update autopost_configs set {', '.join(updates)} where id = $1 and user_id = $2 returning *"
            row = await conn.fetchrow(query, *params)
    
    return {"config": dict(row)}

@router.delete("/{config_id}")
async def delete_autopost_config(
    config_id: str,
    user: AuthUser = Depends(get_current_user)
):
    """Delete autopost config"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("""
            delete from autopost_configs where id = $1 and user_id = $2
        """, config_id, user.id)
        
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Autopost config not found")
    
    return {"message": "Autopost config deleted"}

@router.post("/{config_id}/fetch")
async def fetch_and_preview_rss(
    config_id: str,
    user: AuthUser = Depends(get_current_user)
):
    """Fetch RSS feed and return preview of items to post"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            select * from autopost_configs 
            where id = $1 and user_id = $2
        """, config_id, user.id)
        
        if not row:
            raise HTTPException(status_code=404, detail="Autopost config not found")
        
        feed_url = row["feed_url"]
        post_template = row["post_template"]
    
    # Fetch and parse RSS
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(feed_url)
            content = response.text
        
        # Simple XML parsing for RSS
        items = []
        import re
        title_match = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>', content)
        desc_match = re.search(r'<description><!\[CDATA\[(.*?)\]\]></description>|<description>(.*?)</description>', content)
        link_match = re.search(r'<link>(.*?)</link>', content)
        
        # For now, return sample preview
        preview = {
            "feed_title": "Sample RSS Feed",
            "items": [
                {
                    "title": "Sample Post Title",
                    "content": "This is a preview of how your post will look...",
                    "preview": "This is a preview of how your post will look..."
                }
            ],
            "message": "RSS parsing coming soon - configure autopost to auto-post from RSS feeds"
        }
        
        # Update last_fetched_at
        async with pool.acquire() as conn:
            await conn.execute("""
                update autopost_configs set last_fetched_at = now() where id = $1
            """, config_id)
        
        return preview
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching RSS: {str(e)}")

@router.post("/{config_id}/trigger")
async def trigger_autopost(
    config_id: str,
    user: AuthUser = Depends(get_current_user)
):
    """Manually trigger autopost for a config"""
    # This would fetch RSS and create scheduled posts
    return {
        "message": "Autopost triggered - will fetch RSS and create posts",
        "status": "pending"
    }