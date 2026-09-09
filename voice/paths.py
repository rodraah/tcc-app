"""Centralised resource-path constants for the voice-assistant package.

All paths are resolved relative to the project root (the directory
containing ``voice/``, ``config/``, ``models/``, etc.) — never from the
current working directory.  When frozen (PyInstaller), the root is the
folder that contains the .exe.
"""

from app_paths import (  # noqa: F401 — re-export
    BROWSER_PROFILE_DIR,
    CONFIG_DIR,
    DEFAULT_CONFIG,
    LOGS_DIR,
    MODELS_DIR,
    PROJECT_ROOT,
)
