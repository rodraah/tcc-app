import os
import subprocess
import time
from datetime import datetime
from pathlib import Path


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


def save_content_to_file(content: str, config: dict) -> Path:
    default_dir = os.path.expanduser(
        config.get("default_dir", "~/Documents/VoiceAssistant")
    )
    directory = Path(default_dir)
    directory.mkdir(parents=True, exist_ok=True)

    pattern = config.get("filename_pattern", "nota_{timestamp}.txt")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = pattern.format(timestamp=timestamp)
    path = directory / filename
    path.write_text(content, encoding="utf-8")
    return path.resolve()


def force_close_notepad() -> None:
    subprocess.run(
        ["taskkill", "/IM", "notepad.exe", "/F"],
        check=False,
        capture_output=True,
    )
    time.sleep(0.3)
