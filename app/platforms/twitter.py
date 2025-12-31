import httpx
import hashlib
import base64
import os
from app.utils.logger import logger

def generate_pkce_pair():
    """Generate code verifier and challenge for PKCE."""
    code_verifier = base64.urlsafe_b64encode(os.urandom(30)).decode("utf-8").replace("=", "")
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).decode("utf-8").replace("=", "")
    return code_verifier, code_challenge

async def get_auth_url(client_id: str, redirect_uri: str, state: str, scopes: list, code_challenge: str):
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
        "scope": " ".join(scopes),
        "code_challenge": code_challenge,
        "code_challenge_method": "S256"
    }
    encoded_params = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"https://twitter.com/i/oauth2/authorize?{encoded_params}"

async def exchange_code(client_id: str, client_secret: str, redirect_uri: str, code: str, code_verifier: str):
    async with httpx.AsyncClient() as client:
        auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        res = await client.post(
            "https://api.twitter.com/2/oauth2/token",
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "client_id": client_id,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "code": code,
                "code_verifier": code_verifier
            }
        )
        res.raise_for_status()
        return res.json()

async def post_tweet(access_token: str, text: str):
    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://api.twitter.com/2/tweets",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json={"text": text}
        )
        res.raise_for_status()
        return res.json()
