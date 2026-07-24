"""PGP operations using python-gnupg with ECC (Ed25519/Curve25519)."""

import gnupg
from pathlib import Path
from typing import Optional

gpg = gnupg.GPG()


def import_public_key(key_path: Path) -> str:
    if not key_path.exists():
        raise FileNotFoundError(f"Public key file not found: {key_path}")
    with open(key_path, "rb") as f:
        key_data = f.read().decode()
    import_result = gpg.import_keys(key_data)
    if not import_result.fingerprints:
        raise ValueError("No public key imported. Check file format.")
    return import_result.fingerprints[0]


def import_secret_key(key_path: Path, passphrase: Optional[str] = None) -> str:
    if not key_path.exists():
        raise FileNotFoundError(f"Secret key file not found: {key_path}")
    with open(key_path, "rb") as f:
        key_data = f.read().decode()
    if passphrase:
        gpg.passphrase = passphrase
    import_result = gpg.import_keys(key_data)
    if not import_result.fingerprints:
        raise ValueError("No secret key imported. Check file format.")
    return import_result.fingerprints[0]


def encrypt_to_fingerprint(data: bytes, fingerprint: str) -> bytes:
    if not fingerprint:
        raise ValueError("Fingerprint must not be empty")
    encrypted = gpg.encrypt(
        data,
        fingerprint,
        always_trust=True,
        armor=False,
        extra_args=["--compress-algo", "none"]
    )
    if not encrypted.ok:
        raise RuntimeError(f"PGP encryption failed: {encrypted.stderr}")
    return encrypted.data


def decrypt_with_secret_key(
    encrypted_data: bytes,
    passphrase: Optional[str] = None
) -> bytes:
    """
    Decrypt PGP-encrypted data using the keyring (no file import needed).
    The passphrase is used to unlock the secret key.
    """
    if passphrase:
        gpg.passphrase = passphrase
    decrypted = gpg.decrypt(
        encrypted_data,
        always_trust=True,
        extra_args=["--compress-algo", "none"]
    )
    if not decrypted.ok:
        raise RuntimeError(f"PGP decryption failed: {decrypted.stderr}")
    return decrypted.data


def generate_challenge() -> str:
    import secrets
    return secrets.token_hex(32)


def sign_challenge(
    challenge: str,
    fingerprint: str,
    passphrase: Optional[str] = None
) -> str:
    if passphrase:
        gpg.passphrase = passphrase
    signed = gpg.sign(challenge, keyid=fingerprint, detach=True)
    if not signed:
        raise RuntimeError("Signing failed")
    return signed.data.decode()


def verify_signature(challenge: str, signature: str, fingerprint: str) -> bool:
    verified = gpg.verify(signature.encode(), data=challenge.encode())
    if not verified:
        return False
    return verified.fingerprint == fingerprint


def get_fingerprint(key_path: Path) -> str:
    if not key_path.exists():
        raise FileNotFoundError(f"Key file not found: {key_path}")
    with open(key_path, "rb") as f:
        key_data = f.read().decode()
    imported = gpg.import_keys(key_data)
    if not imported.fingerprints:
        raise ValueError("No key found in file")
    return imported.fingerprints[0]