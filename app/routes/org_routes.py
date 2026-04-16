from fastapi import APIRouter, Depends, HTTPException, Body
from app.utils.auth import get_current_user, AuthUser
from app.db.postgres import fetch_user_by_id, update_user, get_pool
import uuid
import json
import re

router = APIRouter(prefix="/organizations", tags=["Organizations"])

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = text.strip('-')
    return text

@router.get("")
async def get_organizations(user: AuthUser = Depends(get_current_user)):
    """Get all organizations the user belongs to"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Get organizations where user is owner or member
        rows = await conn.fetch("""
            select o.*, om.role as member_role
            from organizations o
            left join organization_members om on o.id = om.organization_id and om.user_id = $1
            where o.owner_id = $1 or om.user_id = $1
            order by o.created_at desc
        """, user.id)
    
    return {"organizations": [dict(r) for r in rows]}

@router.post("")
async def create_organization(
    payload: dict = Body(...),
    user: AuthUser = Depends(get_current_user)
):
    """Create a new organization"""
    name = payload.get("name", "My Organization")
    slug = slugify(payload.get("slug") or name)
    
    # Check slug uniqueness
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("select id from organizations where slug = $1", slug)
        if existing:
            slug = f"{slug}-{uuid.uuid4().hex[:8]}"
        
        org_id = await conn.fetchval("""
            insert into organizations (name, slug, owner_id, settings)
            values ($1, $2, $3, $4)
            returning id
        """, name, slug, user.id, json.dumps({}))
        
        # Add owner as admin member
        await conn.execute("""
            insert into organization_members (organization_id, user_id, role)
            values ($1, $2, 'admin')
        """, org_id, user.id)
        
        row = await conn.fetchrow("select * from organizations where id = $1", org_id)
    
    return {"organization": dict(row), "message": "Organization created"}

@router.get("/{org_id}")
async def get_organization(
    org_id: str,
    user: AuthUser = Depends(get_current_user)
):
    """Get organization details"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            select o.*, om.role as member_role
            from organizations o
            left join organization_members om on o.id = om.organization_id and om.user_id = $1
            where o.id = $2 and (o.owner_id = $1 or om.user_id = $1)
        """, user.id, org_id)
    
    if not row:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    return {"organization": dict(row)}

@router.put("/{org_id}")
async def update_organization(
    org_id: str,
    payload: dict = Body(...),
    user: AuthUser = Depends(get_current_user)
):
    """Update organization settings"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Check ownership or admin
        row = await conn.fetchrow("""
            select o.*, om.role as member_role
            from organizations o
            left join organization_members om on o.id = om.organization_id and om.user_id = $1
            where o.id = $2 and (o.owner_id = $1 or om.role in ('admin', 'owner'))
        """, user.id, org_id)
        
        if not row:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Update fields
        updates = []
        params = [org_id]
        param_idx = 2
        
        if "name" in payload:
            updates.append(f"name = ${param_idx}")
            params.append(payload["name"])
            param_idx += 1
        
        if "settings" in payload:
            updates.append(f"settings = ${param_idx}")
            params.append(json.dumps(payload["settings"]))
            param_idx += 1
        
        if "billing_email" in payload:
            updates.append(f"billing_email = ${param_idx}")
            params.append(payload["billing_email"])
            param_idx += 1
        
        if updates:
            query = f"update organizations set {', '.join(updates)} where id = $1 returning *"
            row = await conn.fetchrow(query, *params)
    
    return {"organization": dict(row), "message": "Organization updated"}

