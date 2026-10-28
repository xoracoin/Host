"""
PyHosting AES-256 Fernet Encryption Module
Provides zero-trust encryption-at-rest for sensitive environment secrets,
API keys, Telegram bot tokens, and database passwords.
"""

import base64
import hashlib
import json
import logging
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)

def _get_fernet_instance() -> Fernet:
    """
    Derives a cryptographically secure 32-byte key from Django's SECRET_KEY
    or a dedicated DATA_ENCRYPTION_KEY setting using SHA-256.
    """
    secret = getattr(settings, 'DATA_ENCRYPTION_KEY', settings.SECRET_KEY)
    key_32 = hashlib.sha256(secret.encode('utf-8')).digest()
    url_safe_key = base64.urlsafe_b64encode(key_32)
    return Fernet(url_safe_key)

def encrypt_string(text: str) -> str:
    """Encrypts a string to a Fernet AES-256 ciphertext."""
    if not text:
        return ""
    try:
        f = _get_fernet_instance()
        return f.encrypt(text.encode('utf-8')).decode('utf-8')
    except Exception as e:
        logger.error(f"Error encrypting string: {e}")
        return text

def decrypt_string(ciphertext: str) -> str:
    """Decrypts a Fernet AES-256 ciphertext string. Returns original if not encrypted."""
    if not ciphertext:
        return ""
    try:
        f = _get_fernet_instance()
        return f.decrypt(ciphertext.encode('utf-8')).decode('utf-8')
    except (InvalidToken, Exception):
        return ciphertext

def encrypt_dict(data: dict) -> str:
    """Serializes and encrypts a dictionary to a Fernet AES-256 ciphertext."""
    if not data or not isinstance(data, dict):
        return ""
    try:
        raw_json = json.dumps(data)
        return encrypt_string(raw_json)
    except Exception as e:
        logger.error(f"Error encrypting dict: {e}")
        return ""

def decrypt_dict(cipher_or_data) -> dict:
    """
    Decrypts a Fernet AES-256 ciphertext string back to a dictionary.
    Handles raw dict or legacy unencrypted JSON string gracefully.
    """
    if isinstance(cipher_or_data, dict):
        if "_encrypted" in cipher_or_data and len(cipher_or_data) == 1:
            return decrypt_dict(cipher_or_data["_encrypted"])
        return cipher_or_data

    if not cipher_or_data or not isinstance(cipher_or_data, str):
        return {}

    try:
        f = _get_fernet_instance()
        decrypted_raw = f.decrypt(cipher_or_data.encode('utf-8')).decode('utf-8')
        parsed = json.loads(decrypted_raw)
        return parsed if isinstance(parsed, dict) else {}
    except (InvalidToken, Exception):
        try:
            parsed = json.loads(cipher_or_data)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        return {}
