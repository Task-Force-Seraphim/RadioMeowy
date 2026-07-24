"""Quantum random number generation with fallback to secrets."""

import json
import secrets
from typing import Optional

import requests

QRNG_ENDPOINTS = [
    "https://api.openquantum.com/v1/qrng",
    "https://qrng.anu.edu.au/API/jsonI.php"
]


def get_random_bytes(num_bytes: int, api_url: Optional[str] = None) -> bytes:
    """
    Fetch quantum randomness from QRNG API.
    Fallback to secrets.token_bytes() if API fails.
    """
    if num_bytes <= 0:
        raise ValueError("Number of bytes must be positive")
    endpoints = [api_url] if api_url else QRNG_ENDPOINTS
    for endpoint in endpoints:
        try:
            resp = requests.get(endpoint, params={"length": num_bytes}, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data:
                    raw = data["data"]
                    if isinstance(raw, str):
                        return bytes.fromhex(raw)
                    elif isinstance(raw, list):
                        return bytes(raw)
                    elif isinstance(raw, bytes):
                        return raw
                elif "random" in data:
                    raw = data["random"]
                    if isinstance(raw, str):
                        return bytes.fromhex(raw)
                elif "result" in data:
                    raw = data["result"]
                    if isinstance(raw, list):
                        return bytes(raw)
        except Exception:
            continue
    return secrets.token_bytes(num_bytes)


def get_nonce(api_url: Optional[str] = None) -> bytes:
    return get_random_bytes(12, api_url)


def get_salt(api_url: Optional[str] = None) -> bytes:
    return get_random_bytes(16, api_url)


def get_aes_key(api_url: Optional[str] = None) -> bytes:
    return get_random_bytes(32, api_url)