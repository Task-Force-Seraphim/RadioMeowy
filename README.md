# RadioMeowy

**Data you can hear, but not understand.**

RadioMeowy is a cryptographic acoustic courier. It encodes encrypted binary data into audio signals using Frequency-Shift Keying (FSK), DTMF tones, or Least Significant Bit (LSB) steganography. The system uses AES-256-GCM for data encryption, PGP key wrapping (Ed25519/Curve25519 ECC), quantum random number generation with fallback, and Reed-Solomon error correction. It produces audio payloads that can be transmitted over phone lines, radio, or stored as ordinary audio files.

This tool is intended for secure data transfer when traditional network channels are unavailable, untrusted, or subject to monitoring. It is used in penetration testing, physical security assessments, covert communication, and backup communication channels.

---

## Table of Contents

- [Threat Model](#threat-model)
- [Use Cases](#use-cases)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Detailed Usage](#detailed-usage)
- [PGP Key Management](#pgp-key-management)
- [Environment Configuration](#environment-configuration)
- [Audio Encoding Methods](#audio-encoding-methods)
- [Payload Format and Error Correction](#payload-format-and-error-correction)
- [Development and Testing](#development-and-testing)
- [License](#license)

---

## Threat Model

RadioMeowy is designed to operate in environments where the following threats are present:

- **Passive surveillance** – An adversary can intercept and record the audio signal, or capture audio files in transit. They may attempt to analyze the signal to extract or classify the data.

- **Active tampering** – An adversary can modify the audio in transit, introducing errors or altering the signal to disrupt decoding.

- **Lossy channels** – The acoustic path (phone lines, radio, low-bitrate codecs) may introduce noise, frequency distortion, or dropped packets. This can cause bit errors in the recovered data.

- **Traffic analysis** – Even if the content is encrypted, the mere presence of an audio signal carrying data may be detectable. The specific modulation (FSK or DTMF) is recognisable as data traffic.

- **Compromised endpoints** – If the private PGP key or the passphrase is exposed, the confidentiality of all past and future communications is lost.

The system mitigates these threats through:

- **Authenticated encryption** – AES-256-GCM provides confidentiality, integrity, and authenticity for the payload. Any tampering with the ciphertext is detected.

- **Forward secrecy** – Each session uses a fresh AES key and nonce. A compromised session key does not affect other sessions.

- **Error correction** – Reed-Solomon (255,223) with interleaving protects against burst errors, correcting up to 16 errors per block. This improves resilience in noisy channels.

- **Quantum entropy** – Nonces, salts, and session keys are generated using quantum random number generators when available, falling back to the system's cryptographic `secrets` module.

- **Stealth option** – LSB steganography embeds the payload into an innocuous carrier audio file. This provides plausible deniability and evades simple traffic analysis.

The system **does not** protect against:

- Traffic analysis when using FSK or DTMF (the signal is clearly data-like).
- Side-channel attacks on the host system (memory dumps, keyloggers).
- Cryptographic weaknesses in PGP or AES (the underlying algorithms are considered secure, but their implementation must be trusted).

---

## Use Cases

- **Covert data transfer** – Embed an encrypted file into a standard music track and share it via email, cloud storage, or USB. The carrier audio appears benign.

- **Air‑gapped communication** – Transmit data between two isolated systems using a speaker and microphone. This is useful in environments where USB drives are banned or network connectivity is forbidden.

- **Backup channel** – When network connectivity fails (e.g., during a natural disaster), use phone lines or radio to send critical status or authentication data.

- **Exfiltration in penetration tests** – Convert sensitive information into audio and play it over a phone call to a remote receiver. This bypasses network egress filters.

- **Digital watermarking** – Embed a fingerprint or tracking token into audio files without perceptible degradation.

---

## Installation

### Prerequisites

- Python 3.10 or higher
- `ffmpeg` (for MP3 loading in steganography mode)

Install ffmpeg:

- Debian/Ubuntu: `sudo apt install ffmpeg`
- macOS: `brew install ffmpeg`
- Windows: Download from ffmpeg.org and add to PATH.

### Install RadioMeowy

```bash
git clone https://github.com/Task-Force-Seraphim/RadioMeowy.git
cd radiomeowy
pip install -e .
```

This installs the package and makes the `radiomeowy` command available.

---

## Quick Start

Assume the recipient's PGP fingerprint is `ABCD1234EF567890` and the file `secret.txt` must be sent.

**FSK encoding:**

```bash
radiomeowy encode --data secret.txt --fingerprint ABCD1234EF567890 --output payload.wav --method fsk
```

**FSK decoding:**

```bash
radiomeowy decode --input payload.wav --secret-key my-private.asc --method fsk --output recovered.txt
```

**Steganography with a carrier:**

```bash
radiomeowy encode --data secret.txt --fingerprint ABCD1234EF567890 --output hidden.wav --method stego --carrier music.mp3
```

**Steganography decoding:**

```bash
radiomeowy decode --input hidden.wav --secret-key my-private.asc --method stego --output recovered.txt
```

---

## Detailed Usage

All commands follow:

```bash
radiomeowy <command> [OPTIONS]
```

### Encode Command

```bash
radiomeowy encode \
  --data <string or file path> \
  --fingerprint <recipient PGP fingerprint> \
  --output <output WAV file> \
  --method {fsk|dtmf|stego} \
  [--carrier <carrier audio file>] \
  [--bitrate <bits per second>] \
  [--sample-rate <Hz>] \
  [--phone-mode] \
  [--drone-mode] \
  [--qrng-api <URL>] \
  [--no-qrng] \
  [--verbose] \
  [--quiet]
```

Options:

- `--data, -d`: Input file path or literal string. If the argument is a valid file path, its contents are read; otherwise, the string is used.
- `--fingerprint, -f`: Recipient's PGP fingerprint (hex string, no spaces). The public key must be in the local GnuPG keyring.
- `--output, -o`: Output WAV file path.
- `--method, -m`: Encoding method: `fsk`, `dtmf`, or `stego`.
- `--carrier, -c`: Required for `stego`. Path to carrier audio file (WAV, MP3, FLAC, AIFF).
- `--bitrate, -b`: Bitrate for FSK (default 300 bps).
- `--sample-rate, -sr`: Sample rate of output audio (default 44100 Hz).
- `--phone-mode`: Optimise levels for phone calls (reduced dynamic range).
- `--drone-mode`: Optimise for drone playback.
- `--qrng-api`: Override QRNG endpoint URL.
- `--no-qrng`: Disable QRNG; use system `secrets`.
- `--verbose, -v`: Enable debug logging.
- `--quiet, -q`: Suppress all non‑error output.

Example:

```bash
radiomeowy encode --data "Classified" --fingerprint DEADBEEF1234 --output msg.wav --method dtmf
```

### Decode Command

```bash
radiomeowy decode \
  --input <audio file> \
  --secret-key <PGP secret key file> \
  [--method {auto|fsk|dtmf|stego}] \
  [--output <decoded file>] \
  [--sample-rate <Hz>] \
  [--phone-mode] \
  [--verbose] \
  [--quiet]
```

Options:

- `--input, -i`: Input audio file.
- `--secret-key, -s`: Path to ASCII‑armored PGP secret key. The passphrase is prompted if not set in environment.
- `--method`: Decoding method: `auto` (not implemented; specify `fsk`, `dtmf`, or `stego`).
- `--output, -o`: File to save decoded plaintext. If omitted, output goes to stdout (UTF‑8 text if possible, otherwise hexdump).
- `--sample-rate, -sr`: Expected sample rate (default 44100 Hz).
- `--phone-mode`: Apply phone‑line equalisation before decoding.
- `--verbose, -v`: Enable debug logging.
- `--quiet, -q`: Suppress non‑error output.

Example:

```bash
radiomeowy decode --input msg.wav --secret-key private.asc --method dtmf --output msg.txt
```

### Challenge and Verify

These commands implement a PGP challenge‑response identity verification.

**Generate challenge:**

```bash
radiomeowy challenge --fingerprint <recipient fingerprint> [--output <file>]
```

**Sign the challenge using GnuPG:**

```bash
gpg --detach-sign --local-user <your-fingerprint> challenge.txt
```

**Verify signature:**

```bash
radiomeowy verify --challenge challenge.txt --signature signature.sig --fingerprint <expected fingerprint>
```

Verification returns success or failure.

---

## PGP Key Management

RadioMeowy uses `python-gnupg`, which depends on a GnuPG installation.

### Generating a Key Pair

```bash
gpg --full-generate-key
```

Select ECC (Ed25519/Curve25519) for optimal performance.

### Exporting Keys

Public key:

```bash
gpg --export --armor <fingerprint> > public.asc
```

Private key:

```bash
gpg --export-secret-key --armor <fingerprint> > private.asc
```

### Importing Keys

```bash
gpg --import public.asc
```

### Extracting Fingerprint

```bash
gpg --fingerprint <email or key ID>
```

The fingerprint is a 40‑character hex string.

---

## Environment Configuration

Create a `.env` file in the working directory (or use system environment variables):

```
PGP_PASSPHRASE=your-passphrase
QRNG_API_KEY=optional-api-key
```

- `PGP_PASSPHRASE`: If set, the decode command uses it without prompting. **Storing this in plain text is not recommended for production**; use a credential manager or prompt at runtime.
- `QRNG_API_KEY`: API key for QRNG endpoints that require authentication.

---

## Audio Encoding Methods

### Frequency-Shift Keying (FSK)

- Bits are represented as two frequencies: 1000 Hz (0) and 2000 Hz (1).
- Bitrate configurable (default 300 bps). Higher bitrates shorten duration but increase error rate.
- Suitable for phone lines and radio.

### DTMF (Dual-Tone Multi-Frequency)

- Each hex nibble (0‑9, A‑F) is encoded as a pair of simultaneous sine tones per the standard DTMF table.
- Tone duration: 100 ms with 50 ms silence.
- Deniable – appears as telephone keypresses.

### LSB Steganography

- Payload is embedded in the least significant bit of each audio sample.
- Carrier must be lossless (WAV, FLAC) for reliable extraction. MP3 carriers are not recommended.
- Output is always a WAV file.
- Capacity is limited by the number of samples (one bit per sample per channel).

---

## Payload Format and Error Correction

The binary payload (after encryption) follows this structure:

```
MAGIC (4B) + VERSION (1B) + SALT (16B) + NONCE (12B) + WKEY_LEN (2B) + WRAPPED_KEY (var) + CIPHERTEXT (var) + TAG (16B)
```

- MAGIC: `MEOW` (ASCII).
- VERSION: `0x01`.
- SALT: 16 bytes (reserved for future KDF).
- NONCE: 12 bytes for AES‑GCM.
- WKEY_LEN: Length of wrapped key (big‑endian).
- WRAPPED_KEY: PGP‑encrypted AES session key.
- CIPHERTEXT: AES‑GCM encrypted data.
- TAG: 16‑byte authentication tag.

For FSK and DTMF, the payload is processed through Reed‑Solomon (255,223) with interleaving. This adds 32 parity bytes per 223 data bytes and corrects up to 16 errors per block. Steganography does not use error correction because the carrier is lossless.

---

## Development and Testing

### Code Quality

```bash
ruff check .
mypy .
```

### Running Tests

```bash
pip install pytest pytest-cov
pytest --cov=radio_meowy
```

### Adding New Audio Methods

Create a new module in `radio_meowy/audio/` with `encode_*` and `decode_*` functions following the existing signatures. Update the CLI to recognise the new method.

---

## License

RadioMeowy is released under the GNU Affero General Public License version 3 (AGPLv3). See the [LICENSE](LICENSE) file.

---

## Authors

**Task Force Seraphim**  
**Seraphim-01**

---

## References

- [Cryptography Library](https://cryptography.io/)
- [python-gnupg](https://python-gnupg.readthedocs.io/)
- [unireedsolomon](https://github.com/lrq3000/unireedsolomon)
- [Quantum Random Number Generator (ANU)](https://qrng.anu.edu.au/)
