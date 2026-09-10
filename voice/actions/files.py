"""Operações de arquivo acionadas por voz (salvar, abrir, listar, criar pasta)."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from unidecode import unidecode

from voice.paths import LOGS_DIR, PROJECT_ROOT

LAST_SAVED_FILE = LOGS_DIR / "last_saved_path.txt"
PROJECT_MARKER = "{project}"


def sanitize_filename(name: str, default: str = "nota") -> str:
    """Converte fala em nome de arquivo .txt seguro."""
    cleaned = unidecode(name).strip().lower()
    if cleaned.endswith(".txt"):
        cleaned = cleaned[: -len(".txt")]
    cleaned = re.sub(r"[^\w\s-]", "", cleaned)
    cleaned = re.sub(r"[-\s]+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = default
    return cleaned + ".txt"


def sanitize_dirname(name: str, default: str = "pasta") -> str:
    cleaned = unidecode(name).strip()
    cleaned = re.sub(r'[<>:"/\\|?*]', "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned or default


def expand_location_path(raw: str) -> Path:
    if str(raw).strip() == PROJECT_MARKER:
        return PROJECT_ROOT
    return Path(os.path.expanduser(str(raw)))


def resolve_location_dir(config: dict, location: str) -> Path:
    locations = config.get("locations") or {}
    raw = locations.get(location) or locations.get(location.lower())
    if not raw:
        raise ValueError(f"Local desconhecido: {location}")
    directory = expand_location_path(str(raw))
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def remember_saved_path(path: Path | str) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    LAST_SAVED_FILE.write_text(str(Path(path).resolve()), encoding="utf-8")


def get_last_saved_path() -> Path | None:
    if not LAST_SAVED_FILE.is_file():
        return None
    raw = LAST_SAVED_FILE.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_file() else None


def open_path(path: Path) -> None:
    resolved = path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {resolved}")
    os.startfile(str(resolved))  # type: ignore[attr-defined]


def open_last_saved() -> Path:
    path = get_last_saved_path()
    if path is None:
        raise FileNotFoundError("Nenhum arquivo salvo recentemente.")
    open_path(path)
    return path


def read_last_saved(max_chars: int = 800) -> tuple[Path, str]:
    path = get_last_saved_path()
    if path is None:
        raise FileNotFoundError("Nenhum arquivo salvo recentemente.")
    text = path.read_text(encoding="utf-8")
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "…"
    return path, text


def create_folder(name: str, location: str, config: dict) -> Path:
    parent = resolve_location_dir(config, location)
    folder = parent / sanitize_dirname(name)
    folder.mkdir(parents=True, exist_ok=True)
    return folder.resolve()


def list_location(
    location: str, config: dict, limit: int = 8
) -> tuple[Path, list[str]]:
    directory = resolve_location_dir(config, location)
    entries = sorted(
        directory.iterdir(),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    names: list[str] = []
    for entry in entries:
        if entry.name.startswith("."):
            continue
        names.append(entry.name)
        if len(names) >= limit:
            break
    return directory.resolve(), names


def summarize_listing(directory: Path, names: list[str]) -> str:
    if not names:
        return f"{directory.name} está vazio."
    joined = ", ".join(names)
    return f"Em {directory.name}: {joined}."


def reveal_in_explorer(path: Path) -> None:
    """Abre o Explorer com o arquivo selecionado (Windows)."""
    subprocess.Popen(["explorer", "/select,", str(path.resolve())])
