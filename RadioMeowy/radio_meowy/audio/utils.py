"""Audio utilities: loading, saving, sync tones, normalization, resampling."""

import subprocess
import io
import numpy as np
import soundfile as sf
import scipy.signal
from pathlib import Path
from typing import Optional, Tuple, Union


def _decode_mp3_with_ffmpeg(path: Path) -> Tuple[np.ndarray, int]:
    """Use ffmpeg to decode MP3 to WAV and return (samples, sample_rate)."""
    cmd = ["ffmpeg", "-i", str(path), "-f", "wav", "-"]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found. Please install ffmpeg to load MP3 files.")
    wav_data, _ = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg decoding failed for {path}")
    with io.BytesIO(wav_data) as f:
        data, sr = sf.read(f)
    return data, sr


def load_audio(
    path: Path,
    sample_rate: Optional[int] = None,
    return_sample_rate: bool = False
) -> Union[np.ndarray, Tuple[np.ndarray, int]]:
    """
    Load audio file (WAV, FLAC, AIFF, MP3) and return as mono float32 array in [-1,1].
    Resamples if sample_rate is specified.
    If return_sample_rate is True, returns (array, sample_rate).
    """
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")
    ext = path.suffix.lower()

    if ext in ('.wav', '.flac', '.aiff'):
        data, sr = sf.read(str(path))
    elif ext == '.mp3':
        data, sr = _decode_mp3_with_ffmpeg(path)
    else:
        raise ValueError(f"Unsupported audio format: {ext}")

    if data.ndim > 1:
        data = data.mean(axis=1)

    data = data.astype(np.float32)
    peak = np.max(np.abs(data))
    if peak > 1.0:
        data = data / peak
    data = np.clip(data, -1.0, 1.0)

    if sample_rate is not None and sr != sample_rate:
        new_length = int(len(data) * sample_rate / sr)
        data = scipy.signal.resample(data, new_length)
        data = data.astype(np.float32)
        sr = sample_rate

    if return_sample_rate:
        return data, sr
    return data


def save_audio(audio: np.ndarray, path: Path, sample_rate: int) -> None:
    """Save mono float32 audio as WAV (PCM_16)."""
    audio = audio.astype(np.float32)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    audio = np.clip(audio, -1.0, 1.0)
    sf.write(str(path), audio, sample_rate, subtype='PCM_16')


def add_sync_tones(audio: np.ndarray, sample_rate: int, freq: int = 1800, duration: float = 0.5) -> np.ndarray:
    n_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False)
    tone = np.sin(2 * np.pi * freq * t).astype(np.float32)
    fade_len = int(min(0.01 * sample_rate, n_samples * 0.1))
    if fade_len > 0:
        tone[:fade_len] *= np.linspace(0, 1, fade_len)
        tone[-fade_len:] *= np.linspace(1, 0, fade_len)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    return np.concatenate([tone, audio, tone])


def detect_sync_tones(audio: np.ndarray, sample_rate: int, freq: int = 1800, threshold: float = 0.5) -> Tuple[int, int]:
    if len(audio) == 0:
        return 0, 0
    win_len = int(sample_rate * 0.1)
    if win_len > len(audio):
        return 0, len(audio)
    t = np.arange(win_len) / sample_rate
    ref = np.sin(2 * np.pi * freq * t)
    corr = np.abs(np.correlate(audio, ref, mode='valid'))
    max_corr = np.max(corr)
    if max_corr < 1e-6:
        return 0, len(audio)
    threshold_abs = threshold * max_corr
    above = np.where(corr > threshold_abs)[0]
    if len(above) == 0:
        return 0, len(audio)
    start = max(0, above[0] - int(0.1 * sample_rate))
    end = min(len(audio), above[-1] + win_len + int(0.1 * sample_rate))
    return start, end


def normalize_audio(audio: np.ndarray, target_db: float = -3.0) -> np.ndarray:
    peak = np.max(np.abs(audio))
    if peak < 1e-12:
        return audio
    target_amp = 10.0 ** (target_db / 20.0)
    gain = target_amp / peak
    return audio * gain