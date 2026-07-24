"""Binary payload construction and parsing for RadioMeowy."""

import struct
from typing import Dict

MAGIC = b'MEOW'
VERSION = b'\x01'


def build_payload(
    salt: bytes,
    nonce: bytes,
    wrapped_key: bytes,
    ciphertext: bytes,
    auth_tag: bytes
) -> bytes:
    """
    Build binary payload:
    MAGIC (4) + VERSION (1) + SALT (16) + NONCE (12) + WRAPPED_KEY_LEN (2) + WRAPPED_KEY + CIPHERTEXT + AUTH_TAG (16)
    """
    if len(salt) != 16:
        raise ValueError("Salt must be 16 bytes")
    if len(nonce) != 12:
        raise ValueError("Nonce must be 12 bytes")
    if len(auth_tag) != 16:
        raise ValueError("Auth tag must be 16 bytes")
    if len(wrapped_key) > 65535:
        raise ValueError("Wrapped key too large")
    payload = MAGIC + VERSION + salt + nonce
    payload += struct.pack(">H", len(wrapped_key))
    payload += wrapped_key
    payload += ciphertext
    payload += auth_tag
    return payload


def parse_payload(data: bytes) -> Dict[str, bytes]:
    """
    Parse binary payload.
    Returns dict with keys: magic, version, salt, nonce, wrapped_key, ciphertext, auth_tag.
    """
    if len(data) < 4 + 1 + 16 + 12 + 2:
        raise ValueError("Payload too short")
    offset = 0
    magic = data[offset:offset+4]
    offset += 4
    if magic != MAGIC:
        raise ValueError("Invalid magic bytes")
    version = data[offset:offset+1]
    offset += 1
    # version not used currently
    salt = data[offset:offset+16]
    offset += 16
    nonce = data[offset:offset+12]
    offset += 12
    if len(data) < offset + 2:
        raise ValueError("Payload missing wrapped key length")
    wrapped_key_len = struct.unpack(">H", data[offset:offset+2])[0]
    offset += 2
    if len(data) < offset + wrapped_key_len + 16:
        raise ValueError("Payload missing data or auth tag")
    wrapped_key = data[offset:offset+wrapped_key_len]
    offset += wrapped_key_len
    ciphertext = data[offset:-16]
    auth_tag = data[-16:]
    return {
        "magic": magic,
        "version": version,
        "salt": salt,
        "nonce": nonce,
        "wrapped_key": wrapped_key,
        "ciphertext": ciphertext,
        "auth_tag": auth_tag
    }