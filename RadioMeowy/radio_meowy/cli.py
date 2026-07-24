"""RadioMeowy CLI using Typer and Rich."""

import sys
import signal
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from radio_meowy import __version__
from radio_meowy.banners import get_random_banner
from radio_meowy.utils import load_environment, get_env_var, prompt_passphrase
from radio_meowy.rng import get_aes_key, get_nonce, get_salt
from radio_meowy.crypto import encrypt_aes_gcm, decrypt_aes_gcm
from radio_meowy.pgp import (
    encrypt_to_fingerprint,
    decrypt_with_secret_key,
    generate_challenge,
    verify_signature,
    import_secret_key,
    get_fingerprint,
)
from radio_meowy.payload import build_payload, parse_payload
from radio_meowy.audio.fsk import encode_fsk, decode_fsk
from radio_meowy.audio.dtmf import encode_dtmf, decode_dtmf
from radio_meowy.audio.stego import encode_lsb, decode_lsb
from radio_meowy.audio.utils import load_audio, save_audio, add_sync_tones, detect_sync_tones, normalize_audio
from radio_meowy.error.correction import encode_reedsolomon, decode_reedsolomon

app = typer.Typer(
    name="radio-meowy",
    help="Cryptographic acoustic courier",
    add_completion=False,
    rich_markup_mode="rich",
    no_args_is_help=True,
)
console = Console()

_interrupted = False

def signal_handler(sig, frame):
    global _interrupted
    _interrupted = True
    console.print("\n[bold red]Interrupted by user. Cleaning up...[/bold red]")

signal.signal(signal.SIGINT, signal_handler)


@app.callback()
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        banner = get_random_banner()
        console.print(Panel(banner, style="bold cyan", border_style="green"))
        console.print("\n[bold yellow]RadioMeowy — Data you can hear, but not understand.[/bold yellow]")
        console.print(f"[dim]Version {__version__}[/dim]")
        console.print("[dim]Use --help for commands.[/dim]")
        load_environment()


