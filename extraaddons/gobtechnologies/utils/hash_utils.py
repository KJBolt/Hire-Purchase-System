import hashlib
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def generate_key():
    """Generate a key for encryption"""
    salt = b'gobtechnologies'  # In production, use a secure random salt
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(b'odoo'))  # In production, use a secure secret
    return key

def encrypt_text(text):
    """Encrypt text using Fernet"""
    if not text:
        return ''
    try:
        key = generate_key()
        f = Fernet(key)
        return base64.urlsafe_b64encode(f.encrypt(text.encode())).decode()
    except Exception:
        return ''

def decrypt_text(encrypted_text):
    """Decrypt text using Fernet"""
    if not encrypted_text:
        return ''
    try:
        key = generate_key()
        f = Fernet(key)
        decoded = base64.urlsafe_b64decode(encrypted_text.encode())
        return f.decrypt(decoded).decode()
    except Exception:
        return ''