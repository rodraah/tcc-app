import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

from voice.actions.files import (
    expand_location_path,
    remember_saved_path,
    sanitize_filename,
)


def read_notepad_content() -> str | None:
    """Lê texto do Bloco de Notas aberto (mesmo com diálogo modal)."""
    try:
        from pywinauto import Desktop

        desktop = Desktop(backend="uia")
        for win in desktop.windows(visible_only=True):
            title = win.window_text().lower()
            if not any(t in title for t in ("bloco de notas", "notepad")):
                continue
            if "salvar como" in title or "save as" in title:
                continue

            for ctrl_type in ("Document", "Edit"):
                try:
                    for ctrl in win.descendants(control_type=ctrl_type):
                        try:
                            text = ctrl.window_text()
                        except Exception:
                            text = ""
                        if not text:
                            try:
                                text = ctrl.get_value()
                            except Exception:
                                text = ""
                        if text is not None:
                            return text
                except Exception:
                    continue
    except Exception:
        pass
    return None


def resolve_save_dir(config: dict, location: str | None = None) -> Path:
    """Resolve pasta de destino: location conhecida ou default_dir."""
    if location:
        locations = config.get("locations") or {}
        raw = locations.get(location) or locations.get(location.lower())
        if not raw:
            raise ValueError(f"Local de salvamento desconhecido: {location}")
        directory = expand_location_path(str(raw))
    else:
        directory = Path(
            os.path.expanduser(
                config.get("default_dir", "~/Documents/VoiceAssistant")
            )
        )
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def save_content_to_file(
    content: str,
    config: dict,
    location: str | None = None,
    name: str | None = None,
) -> Path:
    directory = resolve_save_dir(config, location)
    if name:
        filename = sanitize_filename(name)
    else:
        pattern = config.get("filename_pattern", "nota_{timestamp}.txt")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = pattern.format(timestamp=timestamp)
    path = directory / filename
    path.write_text(content, encoding="utf-8")
    resolved = path.resolve()
    remember_saved_path(resolved)
    return resolved


def save_notepad_to_location(
    config: dict, location: str, name: str | None = None
) -> Path:
    """Lê o Bloco de Notas aberto e grava .txt no local pedido."""
    content = read_notepad_content()
    if content is None:
        raise RuntimeError("Nenhum Bloco de Notas aberto com texto legível.")
    return save_content_to_file(
        content, config, location=location, name=name
    )


def force_close_notepad() -> None:
    subprocess.run(
        ["taskkill", "/IM", "notepad.exe", "/F"],
        check=False,
        capture_output=True,
    )
    time.sleep(0.3)
