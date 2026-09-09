"""Resolve project paths for source runs and frozen (PyInstaller) builds.

- ``data_root``: writable folder next to the .exe (or the repo root in source).
- ``resource_root``: bundled read-only assets inside ``sys._MEIPASS`` when frozen.

Shipped files (models, default YAML/JSON, Playwright Chromium) are copied next
to the exe by the build script, so most callers only need ``data_root``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def resource_root() -> Path:
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def data_root() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def configure_playwright_browsers() -> Path | None:
    """Point Playwright at the bundled Chromium folder when present.

    Call once at process start (before ``sync_playwright().start()``).
    Returns the browsers path if it was configured, else None.
    """
    bundled = data_root() / "ms-playwright"
    if not bundled.is_dir():
        return None
    # Only set when unset so a developer can still override via env.
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(bundled.resolve()))
    return bundled


# Evaluated once at import — fine for both source and frozen.
PROJECT_ROOT = data_root()
RESOURCE_ROOT = resource_root()
CONFIG_DIR = PROJECT_ROOT / "config"
DEFAULT_CONFIG = CONFIG_DIR / "commands.yaml"
MODELS_DIR = PROJECT_ROOT / "models"
LOGS_DIR = PROJECT_ROOT / "logs"
BROWSER_PROFILE_DIR = PROJECT_ROOT / ".browser-profile"
MAPEAMENTO_PATH = PROJECT_ROOT / "mapeamento.json"
PLAYWRIGHT_BROWSERS_DIR = PROJECT_ROOT / "ms-playwright"
