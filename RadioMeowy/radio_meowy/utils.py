"""General utilities: environment loading, passphrase prompting, etc."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
import getpass


def load_environment(env_file: Optional[Path] = None) -> None:
    """
    Load .env file. If no file specified, search for .env in current directory.
    """
    if env_file is None:
        env_file = Path(".env")
    if env_file.exists():
        load_dotenv(env_file)
    else:
        load_dotenv()  # default .env


def get_env_var(name: str, required: bool = False, default: Optional[str] = None) -> Optional[str]:
    """
    Get environment variable. If required and not set, raise ValueError.
    """
    value = os.getenv(name)
    if required and value is None:
        raise ValueError(f"Environment variable {name} is required but not set")
    return value if value is not None else default


def prompt_passphrase(prompt: str = "Enter PGP passphrase: ") -> str:
    """Securely prompt for a passphrase."""
    return getpass.getpass(prompt)