"""DTMF tone encoding and decoding (dual-tone multi-frequency)."""

import numpy as np
from typing import Dict, Tuple, List, Optional

DTMF_MAP: Dict[str, Tuple[int, int]] = {
    '1': (697, 1209), '2': (697, 1336), '3': (697, 1477),
    '4': (770, 1209), '5': (770, 1336), '6': (770, 1477),
    '7': (852, 1209), '8': (852, 1336), '9': (852, 1477),
    '*': (941, 1209), '0': (941, 1336), '#': (941, 1477),
    'A': (697, 1633), 'B': (770, 1633), 'C': (852, 1633), 'D': (941, 1633),
}
DTMF_REV = {v: k for k, v in DTMF_MAP.items()}


def encode_dtmf(
    data: bytes,
    sample_rate: int = 44100,
    duration: float = 0.1,
    silence: float = 0.05
) -> np.ndarray:
    """
    Encode bytes as DTMF tones.
    Each byte is represented as two hex nibbles, each nibble -> one DTMF symbol.
    A short silence is inserted between symbols to aid decoding.
    """
    if duration <= 0 or silence < 0:
        raise ValueError("Duration and silence must be non‑negative")
    hex_str = data.hex().upper()
    symbols = list(hex_str)

    tone_samples = int(sample_rate * duration)
    silence_samples = int(sample_rate * silence)
    t = np.arange(tone_samples) / sample_rate

    audio = []
    for sym in symbols:
        if sym not in DTMF_MAP:
            raise ValueError(f"Invalid hex symbol: {sym}")
        low_freq, high_freq = DTMF_MAP[sym]
        tone = np.sin(2 * np.pi * low_freq * t) + np.sin(2 * np.pi * high_freq * t)
        tone = tone / 2.0
        audio.append(tone)
        if silence_samples > 0:
            audio.append(np.zeros(silence_samples, dtype=np.float32))
    return np.concatenate(audio).astype(np.float32)


def decode_dtmf(audio: np.ndarray, sample_rate: int = 44100) -> bytes:
    """
    Decode DTMF tones back to bytes.
    Uses Goertzel algorithm with tone pair detection, duration validation,
    and inter‑digit silence detection.
    """
    if len(audio) == 0:
        return b""

    freqs = [697, 770, 852, 941, 1209, 1336, 1477, 1633]
    low_freqs = [f for f in freqs if f < 1000]
    high_freqs = [f for f in freqs if f >= 1209]

    win_len = int(sample_rate * 0.03)
    step = int(sample_rate * 0.01)
    if win_len < 1:
        win_len = int(sample_rate * 0.005)
        step = win_len // 2

    rms = np.sqrt(np.mean(audio ** 2))
    threshold = 0.01 if rms < 0.001 else 0.1 * rms

    def _goertzel(samples, target_freq):
        n = len(samples)
        if n == 0:
            return 0.0
        coeff = 2.0 * np.cos(2.0 * np.pi * target_freq / sample_rate)
        q0 = 0.0
        q1 = 0.0
        for s in samples:
            q2 = q1
            q1 = q0
            q0 = coeff * q1 - q2 + s
        real = q0 - q1 * np.cos(2.0 * np.pi * target_freq / sample_rate)
        imag = q1 * np.sin(2.0 * np.pi * target_freq / sample_rate)
        return real*real + imag*imag

    symbols = []
    i = 0
    while i + win_len <= len(audio):
        seg = audio[i:i+win_len]
        energies = {f: _goertzel(seg, f) for f in freqs}
        low_energy = {f: energies[f] for f in low_freqs}
        high_energy = {f: energies[f] for f in high_freqs}
        max_low = max(low_energy, key=low_energy.get)
        max_high = max(high_energy, key=high_energy.get)
        if low_energy[max_low] > threshold and high_energy[max_high] > threshold:
            symbol = DTMF_REV.get((max_low, max_high))
            if symbol is not None:
                symbols.append((i, symbol))
                i += int(sample_rate * 0.1)
                continue
        i += step

    filtered = []
    for pos, sym in symbols:
        if not filtered or (pos - filtered[-1][0]) > int(sample_rate * 0.05):
            filtered.append((pos, sym))
        else:
            if filtered[-1][1] == sym:
                continue
            else:
                filtered.append((pos, sym))

    symbol_sequence = [sym for _, sym in filtered]

    hex_str = ''.join(symbol_sequence)
    hex_str = ''.join(c for c in hex_str if c in '0123456789ABCDEF')
    if len(hex_str) % 2 != 0:
        hex_str = hex_str[:-1]
    if not hex_str:
        return b""
    return bytes.fromhex(hex_str)