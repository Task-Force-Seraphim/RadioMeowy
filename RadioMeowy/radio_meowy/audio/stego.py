"""LSB steganography with lossless carrier warning and writable arrays."""

import os
import struct
import wave
import numpy as np
from pathlib import Path
from radio_meowy.audio.utils import load_audio, save_audio

SYNC_HEADER = b'MEOW'
SYNC_LEN = len(SYNC_HEADER)
LEN_PREFIX_SIZE = 4


def encode_lsb(
    audio_path: Path,
    data: bytes,
    output_path: Path,
    bit_depth: int = 16
) -> None:
    if not audio_path.exists():
        raise FileNotFoundError(f"Carrier audio not found: {audio_path}")
    if bit_depth not in (8, 16):
        raise ValueError("Only 8-bit and 16-bit PCM are supported")
    if not data:
        raise ValueError("Data to embed cannot be empty")

    if audio_path.suffix.lower() == '.mp3':
        print("[WARNING] MP3 is lossy by the way. LSB steganography may not survive. Use WAV or FLAC for reliable results.")

    # Load carrier
    if audio_path.suffix.lower() == '.wav':
        with wave.open(str(audio_path), 'rb') as wav:
            params = wav.getparams()
            nchannels, sampwidth, nframes = params[0], params[1], params[3]
            if sampwidth != bit_depth // 8:
                raise ValueError(f"Sample width mismatch: expected {bit_depth//8} bytes, got {sampwidth}")
            frames = wav.readframes(nframes)
        dtype = np.uint8 if bit_depth == 8 else np.int16
        samples_int = np.frombuffer(frames, dtype=dtype).copy()  # make writable
        if nchannels > 1:
            samples_int = samples_int.reshape(-1, nchannels)[:, 0].copy()
    else:
        # For non-WAV, use load_audio (float) then convert
        samples_float, sample_rate = load_audio(audio_path, return_sample_rate=True)
        if bit_depth == 16:
            samples_int = np.round(samples_float * 32767).astype(np.int16)
        else:
            samples_int = np.round((samples_float + 1.0) * 127.5 - 128).astype(np.int8)
        sample_rate = sample_rate  # for saving

    payload = SYNC_HEADER + struct.pack(">I", len(data)) + data
    bits = []
    for byte in payload:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)

    if len(bits) > len(samples_int):
        raise ValueError(
            f"Data too large: need {len(bits)} bits, carrier provides {len(samples_int)} bits"
        )

    for i, bit in enumerate(bits):
        samples_int[i] = (samples_int[i] & ~1) | bit

    # Save output (always WAV)
    if audio_path.suffix.lower() == '.wav':
        # Reconstruct with original parameters
        with wave.open(str(audio_path), 'rb') as wav_orig:
            orig_params = wav_orig.getparams()
            orig_nchannels = orig_params[0]
            orig_sampwidth = orig_params[1]
            orig_frames = wav_orig.readframes(wav_orig.getnframes())
        # Restore other channels if stereo
        if orig_nchannels > 1:
            samples_orig = np.frombuffer(orig_frames, dtype=dtype).reshape(-1, orig_nchannels).copy()
            samples_orig[:, 0] = samples_int
            out_samples = samples_orig.reshape(-1)
        else:
            out_samples = samples_int
        with wave.open(str(output_path), 'wb') as out_wav:
            out_wav.setparams(orig_params)
            out_wav.writeframes(out_samples.tobytes())
    else:
        # Convert back to float and save
        max_val = 32767 if bit_depth == 16 else 127
        samples_float = samples_int.astype(np.float32) / max_val
        samples_float = np.clip(samples_float, -1.0, 1.0)
        save_audio(samples_float, output_path, sample_rate)


def decode_lsb(audio_path: Path, bit_depth: int = 16) -> bytes:
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    if bit_depth not in (8, 16):
        raise ValueError("Only 8-bit and 16-bit PCM are supported")

    if audio_path.suffix.lower() == '.wav':
        with wave.open(str(audio_path), 'rb') as wav:
            params = wav.getparams()
            nchannels, sampwidth, nframes = params[0], params[1], params[3]
            if sampwidth != bit_depth // 8:
                raise ValueError(f"Sample width mismatch: expected {bit_depth//8} bytes, got {sampwidth}")
            frames = wav.readframes(nframes)
        dtype = np.uint8 if bit_depth == 8 else np.int16
        samples_int = np.frombuffer(frames, dtype=dtype).copy()
        if nchannels > 1:
            samples_int = samples_int.reshape(-1, nchannels)[:, 0].copy()
    else:
        samples_float, _ = load_audio(audio_path, return_sample_rate=True)
        if bit_depth == 16:
            samples_int = np.round(samples_float * 32767).astype(np.int16)
        else:
            samples_int = np.round((samples_float + 1.0) * 127.5 - 128).astype(np.int8)

    bits = []
    for sample in samples_int:
        bits.append(sample & 1)

    data_bytes = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            if i + j < len(bits):
                byte = (byte << 1) | bits[i + j]
        data_bytes.append(byte)

    if os.getenv('RADIOMEOWY_DEBUG'):
        print(f"[DEBUG] Extracted first 32 bytes: {data_bytes[:32].hex()}")
        sync_pos = data_bytes.find(SYNC_HEADER)
        print(f"[DEBUG] Sync header position: {sync_pos}")

    sync_pos = data_bytes.find(SYNC_HEADER)
    if sync_pos == -1:
        raise ValueError("Sync header 'MEOW' not found in extracted data")
    if len(data_bytes) < sync_pos + SYNC_LEN + LEN_PREFIX_SIZE:
        raise ValueError("Payload too short for header")
    data_len = struct.unpack(">I", data_bytes[sync_pos+SYNC_LEN:sync_pos+SYNC_LEN+LEN_PREFIX_SIZE])[0]
    start = sync_pos + SYNC_LEN + LEN_PREFIX_SIZE
    if len(data_bytes) < start + data_len:
        raise ValueError(f"Data truncated: expected {data_len} bytes, got {len(data_bytes)-start}")
    return bytes(data_bytes[start:start+data_len])