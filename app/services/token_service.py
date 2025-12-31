import os
from cryptography.fernet import Fernet
from app.utils.logger import logger

# Encryption key should be in .env
ENCRYPTION_KEY = os.getenv("TOKEN_ENCRYPTION_KEY")

def get_fernet():
    if not ENCRYPTION_KEY:
        # For development, generate a key if missing (NOT FOR PRODUCTION)
        logger.warning("TOKEN_ENCRYPTION_KEY missing. Using a temporary key.")
        return Fernet(Fernet.generate_key())
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
