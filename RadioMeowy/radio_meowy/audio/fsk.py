"""Frequency-Shift Keying (FSK) modulation for binary data."""

import numpy as np
from typing import Tuple


def encode_fsk(
    data: bytes,
    bitrate: int = 300,
    sample_rate: int = 44100,
    freq0: int = 1000,
    freq1: int = 2000
) -> np.ndarray:
    """
    Encode binary data as Frequency-Shift Keying audio.
    bit 0 = freq0, bit 1 = freq1.
    Returns numpy array of float in [-1, 1].
    """
    if bitrate <= 0 or sample_rate <= 0:
        raise ValueError("Bitrate and sample rate must be positive")
    # Generate time for each bit
    samples_per_bit = int(sample_rate / bitrate)
    total_samples = len(data) * 8 * samples_per_bit
    audio = np.zeros(total_samples, dtype=np.float32)
    t = np.arange(samples_per_bit) / sample_rate
    for byte_idx, byte in enumerate(data):
        for bit_idx in range(8):
            bit = (byte >> (7 - bit_idx)) & 1
            freq = freq1 if bit else freq0
            segment = np.sin(2 * np.pi * freq * t)
            start = (byte_idx * 8 + bit_idx) * samples_per_bit
            audio[start:start + samples_per_bit] = segment
    return audio


def decode_fsk(
    audio: np.ndarray,
    bitrate: int = 300,
    sample_rate: int = 44100,
    freq0: int = 1000,
    freq1: int = 2000
) -> bytes:
    """
    Decode FSK audio back to binary data.
    Uses Goertzel algorithm for frequency detection.
    """
    if bitrate <= 0 or sample_rate <= 0:
        raise ValueError("Bitrate and sample rate must be positive")
    samples_per_bit = int(sample_rate / bitrate)
    if len(audio) < samples_per_bit:
        return b""
    # Compute number of bits
    n_bits = len(audio) // samples_per_bit
    # decode bits
    bits = []
    for i in range(n_bits):
        segment = audio[i * samples_per_bit:(i + 1) * samples_per_bit]
        # Goertzel for both frequencies
        energy0 = _goertzel(segment, freq0, sample_rate)
        energy1 = _goertzel(segment, freq1, sample_rate)
        bit = 1 if energy1 > energy0 else 0
        bits.append(bit)
    # Group bits into bytes
    bytes_out = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            if i + j < len(bits):
                byte = (byte << 1) | bits[i + j]
        bytes_out.append(byte)
    return bytes(bytes_out)


def _goertzel(samples: np.ndarray, target_freq: float, sample_rate: float) -> float:
    """
    Goertzel algorithm to compute energy at target frequency.
    """
    n = len(samples)
    if n == 0:
        return 0.0
    coeff = 2.0 * np.cos(2.0 * np.pi * target_freq / sample_rate)
    q0 = 0.0
    q1 = 0.0
    for sample in samples:
        q2 = q1
        q1 = q0
        q0 = coeff * q1 - q2 + sample
    real = q0 - q1 * np.cos(2.0 * np.pi * target_freq / sample_rate)
    imag = q1 * np.sin(2.0 * np.pi * target_freq / sample_rate)
    return real * real + imag * imag