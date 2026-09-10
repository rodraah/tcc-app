"""Gerenciamento de arquivos por voz."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.actions.dialog import (
    create_folder_handler,
    list_folder_handler,
    open_last_file_handler,
    read_last_file_handler,
    save_notepad_handler,
)
from voice.actions.files import (
    PROJECT_MARKER,
    expand_location_path,
    get_last_saved_path,
    remember_saved_path,
    sanitize_filename,
    sanitize_dirname,
)
from voice.actions.notepad import save_content_to_file
from voice.intent_parser import IntentParser
from voice.models import Intent
from voice.paths import PROJECT_ROOT


def test_sanitize_filename():
    assert sanitize_filename("lista de compras") == "lista_de_compras.txt"
    assert sanitize_filename("Ja Tem.txt") == "ja_tem.txt"


def test_save_named_to_downloads():
    with tempfile.TemporaryDirectory() as tmp:
        downloads = Path(tmp) / "Downloads"
        config = {
            "filename_pattern": "nota_{timestamp}.txt",
            "locations": {"downloads": str(downloads)},
        }
        path = save_content_to_file(
            "ola", config, location="downloads", name="lista de compras"
        )
        assert path.name == "lista_de_compras.txt"
        assert path.parent == downloads.resolve()
        assert path.read_text(encoding="utf-8") == "ola"


def test_save_to_documentos_and_project():
    with tempfile.TemporaryDirectory() as tmp:
        docs = Path(tmp) / "Documents"
        config = {
            "locations": {
                "documentos": str(docs),
                "projeto": PROJECT_MARKER,
            }
        }
        p1 = save_content_to_file("a", config, location="documentos", name="a")
        assert p1.parent == docs.resolve()
        assert expand_location_path(PROJECT_MARKER) == PROJECT_ROOT
        p2 = save_content_to_file("b", config, location="projeto", name="b")
        assert p2.parent == PROJECT_ROOT.resolve()
        p2.unlink(missing_ok=True)


def test_remember_and_open_last(monkeypatch_path=None):
    with tempfile.TemporaryDirectory() as tmp:
        note = Path(tmp) / "nota.txt"
        note.write_text("conteudo", encoding="utf-8")
        with patch("voice.actions.files.LAST_SAVED_FILE", Path(tmp) / "last.txt"):
            with patch("voice.actions.files.LOGS_DIR", Path(tmp)):
                remember_saved_path(note)
                assert get_last_saved_path() == note.resolve()
                with patch("voice.actions.files.open_path") as opener:
                    path = open_last_file_handler(Intent("open_last_file"))
                    opener.assert_called_once()
                    assert path == str(note.resolve())
                text = read_last_file_handler(Intent("read_last_file"))
                assert text == "conteudo"


def test_create_and_list_folder():
    with tempfile.TemporaryDirectory() as tmp:
        docs = Path(tmp) / "Documents"
        config = {"locations": {"documentos": str(docs), "downloads": str(Path(tmp) / "Dl")}}
        created = create_folder_handler(
            Intent("create_folder", {"name": "TCC", "location": "documentos"}),
            config,
        )
        assert Path(created).name == "TCC"
        assert Path(created).is_dir()
        (Path(tmp) / "Dl").mkdir()
        (Path(tmp) / "Dl" / "a.txt").write_text("x", encoding="utf-8")
        summary = list_folder_handler(
            Intent("list_folder", {"location": "downloads"}), config
        )
        assert "a.txt" in summary


def test_parser_save_named():
    parser = IntentParser()
    intent = parser.parse("salvar em downloads como lista de compras")
    assert intent is not None
    assert intent.name == "save_notepad"
    assert intent.params["location"] == "downloads"
    assert intent.params["name"] == "lista de compras"


def test_parser_save_documentos_projeto():
    parser = IntentParser()
    assert parser.parse("salvar em documentos").params["location"] == "documentos"
    assert parser.parse("salvar na pasta do projeto").params["location"] == "projeto"


def test_parser_open_read_last():
    parser = IntentParser()
    assert parser.parse("abrir ultima nota").name == "open_last_file"
    assert parser.parse("abrir o que acabei de salvar").name == "open_last_file"
    assert parser.parse("ler ultima nota").name == "read_last_file"


def test_parser_create_and_list():
    parser = IntentParser()
    create = parser.parse("criar pasta TCC em documentos")
    assert create.name == "create_folder"
    assert create.params["name"] == "tcc"
    assert create.params["location"] == "documentos"
    listing = parser.parse("o que tem em downloads")
    assert listing.name == "list_folder"
    assert listing.params["location"] == "downloads"


def test_sanitize_dirname():
    assert sanitize_dirname("TCC 2026") == "TCC 2026"


def test_save_notepad_handler_passes_name():
    config = {"locations": {"downloads": "~/Downloads"}}
    with patch(
        "voice.actions.dialog.save_notepad_to_location",
        return_value=Path("x.txt"),
    ) as save_fn:
        save_notepad_handler(
            Intent(
                "save_notepad",
                {"location": "downloads", "name": "lista"},
            ),
            config,
        )
        save_fn.assert_called_once_with(config, "downloads", name="lista")


if __name__ == "__main__":
    test_sanitize_filename()
    test_save_named_to_downloads()
    test_save_to_documentos_and_project()
    test_remember_and_open_last()
    test_create_and_list_folder()
    test_parser_save_named()
    test_parser_save_documentos_projeto()
    test_parser_open_read_last()
    test_parser_create_and_list()
    test_sanitize_dirname()
    test_save_notepad_handler_passes_name()
    print("Todos os testes passaram.")
