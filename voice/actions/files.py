"""Operações de arquivo acionadas por voz (salvar, abrir, listar, criar pasta)."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from rapidfuzz import fuzz
from unidecode import unidecode

from voice.paths import LOGS_DIR, PROJECT_ROOT

LAST_SAVED_FILE = LOGS_DIR / "last_saved_path.txt"
RECENT_FILES = LOGS_DIR / "recent_files.json"
PROJECT_MARKER = "{project}"
DEFAULT_RECENT_LIMIT = 10


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


def _read_recent_raw() -> list[str]:
    if RECENT_FILES.is_file():
        try:
            data = json.loads(RECENT_FILES.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [str(p) for p in data if p]
        except (json.JSONDecodeError, OSError):
            pass
    if LAST_SAVED_FILE.is_file():
        raw = LAST_SAVED_FILE.read_text(encoding="utf-8").strip()
        if raw:
            return [raw]
    return []


def _write_recent(paths: list[str]) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    RECENT_FILES.write_text(
        json.dumps(paths, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if paths:
        LAST_SAVED_FILE.write_text(paths[0], encoding="utf-8")
    elif LAST_SAVED_FILE.exists():
        LAST_SAVED_FILE.unlink()


def get_recent_paths(limit: int | None = None) -> list[Path]:
    """Últimos caminhos salvos (mais recente primeiro). Só retorna arquivos que existem."""
    out: list[Path] = []
    for raw in _read_recent_raw():
        path = Path(raw)
        if path.is_file() and path not in out:
            out.append(path)
        if limit is not None and len(out) >= limit:
            break
    return out


def remember_saved_path(path: Path | str, *, limit: int = DEFAULT_RECENT_LIMIT) -> None:
    resolved = str(Path(path).resolve())
    paths = [resolved]
    for raw in _read_recent_raw():
        if raw != resolved:
            paths.append(raw)
    _write_recent(paths[: max(1, int(limit))])


def forget_saved_path(path: Path | str) -> None:
    target = str(Path(path).resolve())
    remaining = [p for p in _read_recent_raw() if p != target]
    _write_recent(remaining)


def get_last_saved_path() -> Path | None:
    recent = get_recent_paths(limit=1)
    return recent[0] if recent else None


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


def read_text_file(path: Path, max_chars: int = 800) -> str:
    text = path.read_text(encoding="utf-8")
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "…"
    return text


def read_last_saved(max_chars: int = 800) -> tuple[Path, str]:
    path = get_last_saved_path()
    if path is None:
        raise FileNotFoundError("Nenhum arquivo salvo recentemente.")
    return path, read_text_file(path, max_chars=max_chars)


def _name_score(spoken: str, entry: Path) -> int:
    needle = unidecode(spoken).strip().lower()
    if needle.endswith(".txt"):
        needle = needle[: -len(".txt")]
    needle_compact = re.sub(r"[^\w]+", "", needle)
    stem = unidecode(entry.stem).lower()
    stem_compact = re.sub(r"[^\w]+", "", stem)
    scores = [
        fuzz.ratio(needle, stem),
        fuzz.ratio(needle_compact, stem_compact),
        fuzz.partial_ratio(needle, stem),
    ]
    if needle and (needle in stem or needle_compact in stem_compact):
        scores.append(95)
    return max(scores)


def find_named_file(
    name: str, location: str, config: dict, *, min_score: int = 70
) -> Path:
    directory = resolve_location_dir(config, location)
    exact = directory / sanitize_filename(name)
    if exact.is_file():
        return exact.resolve()

    best: Path | None = None
    best_score = 0
    for entry in directory.iterdir():
        if not entry.is_file() or entry.name.startswith("."):
            continue
        score = _name_score(name, entry)
        if score > best_score:
            best_score = score
            best = entry
    if best is None or best_score < min_score:
        raise FileNotFoundError(
            f"Arquivo '{name}' não encontrado em {directory.name}."
        )
    return best.resolve()


def search_in_location(
    query: str, location: str, config: dict, limit: int = 8
) -> tuple[Path, list[str]]:
    directory = resolve_location_dir(config, location)
    needle = unidecode(query).strip().lower()
    hits: list[str] = []
    ranked: list[tuple[int, str]] = []
    for entry in directory.iterdir():
        if entry.name.startswith("."):
            continue
        hay = unidecode(entry.name).lower()
        if needle and needle in hay:
            score = 100
        else:
            score = fuzz.partial_ratio(needle, hay) if needle else 0
        if score >= 70:
            ranked.append((score, entry.name))
    ranked.sort(key=lambda item: (-item[0], item[1].lower()))
    for _, name in ranked[:limit]:
        hits.append(name)
    return directory.resolve(), hits


def create_folder(name: str, location: str, config: dict) -> Path:
    parent = resolve_location_dir(config, location)
    folder = parent / sanitize_dirname(name)
    folder.mkdir(parents=True, exist_ok=True)
    return folder.resolve()


def list_location(
    location: str,
    config: dict,
    limit: int = 8,
    kind: str = "all",
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
        if kind == "dirs" and not entry.is_dir():
            continue
        if kind == "txt" and not (entry.is_file() and entry.suffix.lower() == ".txt"):
            continue
        if kind == "all":
            pass
        elif kind not in ("dirs", "txt"):
            raise ValueError(f"Filtro de listagem desconhecido: {kind}")
        names.append(entry.name)
        if len(names) >= limit:
            break
    return directory.resolve(), names


def summarize_listing(directory: Path, names: list[str], *, kind: str = "all") -> str:
    label = {
        "dirs": "pastas",
        "txt": "arquivos txt",
        "all": "itens",
    }.get(kind, "itens")
    if not names:
        return f"{directory.name} não tem {label}."
    joined = ", ".join(names)
    return f"Em {directory.name} ({label}): {joined}."


def summarize_search(directory: Path, query: str, names: list[str]) -> str:
    if not names:
        return f"Nada com '{query}' em {directory.name}."
    joined = ", ".join(names)
    return f"Em {directory.name}, encontrei: {joined}."


def summarize_recent(paths: list[Path]) -> str:
    if not paths:
        return "Nenhum arquivo recente."
    joined = ", ".join(p.name for p in paths)
    return f"Recentes: {joined}."


def reveal_in_explorer(path: Path) -> None:
    """Abre o Explorer com o arquivo selecionado (Windows)."""
    subprocess.Popen(["explorer", "/select,", str(path.resolve())])


def reveal_last_saved() -> Path:
    path = get_last_saved_path()
    if path is None:
        raise FileNotFoundError("Nenhum arquivo salvo recentemente.")
    reveal_in_explorer(path)
    return path


def send_to_recycle_bin(path: Path) -> None:
    """Move para a Lixeira do Windows (FOF_ALLOWUNDO)."""
    import ctypes
    from ctypes import wintypes

    resolved = path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {resolved}")

    FO_DELETE = 0x0003
    FOF_ALLOWUNDO = 0x0040
    FOF_NOCONFIRMATION = 0x0010
    FOF_SILENT = 0x0004

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", wintypes.WORD),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", wintypes.LPVOID),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    # LPCWSTR a partir de str ganha 1 NUL; o \0 extra vira o segundo exigido pela API.
    op = SHFILEOPSTRUCTW()
    op.wFunc = FO_DELETE
    op.pFrom = str(resolved) + "\0"
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if result != 0:
        raise OSError(f"Falha ao enviar para a lixeira (código {result}).")
    forget_saved_path(resolved)


def resolve_delete_target(intent_params: dict, config: dict) -> Path:
    if intent_params.get("path"):
        path = Path(str(intent_params["path"]))
        if not path.is_file():
            raise FileNotFoundError(f"Arquivo não encontrado: {path}")
        return path.resolve()
    name = intent_params.get("name")
    location = intent_params.get("location")
    if name and location:
        return find_named_file(str(name), str(location), config)
    path = get_last_saved_path()
    if path is None:
        raise FileNotFoundError("Nenhum arquivo salvo recentemente.")
    return path
