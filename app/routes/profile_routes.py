from fastapi import APIRouter, Depends, HTTPException, Body
from app.utils.auth import get_current_user, AuthUser
from app.db.postgres import fetch_user_by_id, update_user
from typing import List, Optional
import uuid
import json

router = APIRouter(prefix="/profiles", tags=["Profiles"])


DEFAULT_CREATED_AT = "2024-01-01T00:00:00"


def _decode_json_value(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _normalize_profile(profile):
    profile = _decode_json_value(profile)
    if isinstance(profile, dict):
        profile_id = profile.get("id") or str(uuid.uuid4())
        name = profile.get("name") or "Default"
        created_at = profile.get("created_at") or DEFAULT_CREATED_AT
        if _is_malformed_character_profile(profile_id, name, created_at):
            return None
        return {
            **profile,
            "id": str(profile_id),
            "name": name,
            "created_at": created_at,
        }
    if isinstance(profile, str) and profile.strip():
        if len(profile.strip()) == 1:
            return None
        return {
            "id": profile,
            "name": profile,
            "created_at": DEFAULT_CREATED_AT,
        }
    return None


def _is_malformed_character_profile(profile_id, name, created_at):
    return (
        isinstance(profile_id, str)
        and isinstance(name, str)
        and len(profile_id) == 1
        and len(name) == 1
        and profile_id == name
        and created_at == DEFAULT_CREATED_AT
    )


def _normalize_account(account):
    account = _decode_json_value(account)
    if not isinstance(account, dict):
        return None

    normalized = dict(account)
    profile_id = normalized.get("profileId") or normalized.get("profile_id")
    if profile_id:
        normalized["profileId"] = str(profile_id)
    return normalized


def _as_list(value):
    value = _decode_json_value(value)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return [value]


def _normalize_profiles(profiles):
    return [
        profile
        for profile in (_normalize_profile(profile) for profile in _as_list(profiles))
        if profile
    ]


def _normalize_accounts(accounts):
    return [
        account
        for account in (_normalize_account(account) for account in _as_list(accounts))
        if account
    ]


@router.get("")
async def get_profiles(user: AuthUser = Depends(get_current_user)):
    """Get all profiles for the current user, including their linked accounts."""
    user_id = user.id
    user_row = await fetch_user_by_id(user_id)
    
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    
    raw_profiles = user_row.get("profiles")
    raw_linked_accounts = user_row.get("linked_accounts")
    profiles = _normalize_profiles(raw_profiles)
    linked_accounts = _normalize_accounts(raw_linked_accounts)
    should_update_user = raw_profiles != profiles or raw_linked_accounts != linked_accounts
    
    # Ensure user has at least one default profile if none exist
    if not profiles:
        default_profile = {
            "id": str(uuid.uuid4()),
            "name": "Default",
            "created_at": DEFAULT_CREATED_AT
        }
        
        # Assign existing accounts to this default profile if they have no profile_id
        for acc in linked_accounts:
            if not acc.get("profileId"):
                acc["profileId"] = default_profile["id"]
        
        profiles = [default_profile]
        should_update_user = True

    if should_update_user:
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
    
    profiles = _normalize_profiles(user_row.get("profiles"))
    
    # Check if name exists
    if any(p.get("name") == name for p in profiles):
        raise HTTPException(status_code=400, detail="Profile with this name already exists")
    
    new_profile = {
        "id": str(uuid.uuid4()),
        "name": name,
        "created_at": DEFAULT_CREATED_AT
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
    
    profiles = _normalize_profiles(user_row.get("profiles"))
    linked_accounts = _normalize_accounts(user_row.get("linked_accounts"))
    
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
