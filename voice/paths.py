"""Centralised resource-path constants for the voice-assistant package.

All paths are resolved relative to the project root (the directory
containing ``voice/``, ``config/``, ``models/``, etc.) — never from the
current working directory.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DEFAULT_CONFIG = CONFIG_DIR / "commands.yaml"
MODELS_DIR = PROJECT_ROOT / "models"
LOGS_DIR = PROJECT_ROOT / "logs"
BROWSER_PROFILE_DIR = PROJECT_ROOT / ".browser-profile"
