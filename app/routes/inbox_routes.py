from typing import Any, Dict, List
import uuid
import httpx
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from app.utils.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/inbox", tags=["Inbox"])

# Mock data removed in favor of live Meta API integration

from app.services.token_service import decrypt_token
from app.platforms import facebook

@router.get("/threads")
async def get_threads(current_user: User = Depends(get_current_user)):
    """Fetch all inbox threads for the connected accounts."""
    threads = []
    
    for acc in current_user.linked_accounts:
        if acc.platform in ["facebook", "instagram"] and acc.access_token_enc:
            try:
                page_access_token = decrypt_token(acc.access_token_enc)
                if acc.platform == "facebook":
                    conversations = await facebook.get_page_conversations(acc.account_id, page_access_token)
                else:
                    # instagram
                    ig_user_id = acc.raw_profile.get("id") if acc.raw_profile else None
                    if not ig_user_id:
                        continue
                    conversations = await facebook.get_ig_conversations(ig_user_id, page_access_token)
                
                for conv in conversations:
                    # Parse Meta's response format
                    participants = conv.get("participants", {}).get("data", [])
                    # The sender is usually the participant who is not the page
                    sender = next((p for p in participants if p.get("id") != acc.account_id), {})
                    sender_name = sender.get("name") or sender.get("username") or "Unknown User"
                    
                    threads.append({
                        "id": f"{acc.platform}_{acc.account_id}_{conv.get('id')}",
                        "real_thread_id": conv.get("id"), # Store the real ID for subsequent calls
                        "account_id": acc.account_id,
                        "platform": acc.platform,
                        "sender_name": sender_name,
                        "sender_avatar": f"https://ui-avatars.com/api/?name={sender_name.replace(' ', '+')}&background=random",
                        "snippet": conv.get("snippet", ""),
                        "is_read": conv.get("unread_count", 0) == 0,
                        "updated_at": conv.get("updated_time", datetime.now(timezone.utc).isoformat()),
                    })
            except Exception as e:
                import logging
                logging.error(f"Error fetching threads for {acc.platform} account {acc.account_id}: {e}")
                
    # Sort threads by updated_at descending
    threads.sort(key=lambda x: x["updated_at"], reverse=True)
    return {"threads": threads}

@router.get("/threads/{thread_id}/messages")
async def get_thread_messages(thread_id: str, current_user: User = Depends(get_current_user)):
    """Fetch messages for a specific thread."""
    # thread_id format: platform_accountid_realthreadid
    parts = thread_id.split("_", 2)
    if len(parts) != 3:
        raise HTTPException(status_code=400, detail="Invalid thread ID format")
        
    platform, account_id, real_thread_id = parts
    
    # Find the corresponding account to get the token
    acc = next((a for a in current_user.linked_accounts if a.account_id == account_id and a.platform == platform), None)
    if not acc or not acc.access_token_enc:
        raise HTTPException(status_code=404, detail="Connected account not found or missing token")
        
    try:
        page_access_token = decrypt_token(acc.access_token_enc)
        meta_messages = await facebook.get_conversation_messages(real_thread_id, page_access_token)
        
        messages = []
        for msg in meta_messages:
            is_from_me = msg.get("from", {}).get("id") == account_id
            messages.append({
                "id": msg.get("id"),
                "is_from_me": is_from_me,
                "text": msg.get("message", ""),
                "created_at": msg.get("created_time", datetime.now(timezone.utc).isoformat()),
            })
            
        # Meta returns messages newest first usually, we might need to sort them oldest first for UI
        messages.sort(key=lambda x: x["created_at"])
        return {"messages": messages}
    except Exception as e:
        import logging
        logging.error(f"Error fetching messages for thread {real_thread_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching messages from Meta")

@router.post("/threads/{thread_id}/messages")
async def send_message(thread_id: str, payload: Dict[str, Any], current_user: User = Depends(get_current_user)):
    """Send a reply to a specific thread."""
    parts = thread_id.split("_", 2)
    if len(parts) != 3:
        raise HTTPException(status_code=400, detail="Invalid thread ID format")
        
    platform, account_id, real_thread_id = parts
    
    text = payload.get("text")
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
        
    acc = next((a for a in current_user.linked_accounts if a.account_id == account_id and a.platform == platform), None)
    if not acc or not acc.access_token_enc:
        raise HTTPException(status_code=404, detail="Connected account not found or missing token")
        
    try:
        page_access_token = decrypt_token(acc.access_token_enc)
        
        # In Meta Graph API, to reply to a conversation, you POST to /{conversation_id}/messages
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"https://graph.facebook.com/v21.0/{real_thread_id}/messages",
                params={"access_token": page_access_token},
                json={"message": text}
            )
            
            if res.status_code != 200:
                raise Exception(f"Failed to send message: {res.text}")
                
        new_message = {
            "id": f"msg_{uuid.uuid4().hex[:8]}",
            "is_from_me": True,
            "text": text,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        return {"message": new_message}
    except Exception as e:
        import logging
        logging.error(f"Error sending message to thread {real_thread_id}: {e}")
        raise HTTPException(status_code=500, detail="Error sending message")
