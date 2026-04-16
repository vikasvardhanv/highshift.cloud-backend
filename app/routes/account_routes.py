from fastapi import APIRouter, Depends, HTTPException
from app.utils.auth import get_current_user, AuthUser
from app.db.postgres import fetch_user_by_id, update_user

router = APIRouter(prefix="/linked-accounts", tags=["Accounts"])

@router.get("")
async def get_linked_accounts(user: AuthUser = Depends(get_current_user)):
    user_id = user.id
    user_row = await fetch_user_by_id(user_id)
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    return {"accounts": user_row.get("linked_accounts") or []}

@router.delete("/disconnect/{platform}/{account_id}")
async def disconnect_account(
    platform: str,
    account_id: str,
    user: AuthUser = Depends(get_current_user)
):
    user_id = user.id
    user_row = await fetch_user_by_id(user_id)
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    
    linked_accounts = user_row.get("linked_accounts") or []
    original_count = len(linked_accounts)
    
    # Filter out the account to remove
    linked_accounts = [
        acc for acc in linked_accounts 
        if not (acc.get("platform") == platform and acc.get("accountId") == account_id)
    ]
    
    # If no change, maybe it didn't exist
    if len(linked_accounts) == original_count:
        raise HTTPException(status_code=404, detail="Account not found")
    
    await update_user(user_id, {"linked_accounts": linked_accounts})
    return {"message": "Disconnected successfully", "remaining": len(linked_accounts)}
