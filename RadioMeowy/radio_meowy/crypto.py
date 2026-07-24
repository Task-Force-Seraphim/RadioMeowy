"""Cryptographic primitives: AES-256-GCM and Argon2id KDF."""

from typing import Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.backends import default_backend


def encrypt_aes_gcm(key: bytes, plaintext: bytes, nonce: bytes) -> Tuple[bytes, bytes]:
    """
    Encrypt plaintext with AES-256-GCM.
    Returns (ciphertext, auth_tag).
    """
    if len(key) != 32:
        raise ValueError("Key must be 32 bytes for AES-256")
    if len(nonce) != 12:
        raise ValueError("Nonce must be 12 bytes for AES-GCM")
    aesgcm = AESGCM(key)
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, None)
    # Split: first len(plaintext) bytes are ciphertext, last 16 are tag
    ciphertext = ciphertext_with_tag[:-16]
    auth_tag = ciphertext_with_tag[-16:]
    return ciphertext, auth_tag


def decrypt_aes_gcm(key: bytes, ciphertext: bytes, nonce: bytes, auth_tag: bytes) -> bytes:
    """
    Decrypt AES-256-GCM ciphertext with authentication.
    """
    if len(key) != 32:
        raise ValueError("Key must be 32 bytes for AES-256")
    if len(nonce) != 12:
        raise ValueError("Nonce must be 12 bytes for AES-GCM")
    if len(auth_tag) != 16:
        raise ValueError("Auth tag must be 16 bytes")
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext + auth_tag, None)
    return plaintext


def derive_key_argon2(
    fingerprint: str,
    salt: bytes,
    memory_cost: int = 65536,
    time_cost: int = 3,
    parallelism: int = 4
) -> bytes:
    """
    Derive a 32-byte key using Argon2id from a PGP fingerprint and salt.
    """
    if len(salt) != 16:
        raise ValueError("Salt must be 16 bytes")
    kdf = Argon2id(
        salt=salt,
        length=32,
        memory_cost=memory_cost,
        time_cost=time_cost,
        parallelism=parallelism,
        backend=default_backend()
    )
    return kdf.derive(fingerprint.encode("utf-8"))