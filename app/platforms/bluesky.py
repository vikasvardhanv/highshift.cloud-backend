import httpx
from datetime import datetime
from app.utils.logger import logger

# Bluesky / AT Protocol
# Using direct XRPC calls to avoid heavy dependencies for now.
# Endpoint: https://bsky.social/xrpc/...

BSKY_SERVER = "https://bsky.social"

async def login(identifier: str, password: str):
    """
    Create a session. Identifier can be handle or email.
    Password should be an App Password if 2FA is on.
    """
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{BSKY_SERVER}/xrpc/com.atproto.server.createSession",
            json={
                "identifier": identifier,
                "password": password
            }
        )
        res.raise_for_status()
        return res.json()

async def create_record(access_token: str, did: str, text: str):
    """
    Post a status update (feed item).
    """
    import datetime
    
    # We need strictly formatted ISO string "1985-04-12T23:20:50.52Z"
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"
    
    record = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": now_iso
    }
    
    payload = {
        "repo": did,
        "collection": "app.bsky.feed.post",
        "record": record
    }
    
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{BSKY_SERVER}/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {access_token}"},
            json=payload
        )
        res.raise_for_status()
        return res.json()

async def get_profile(access_token: str, actor: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{BSKY_SERVER}/xrpc/app.bsky.actor.getProfile",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"actor": actor}
        )
        res.raise_for_status()
        return res.json()
