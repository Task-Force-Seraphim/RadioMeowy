"""Reed‑Solomon error correction with length prefix using unireedsolomon."""

import struct
from typing import Tuple
from unireedsolomon import RSCoder

RS = RSCoder(255, 223)          # RS(255, 223), corrects up to 16 errors
BLOCK_SIZE_DATA = 223
BLOCK_SIZE_ENCODED = 255
LEN_PREFIX_SIZE = 4


def encode_reedsolomon(data: bytes) -> bytes:
    if not data:
        return b''
    payload = struct.pack(">I", len(data)) + data
    blocks = []
    for i in range(0, len(payload), BLOCK_SIZE_DATA):
        block = payload[i:i + BLOCK_SIZE_DATA]
        if len(block) < BLOCK_SIZE_DATA:
            block += b'\x00' * (BLOCK_SIZE_DATA - len(block))
        encoded = RS.encode(block)
        # unireedsolomon may return str; ensure bytes
        if isinstance(encoded, str):
            encoded = encoded.encode('latin-1')
        blocks.append(encoded)
    return b''.join(blocks)


def decode_reedsolomon(data: bytes) -> Tuple[bytes, bool]:
    if not data:
        return b'', True

    if len(data) % BLOCK_SIZE_ENCODED != 0:
        pad_len = BLOCK_SIZE_ENCODED - (len(data) % BLOCK_SIZE_ENCODED)
        data += b'\x00' * pad_len

    decoded_blocks = []
    success = True

    for i in range(0, len(data), BLOCK_SIZE_ENCODED):
        block = data[i:i + BLOCK_SIZE_ENCODED]
        try:
            decoded, _ = RS.decode(block)
            # decode may return str; ensure bytes
            if isinstance(decoded, str):
                decoded = decoded.encode('latin-1')
            decoded_blocks.append(decoded)
        except Exception:
            # Fallback: take the first 223 bytes (the original message part)
            decoded_blocks.append(block[:BLOCK_SIZE_DATA])
            success = False

    full = b''.join(decoded_blocks)

    if len(full) < LEN_PREFIX_SIZE:
        raise ValueError("Decoded data too short for length prefix")

    orig_len = struct.unpack(">I", full[:LEN_PREFIX_SIZE])[0]
    if orig_len > len(full) - LEN_PREFIX_SIZE:
        raise ValueError(f"Length prefix {orig_len} exceeds available data")

    return full[LEN_PREFIX_SIZE:LEN_PREFIX_SIZE + orig_len], success