@app.command()
def encode(
    ctx: typer.Context,
    data: str = typer.Option(..., "--data", "-d", help="Input file path or string data"),
    fingerprint: str = typer.Option(..., "--fingerprint", "-f", help="Recipient's PGP fingerprint"),
    output: Path = typer.Option(..., "--output", "-o", help="Output WAV file path"),
    method: str = typer.Option("fsk", "--method", "-m", help="Encoding method: fsk|dtmf|stego"),
    carrier: Optional[Path] = typer.Option(None, "--carrier", "-c", help="Carrier audio for stego mode"),
    bitrate: int = typer.Option(300, "--bitrate", "-b", help="Bits per second (default: 300)"),
    sample_rate: int = typer.Option(44100, "--sample-rate", "-sr", help="Sample rate (default: 44100)"),
    phone_mode: bool = typer.Option(False, "--phone-mode", help="Optimize for phone calls"),
    drone_mode: bool = typer.Option(False, "--drone-mode", help="Optimize for drone playback"),
    qrng_api: Optional[str] = typer.Option(None, "--qrng-api", help="QRNG API endpoint override"),
    no_qrng: bool = typer.Option(False, "--no-qrng", help="Disable QRNG (fallback to secrets)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Debug logging"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress output"),
):
    global _interrupted
    if _interrupted:
        raise typer.Exit(1)

    load_environment()

    try:
        data_path = Path(data)
        if data_path.exists():
            with open(data_path, 'rb') as f:
                plaintext = f.read()
        else:
            plaintext = data.encode('utf-8')
    except Exception as e:
        console.print(f"[red]Error reading input data: {e}[/red]")
        raise typer.Exit(1)

    aes_key = get_aes_key(api_url=qrng_api if not no_qrng else None)
    nonce = get_nonce(api_url=qrng_api if not no_qrng else None)
    salt = get_salt(api_url=qrng_api if not no_qrng else None)

    ciphertext, auth_tag = encrypt_aes_gcm(aes_key, plaintext, nonce)

    try:
        wrapped_key = encrypt_to_fingerprint(aes_key, fingerprint)
    except Exception as e:
        console.print(f"[red]PGP encryption failed: {e}[/red]")
        raise typer.Exit(1)

    payload = build_payload(salt, nonce, wrapped_key, ciphertext, auth_tag)

    # For stego it doesn't apply RS due to WAV LSB being lossless
    if method == "stego":
        data_to_audio = payload
        if not quiet:
            console.print("[yellow]Steganography: no error correction applied (lossless).[/yellow]")
    else:
        if not quiet:
            console.print("[yellow]Applying Reed-Solomon error correction...[/yellow]")
        data_to_audio = encode_reedsolomon(payload)

    try:
        if method == "fsk":
            audio = encode_fsk(data_to_audio, bitrate=bitrate, sample_rate=sample_rate)
        elif method == "dtmf":
            audio = encode_dtmf(data_to_audio, sample_rate=sample_rate)
        elif method == "stego":
            if carrier is None:
                raise ValueError("Carrier audio required for stego mode")
            encode_lsb(carrier, data_to_audio, output, bit_depth=16)
            if not quiet:
                console.print(f"[green]Stego encoded data into {output}[/green]")
            return
        else:
            raise ValueError(f"Unsupported method: {method}")
    except Exception as e:
        console.print(f"[red]Audio encoding failed: {e}[/red]")
        raise typer.Exit(1)

    audio = add_sync_tones(audio, sample_rate)

    if phone_mode:
        audio = normalize_audio(audio, target_db=-6.0)
    elif drone_mode:
        audio = normalize_audio(audio, target_db=-3.0)

    try:
        save_audio(audio, output, sample_rate)
    except Exception as e:
        console.print(f"[red]Failed to save audio: {e}[/red]")
        raise typer.Exit(1)

    if not quiet:
        console.print(f"[green]Encoded audio saved to {output}[/green]")


@app.command()
def decode(
    ctx: typer.Context,
    input: Path = typer.Option(..., "--input", "-i", help="Input audio file or stdin"),
    secret_key: Path = typer.Option(..., "--secret-key", "-s", help="PGP secret key (ASCII armor)"),
    method: str = typer.Option("auto", "--method", "-m", help="auto|fsk|dtmf|stego"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file for decoded data"),
    sample_rate: int = typer.Option(44100, "--sample-rate", "-sr", help="Sample rate (default: 44100)"),
    phone_mode: bool = typer.Option(False, "--phone-mode", help="Optimize for phone-call audio"),
    qrng_api: Optional[str] = typer.Option(None, "--qrng-api", help="QRNG API endpoint override"),
    no_qrng: bool = typer.Option(False, "--no-qrng", help="Disable QRNG"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Debug logging"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress output"),
):
    global _interrupted
    if _interrupted:
        raise typer.Exit(1)

    load_environment()

    try:
        audio = load_audio(input, sample_rate=sample_rate)
    except Exception as e:
        console.print(f"[red]Failed to load audio: {e}[/red]")
        raise typer.Exit(1)

    start, end = detect_sync_tones(audio, sample_rate)
    if start > 0 or end < len(audio):
        audio = audio[start:end]
        if not quiet:
            console.print(f"[dim]Trimmed sync tones: {start} to {end}[/dim]")

    if method == "auto":
        console.print("[red]Auto detection not implemented. Please specify --method fsk|dtmf|stego.[/red]")
        raise typer.Exit(1)

    try:
        if method == "fsk":
            data_bytes = decode_fsk(audio, bitrate=300, sample_rate=sample_rate)
        elif method == "dtmf":
            data_bytes = decode_dtmf(audio, sample_rate=sample_rate)
        elif method == "stego":
            data_bytes = decode_lsb(input, bit_depth=16)
        else:
            raise ValueError(f"Unsupported method: {method}")
    except Exception as e:
        console.print(f"[red]Audio decoding failed: {e}[/red]")
        raise typer.Exit(1)

    if verbose:
        console.print(f"[dim]Extracted first 20 bytes: {data_bytes[:20].hex()}[/dim]")

    # For stego the tool skips RS because we didn't apply it during encoding
    if method == "stego":
        try:
            payload = data_bytes
            # The payload starts with MAGIC, no length prefix.
            parsed = parse_payload(payload)
            if verbose:
                console.print("[dim]Parsed stego payload directly (no RS).[/dim]")
        except Exception as e:
            console.print(f"[red]Stego payload parsing failed: {e}[/red]")
            raise typer.Exit(1)
    else:
        # For fsk and dtmf we need RS decode
        if not quiet:
            console.print("[yellow]Applying Reed-Solomon error correction...[/yellow]")
        try:
            payload, success = decode_reedsolomon(data_bytes)
            if not success:
                console.print("[yellow]Some RS blocks could not be corrected; data may be corrupted.[/yellow]")
            if verbose:
                console.print(f"[dim]After RS decode, first 20 bytes: {payload[:20].hex()}[/dim]")
            parsed = parse_payload(payload)
        except Exception as e:
            console.print(f"[red]RS decoding and payload parsing failed: {e}[/red]")
            raise typer.Exit(1)

    # Decrypt PGP-wrapped key using keyring
    try:
        passphrase = get_env_var("PGP_PASSPHRASE")
        if passphrase is None:
            passphrase = prompt_passphrase("Enter PGP secret key passphrase: ")

        aes_key = decrypt_with_secret_key(parsed["wrapped_key"], passphrase=passphrase)
        if verbose:
            console.print(f"[dim]AES key (hex): {aes_key.hex()}[/dim]")
            console.print(f"[dim]Nonce (hex): {parsed['nonce'].hex()}[/dim]")
            console.print(f"[dim]Ciphertext length: {len(parsed['ciphertext'])} bytes[/dim]")
            console.print(f"[dim]Auth tag (hex): {parsed['auth_tag'].hex()}[/dim]")
    except Exception as e:
        console.print(f"[red]PGP decryption failed: {e}[/red]")
        if verbose:
            console.print("[dim]Ensure the correct private key is in your keyring and the passphrase is correct.[/dim]")
        raise typer.Exit(1)

    # Decrypt AES-GCM
    try:
        plaintext = decrypt_aes_gcm(aes_key, parsed["ciphertext"], parsed["nonce"], parsed["auth_tag"])
    except Exception as e:
        console.print(f"[red]AES decryption failed: {e}[/red]")
        if verbose:
            console.print(f"[dim]Exception type: {type(e).__name__}[/dim]")
            console.print("[dim]Check that the PGP key matches the fingerprint used during encoding.[/dim]")
            console.print("[dim]If the data is corrupted, try the --method fsk or dtmf (if applicable).[/dim]")
        raise typer.Exit(1)

    if output is not None:
        with open(output, 'wb') as f:
            f.write(plaintext)
        if not quiet:
            console.print(f"[green]Decoded data saved to {output}[/green]")
    else:
        try:
            text = plaintext.decode('utf-8')
            console.print(text)
        except UnicodeDecodeError:
            console.print("[dim]Binary data (not UTF-8):[/dim]")
            console.print(plaintext.hex())


@app.command()
def challenge(
    ctx: typer.Context,
    fingerprint: str = typer.Option(..., "--fingerprint", "-f", help="PGP fingerprint to challenge"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file for challenge"),
):
    load_environment()
    challenge_text = generate_challenge()
    if output:
        with open(output, 'w') as f:
            f.write(challenge_text)
        console.print(f"[green]Challenge written to {output}[/green]")
    else:
        console.print(challenge_text)


@app.command()
def verify(
    ctx: typer.Context,
    challenge: Path = typer.Option(..., "--challenge", "-c", help="Challenge file"),
    signature: Path = typer.Option(..., "--signature", "-s", help="Signature file"),
    fingerprint: str = typer.Option(..., "--fingerprint", "-f", help="Expected fingerprint"),
):
    load_environment()
    try:
        with open(challenge, 'r') as f:
            challenge_text = f.read().strip()
        with open(signature, 'r') as f:
            signature_text = f.read().strip()
    except Exception as e:
        console.print(f"[red]Failed to read files: {e}[/red]")
        raise typer.Exit(1)
    valid = verify_signature(challenge_text, signature_text, fingerprint)
    if valid:
        console.print("[green]Signature is valid![/green]")
    else:
        console.print("[red]Signature verification failed.[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()