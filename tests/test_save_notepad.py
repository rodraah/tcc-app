"""Salvar Bloco de Notas em Downloads / Área de Trabalho."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.actions.dialog import save_notepad_handler
from voice.actions.notepad import resolve_save_dir, save_content_to_file
from voice.models import Intent


def test_save_content_to_downloads_location():
    with tempfile.TemporaryDirectory() as tmp:
        downloads = Path(tmp) / "Downloads"
        config = {
            "filename_pattern": "nota_{timestamp}.txt",
            "locations": {"downloads": str(downloads)},
        }
        path = save_content_to_file("ola", config, location="downloads")
        assert path.parent == downloads.resolve()
        assert path.read_text(encoding="utf-8") == "ola"
        assert path.name.startswith("nota_")


def test_save_content_named():
    with tempfile.TemporaryDirectory() as tmp:
        downloads = Path(tmp) / "Downloads"
        config = {"locations": {"downloads": str(downloads)}}
        path = save_content_to_file(
            "x", config, location="downloads", name="minha nota"
        )
        assert path.name == "minha_nota.txt"


def test_save_content_to_desktop_location():
    with tempfile.TemporaryDirectory() as tmp:
        desktop = Path(tmp) / "Desktop"
        config = {
            "filename_pattern": "nota_{timestamp}.txt",
            "locations": {"desktop": str(desktop)},
        }
        path = save_content_to_file("x", config, location="desktop")
        assert path.parent == desktop.resolve()


def test_resolve_save_dir_unknown_raises():
    try:
        resolve_save_dir({"locations": {}}, location="nowhere")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "nowhere" in str(exc)


def test_save_notepad_handler_uses_location():
    with tempfile.TemporaryDirectory() as tmp:
        downloads = Path(tmp) / "Downloads"
        config = {
            "filename_pattern": "nota_{timestamp}.txt",
            "locations": {"downloads": str(downloads)},
        }
        with patch(
            "voice.actions.dialog.save_notepad_to_location",
            return_value=downloads / "nota_1.txt",
        ) as save_fn:
            result = save_notepad_handler(
                Intent("save_notepad", {"location": "downloads"}), config
            )
            save_fn.assert_called_once_with(config, "downloads", name=None)
            assert result.endswith("nota_1.txt")


if __name__ == "__main__":
    test_save_content_to_downloads_location()
    test_save_content_named()
    test_save_content_to_desktop_location()
    test_resolve_save_dir_unknown_raises()
    test_save_notepad_handler_uses_location()
    print("Todos os testes passaram.")
