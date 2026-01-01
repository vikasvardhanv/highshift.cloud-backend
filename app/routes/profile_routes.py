from fastapi import APIRouter, Depends, HTTPException, Body
from app.models.user import User, Profile
from app.utils.auth import get_current_user
from datetime import datetime

router = APIRouter(prefix="/profiles", tags=["Profiles"])

@router.get("")
async def get_profiles(user: User = Depends(get_current_user)):
    """List all profiles for the current user."""
    return {"profiles": [p.dict() for p in user.profiles]}

@router.post("")
async def create_profile(
    payload: dict = Body(...),
    user: User = Depends(get_current_user)
):
    """Create a new profile."""
    name = payload.get("name", "").strip()
    
    if not name:
        raise HTTPException(status_code=400, detail="Profile name is required")
    
    # Check for duplicates (case-sensitive)
    if any(p.name == name for p in user.profiles):
        raise HTTPException(status_code=400, detail="Profile with this name already exists")
    
    # Check limit
    if len(user.profiles) >= user.max_profiles:
        raise HTTPException(status_code=400, detail=f"Maximum {user.max_profiles} profiles allowed")
    
    new_profile = Profile(name=name)
    user.profiles.append(new_profile)
    user.updated_at = datetime.utcnow()
    await user.save()
    
    return {"success": True, "profile": new_profile.dict()}

@router.delete("/{profile_name}")
async def delete_profile(
    profile_name: str,
    user: User = Depends(get_current_user)
):
    """Delete a profile by name."""
    profile = next((p for p in user.profiles if p.name == profile_name), None)
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    user.profiles = [p for p in user.profiles if p.name != profile_name]
    
    # Optionally: Clear profile_name from linked_accounts associated with this profile
    for acc in user.linked_accounts:
        if acc.profile_name == profile_name:
            acc.profile_name = None
    
    user.updated_at = datetime.utcnow()
    await user.save()
    
    return {"success": True}

@router.post("/{profile_name}/accounts/{account_id}")
async def assign_account_to_profile(
    profile_name: str,
    account_id: str,
    user: User = Depends(get_current_user)
):
    """Assign a linked account to a profile."""
    profile = next((p for p in user.profiles if p.name == profile_name), None)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    account = next((a for a in user.linked_accounts if a.account_id == account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    account.profile_name = profile_name
    user.updated_at = datetime.utcnow()
    await user.save()
    
    return {"success": True, "account": account.account_id, "profile": profile_name}

@router.get("/{profile_name}/accounts")
async def get_profile_accounts(
    profile_name: str,
    user: User = Depends(get_current_user)
):
    """Get all accounts assigned to a specific profile."""
    profile = next((p for p in user.profiles if p.name == profile_name), None)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    accounts = [a for a in user.linked_accounts if a.profile_name == profile_name]
    
    return {
        "profile": profile_name,
        "accounts": [
            {
                "accountId": a.account_id,
                "platform": a.platform,
                "username": a.username,
                "displayName": a.display_name
            }
            for a in accounts
        ]
    }
