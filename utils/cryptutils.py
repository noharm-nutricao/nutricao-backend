"""Utils: Cryptography utilities"""

import base64
from typing import Union

from cryptography.fernet import Fernet

from config import Config
from utils import logger


def encrypt_data(plaintext: str) -> Union[str, None]:
    """Encrypt data using Fernet (symmetric encryption)."""
    if not plaintext:
        return None

    if not Config.ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY not set")

    try:
        fernet = Fernet(Config.ENCRYPTION_KEY.encode())
        encrypted = fernet.encrypt(plaintext.encode("utf-8"))
        return base64.b64encode(encrypted).decode("utf-8")
    except Exception as e:
        logger.backend_logger.error(f"Encryption error: {e}")
        raise ValueError("Erro ao criptografar dados sensíveis")


def decrypt_data(ciphertext: str) -> Union[str, None]:
    """Decrypt data produced by :func:`encrypt_data` (Fernet)."""
    if not ciphertext:
        return None

    if not Config.ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY not set")

    try:
        encr_key: bytes = Config.ENCRYPTION_KEY.encode()
        fernet: Fernet = Fernet(encr_key)
        decoded: bytes = base64.b64decode(ciphertext.encode("utf-8"))
        return fernet.decrypt(decoded).decode("utf-8")
    except Exception as e:
        logger.backend_logger.error(f"Decryption error: {e}")
        raise ValueError("Erro ao descriptografar dados sensíveis")
