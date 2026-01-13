from fastapi import APIRouter, Depends, HTTPException, Body
from app.models.user import User, Profile
from app.utils.auth import get_current_user
from typing import List
import uuid

async def ensure_db():
    from main import ensure_beanie_initialized
    await ensure_beanie_initialized()

router = APIRouter(prefix="/profiles", tags=["Profiles"], dependencies=[Depends(ensure_db)])

@router.get("")
async def get_profiles(user: User = Depends(get_current_user)):
    """Get all profiles for the current user, including their linked accounts."""
    results = []
    
    # Ensure user has at least one default profile if none exist
    if not user.profiles:
        default_profile = Profile(name="Default")
        user.profiles = [default_profile]
        # Assign existing accounts to this default profile if they have no profile_id
        for acc in user.linked_accounts:
            if not acc.profile_id:
                acc.profile_id = default_profile.id
        await user.save()

    for profile in user.profiles:
        # filter accounts for this profile
        accounts = [acc for acc in user.linked_accounts if acc.profile_id == profile.id]
        results.append({
            "id": profile.id,
            "name": profile.name,
            "created_at": profile.created_at,
            "accounts": accounts
        })
    return {"profiles": results}

@router.post("")
async def create_profile(name: str = Body(..., embed=True), user: User = Depends(get_current_user)):
    """Create a new profile."""
    # Check if name exists
    if any(p.name == name for p in user.profiles):
        raise HTTPException(status_code=400, detail="Profile with this name already exists")
    
    # Check limits
    # (Optional: Implement plan limits later)
    
    new_profile = Profile(name=name)
    user.profiles.append(new_profile)
    await user.save()
    
    return new_profile

@router.delete("/{profile_id}")
async def delete_profile(profile_id: str, user: User = Depends(get_current_user)):
    """Delete a profile and its associated accounts."""
    
    # Check if profile exists
    profile = next((p for p in user.profiles if p.id == profile_id), None)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
        
    # Prevent deleting the last profile maybe? Or allow it and then they have 0 profiles. 
    # Let's allow deleting any.
    
    # Remove accounts associated with this profile
    user.linked_accounts = [acc for acc in user.linked_accounts if acc.profile_id != profile_id]
    
    # Remove profile
    user.profiles = [p for p in user.profiles if p.id != profile_id]
    
    await user.save()
    return {"message": "Profile deleted", "deleted_profile_id": profile_id}
