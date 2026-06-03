"""Testes do round-trip de cifragem (issue #88)."""

from cryptography.fernet import Fernet

from config import Config
from utils import cryptutils


def test_encrypt_decrypt_round_trip(monkeypatch) -> None:
    monkeypatch.setattr(Config, "ENCRYPTION_KEY", Fernet.generate_key().decode())

    plaintext = "token-secreto-123"
    ciphertext = cryptutils.encrypt_data(plaintext)

    assert ciphertext != plaintext
    assert cryptutils.decrypt_data(ciphertext) == plaintext


def test_encrypt_decrypt_empty_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(Config, "ENCRYPTION_KEY", Fernet.generate_key().decode())

    assert cryptutils.encrypt_data("") is None
    assert cryptutils.decrypt_data("") is None
