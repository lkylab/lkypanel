from django.conf import settings
from cryptography.fernet import Fernet

def _fernet() -> Fernet:
    key = settings.FERNET_KEY
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)

def encrypt_data(plaintext: str) -> bytes:
    if not plaintext:
        return b""
    return _fernet().encrypt(plaintext.encode())

def decrypt_data(ciphertext: bytes) -> str:
    if not ciphertext:
        return ""
    return _fernet().decrypt(ciphertext).decode()