@router.delete("/{org_id}")
async def delete_organization(
    org_id: str,
    user: AuthUser = Depends(get_current_user)
):
    """Delete organization (owner only)"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("select owner_id from organizations where id = $1", org_id)
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        if row["owner_id"] != user.id:
            raise HTTPException(status_code=403, detail="Only owner can delete organization")
        
        await conn.execute("delete from organizations where id = $1", org_id)
    
    return {"message": "Organization deleted"}

@router.get("/{org_id}/members")
async def get_organization_members(
    org_id: str,
    user: AuthUser = Depends(get_current_user)
):
    """Get organization members"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Check access
        check = await conn.fetchrow("""
            select o.*, om.role as member_role
            from organizations o
            left join organization_members om on o.id = om.organization_id and om.user_id = $1
            where o.id = $2 and (o.owner_id = $1 or om.user_id = $1)
        """, user.id, org_id)
        
        if not check:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        rows = await conn.fetch("""
            select om.*, u.email, u.full_name, u.avatar_url
            from organization_members om
            join users u on om.user_id = u.id
            where om.organization_id = $1
            order by om.created_at
        """, org_id)
    
    return {"members": [dict(r) for r in rows]}

@router.post("/{org_id}/members")
async def invite_organization_member(
    org_id: str,
    payload: dict = Body(...),
    user: AuthUser = Depends(get_current_user)
):
    """Invite a user to organization"""
    email = payload.get("email")
    role = payload.get("role", "user")
    
    if not email:
        raise HTTPException(status_code=400, detail="Email required")
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Check admin/owner
        check = await conn.fetchrow("""
            select o.*, om.role as member_role
            from organizations o
            left join organization_members om on o.id = om.organization_id and om.user_id = $1
            where o.id = $2 and (o.owner_id = $1 or om.role in ('admin', 'owner'))
        """, user.id, org_id)
        
        if not check:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Find user by email
        user_row = await conn.fetchrow("select id, email from users where lower(email) = lower($1)", email)
        if not user_row:
            return {"message": "User not found. They need to register first.", "invited": False}
        
        # Check if already member
        existing = await conn.fetchrow("""
            select id from organization_members 
            where organization_id = $1 and user_id = $2
        """, org_id, user_row["id"])
        
        if existing:
            raise HTTPException(status_code=400, detail="User is already a member")
        
        # Add member
        await conn.execute("""
            insert into organization_members (organization_id, user_id, role, invited_by)
            values ($1, $2, $3, $4)
        """, org_id, user_row["id"], role, user.id)
        
        # Create notification
        await conn.execute("""
            insert into notifications (user_id, organization_id, title, message, type)
            values ($1, $2, $3, $4, 'info')
        """, user_row["id"], org_id, f"Organization Invitation", f"You have been invited to join an organization")
    
    return {"message": "User invited", "invited": True}

@router.delete("/{org_id}/members/{member_id}")
async def remove_organization_member(
    org_id: str,
    member_id: str,
    user: AuthUser = Depends(get_current_user)
):
    """Remove a member from organization"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Check admin/owner
        check = await conn.fetchrow("""
            select o.*, om.role as member_role
            from organizations o
            left join organization_members om on o.id = om.organization_id and om.user_id = $1
            where o.id = $2 and (o.owner_id = $1 or om.role in ('admin', 'owner'))
        """, user.id, org_id)
        
        if not check:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Can't remove owner
        org = await conn.fetchrow("select owner_id from organizations where id = $1", org_id)
        if org and org["owner_id"] == member_id:
            raise HTTPException(status_code=400, detail="Cannot remove organization owner")
        
        await conn.execute("""
            delete from organization_members 
            where organization_id = $1 and user_id = $2
        """, org_id, member_id)
    
    return {"message": "Member removed"}

@router.put("/{org_id}/members/{member_id}")
async def update_member_role(
    org_id: str,
    member_id: str,
    payload: dict = Body(...),
    user: AuthUser = Depends(get_current_user)
):
    """Update member role"""
    role = payload.get("role", "user")
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Check owner
        check = await conn.fetchrow("""
            select owner_id from organizations where id = $1
        """, org_id)
        
        if not check or check["owner_id"] != user.id:
            raise HTTPException(status_code=403, detail="Only owner can change roles")
        
        await conn.execute("""
            update organization_members set role = $1 
            where organization_id = $2 and user_id = $3
        """, role, org_id, member_id)
    
    return {"message": "Role updated"}