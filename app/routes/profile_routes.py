from fastapi import APIRouter, Depends, HTTPException, Body
from app.utils.auth import get_current_user, AuthUser
from app.db.postgres import fetch_user_by_id, update_user
from typing import List, Optional
import uuid
import json

router = APIRouter(prefix="/profiles", tags=["Profiles"])

@router.get("")
async def get_profiles(user: AuthUser = Depends(get_current_user)):
    """Get all profiles for the current user, including their linked accounts."""
    user_id = user.id
    user_row = await fetch_user_by_id(user_id)
    
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    
    profiles = user_row.get("profiles") or []
    linked_accounts = user_row.get("linked_accounts") or []
    
    # Ensure user has at least one default profile if none exist
    if not profiles:
        default_profile = {
            "id": str(uuid.uuid4()),
            "name": "Default",
            "created_at": "2024-01-01T00:00:00"
        }
        
        # Assign existing accounts to this default profile if they have no profile_id
        for acc in linked_accounts:
            if not acc.get("profileId"):
                acc["profileId"] = default_profile["id"]
        
        profiles = [default_profile]
        await update_user(user_id, {"profiles": profiles, "linked_accounts": linked_accounts})
    
    results = []
    for profile in profiles:
        profile_id = profile.get("id")
        # filter accounts for this profile
        accounts = [acc for acc in linked_accounts if acc.get("profileId") == profile_id]
        results.append({
            "id": profile_id,
            "name": profile.get("name"),
            "created_at": profile.get("created_at"),
            "accounts": accounts
        })
    return {"profiles": results}

@router.post("")
async def create_profile(name: str = Body(..., embed=True), user: AuthUser = Depends(get_current_user)):
    """Create a new profile."""
    user_id = user.id
    user_row = await fetch_user_by_id(user_id)
    
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    
    profiles = user_row.get("profiles") or []
    
    # Check if name exists
    if any(p.get("name") == name for p in profiles):
        raise HTTPException(status_code=400, detail="Profile with this name already exists")
    
    new_profile = {
        "id": str(uuid.uuid4()),
        "name": name,
        "created_at": "2024-01-01T00:00:00"
    }
    profiles.append(new_profile)
    await update_user(user_id, {"profiles": profiles})
    
    return new_profile

@router.delete("/{profile_id}")
async def delete_profile(profile_id: str, user: AuthUser = Depends(get_current_user)):
    """Delete a profile and its associated accounts."""
    user_id = user.id
    user_row = await fetch_user_by_id(user_id)
    
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    
    profiles = user_row.get("profiles") or []
    linked_accounts = user_row.get("linked_accounts") or []
    
    # Check if profile exists
    profile = next((p for p in profiles if p.get("id") == profile_id), None)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Remove accounts associated with this profile
    linked_accounts = [acc for acc in linked_accounts if acc.get("profileId") != profile_id]
    
    # Remove profile
    profiles = [p for p in profiles if p.get("id") != profile_id]
    
    await update_user(user_id, {"profiles": profiles, "linked_accounts": linked_accounts})
    return {"message": "Profile deleted", "deleted_profile_id": profile_id}
