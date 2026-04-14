import os
import base64
import hashlib
from cryptography.fernet import Fernet
from app.utils.logger import logger

def get_fernet():
    """
    Use explicit TOKEN_ENCRYPTION_KEY when provided.
    Otherwise derive a stable Fernet key from JWT_SECRET as a safer fallback.
    """
    configured = os.getenv("TOKEN_ENCRYPTION_KEY")
    if configured:
        return Fernet(configured.encode())

    fallback_secret = os.getenv("JWT_SECRET", "highshift-dev-only-secret")
    digest = hashlib.sha256(fallback_secret.encode()).digest()
    derived_key = base64.urlsafe_b64encode(digest)
    logger.warning(
        "TOKEN_ENCRYPTION_KEY missing. Deriving encryption key from JWT_SECRET fallback."
    )
    return Fernet(derived_key)

def encrypt_token(token: str) -> str:
    """Encrypt a plain text token."""
    f = get_fernet()
    return f.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    """Decrypt an encrypted token."""
    f = get_fernet()
    return f.decrypt(encrypted_token.encode()).decode()

async def ensure_valid_access_token(user_id: str, linked_account_id: str):
    """
    (To be implemented) Logic to check expiry and refresh if needed.
    """
    # Placeholder for now
    pass
