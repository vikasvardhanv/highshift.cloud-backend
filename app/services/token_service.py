import os
from cryptography.fernet import Fernet
from app.utils.logger import logger

# Encryption key should be in .env
ENCRYPTION_KEY = os.getenv("TOKEN_ENCRYPTION_KEY")

def get_fernet():
    if not ENCRYPTION_KEY:
        # Fallback to a consistent key for development/serverless if env var is missing
        # This prevents "Invalid Token" errors when instances restart
        # Key below is a valid Fernet key (32 url-safe base64-encoded bytes)
        logger.warning("TOKEN_ENCRYPTION_KEY missing. Using fallback DEV key.")
        return Fernet(b'C9W_dF7k-U7f_7o8E3r2q1w4e5r6t7y8u9i0o1p2a3s=')
    return Fernet(ENCRYPTION_KEY.encode())

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
