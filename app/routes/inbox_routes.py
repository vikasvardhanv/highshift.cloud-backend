from typing import Any, Dict, List
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from app.utils.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/inbox", tags=["Inbox"])

# In-memory store for demonstration purposes
MOCK_THREADS = [
    {
        "id": "thread_1",
        "account_id": "mock_acc_1",
        "platform": "facebook",
        "sender_name": "Alice Johnson",
        "sender_avatar": "https://ui-avatars.com/api/?name=Alice+Johnson&background=random",
        "snippet": "Hey! I have a question about your pricing plans.",
        "is_read": False,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "thread_2",
        "account_id": "mock_acc_2",
        "platform": "instagram",
        "sender_name": "bob_builder",
        "sender_avatar": "https://ui-avatars.com/api/?name=bob+builder&background=random",
        "snippet": "Love the new feature you just announced 🔥",
        "is_read": True,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    },
]

MOCK_MESSAGES = {
    "thread_1": [
        {
            "id": "msg_1",
            "is_from_me": False,
            "text": "Hi there! I saw your ad.",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "id": "msg_2",
            "is_from_me": False,
            "text": "Hey! I have a question about your pricing plans.",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ],
    "thread_2": [
        {
            "id": "msg_3",
            "is_from_me": False,
            "text": "Love the new feature you just announced 🔥",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
}

@router.get("/threads")
async def get_threads(current_user: User = Depends(get_current_user)):
    """Fetch all inbox threads for the connected accounts."""
    # In a real integration, we would filter by the user's connected account_ids
    return {"threads": MOCK_THREADS}

@router.get("/threads/{thread_id}/messages")
async def get_thread_messages(thread_id: str, current_user: User = Depends(get_current_user)):
    """Fetch messages for a specific thread."""
    if thread_id not in MOCK_MESSAGES:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    # Mark thread as read
    for t in MOCK_THREADS:
        if t["id"] == thread_id:
            t["is_read"] = True
            
    return {"messages": MOCK_MESSAGES[thread_id]}

@router.post("/threads/{thread_id}/messages")
async def send_message(thread_id: str, payload: Dict[str, Any], current_user: User = Depends(get_current_user)):
    """Send a reply to a specific thread."""
    if thread_id not in MOCK_MESSAGES:
        raise HTTPException(status_code=404, detail="Thread not found")
        
    text = payload.get("text")
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
        
    new_message = {
        "id": f"msg_{uuid.uuid4().hex[:8]}",
        "is_from_me": True,
        "text": text,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    
    MOCK_MESSAGES[thread_id].append(new_message)
    
    # Update thread snippet and time
    for t in MOCK_THREADS:
        if t["id"] == thread_id:
            t["snippet"] = text
            t["updated_at"] = datetime.now(timezone.utc).isoformat()
            t["is_read"] = True
            
    return {"message": new_message}
