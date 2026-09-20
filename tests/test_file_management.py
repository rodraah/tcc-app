"""Gerenciamento de arquivos por voz."""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.actions.dialog import (
    create_folder_handler,
    delete_file_handler,
    list_folder_handler,
    list_recent_files_handler,
    open_file_handler,
    open_last_file_handler,
    read_file_handler,
    read_last_file_handler,
    reveal_last_file_handler,
    save_notepad_handler,
    search_files_handler,
)
from voice.actions.files import (
    PROJECT_MARKER,
    expand_location_path,
    find_named_file,
    get_last_saved_path,
    get_recent_paths,
    remember_saved_path,
    sanitize_dirname,
    sanitize_filename,
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


def test_remember_and_open_last():
    with tempfile.TemporaryDirectory() as tmp:
        note = Path(tmp) / "nota.txt"
        note.write_text("conteudo", encoding="utf-8")
        with patch("voice.actions.files.LAST_SAVED_FILE", Path(tmp) / "last.txt"):
            with patch("voice.actions.files.RECENT_FILES", Path(tmp) / "recent.json"):
                with patch("voice.actions.files.LOGS_DIR", Path(tmp)):
                    remember_saved_path(note)
                    assert get_last_saved_path() == note.resolve()
                    with patch("voice.actions.files.open_path") as opener:
                        path = open_last_file_handler(Intent("open_last_file"))
                        opener.assert_called_once()
                        assert path == str(note.resolve())
                    text = read_last_file_handler(Intent("read_last_file"))
                    assert text == "conteudo"


def test_recent_history_keeps_n():
    with tempfile.TemporaryDirectory() as tmp:
        files = []
        for i in range(5):
            p = Path(tmp) / f"n{i}.txt"
            p.write_text(str(i), encoding="utf-8")
            files.append(p)
        with patch("voice.actions.files.LAST_SAVED_FILE", Path(tmp) / "last.txt"):
            with patch("voice.actions.files.RECENT_FILES", Path(tmp) / "recent.json"):
                with patch("voice.actions.files.LOGS_DIR", Path(tmp)):
                    for p in files:
                        remember_saved_path(p, limit=3)
                    recent = get_recent_paths()
                    assert len(recent) == 3
                    assert recent[0] == files[-1].resolve()
                    assert recent[1] == files[-2].resolve()
                    assert recent[2] == files[-3].resolve()
                    data = json.loads((Path(tmp) / "recent.json").read_text(encoding="utf-8"))
                    assert len(data) == 3


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
        (Path(tmp) / "Dl" / "pasta").mkdir()
        (Path(tmp) / "Dl" / "b.md").write_text("y", encoding="utf-8")
        summary = list_folder_handler(
            Intent("list_folder", {"location": "downloads"}), config
        )
        assert "a.txt" in summary
        dirs_only = list_folder_handler(
            Intent("list_folder", {"location": "downloads", "kind": "dirs"}),
            config,
        )
        assert "pasta" in dirs_only
        assert "a.txt" not in dirs_only
        txt_only = list_folder_handler(
            Intent("list_folder", {"location": "downloads", "kind": "txt"}),
            config,
        )
        assert "a.txt" in txt_only
        assert "b.md" not in txt_only
        assert "pasta" not in txt_only


def test_open_read_search_by_name():
    with tempfile.TemporaryDirectory() as tmp:
        docs = Path(tmp) / "Documents"
        docs.mkdir()
        note = docs / "lista_de_compras.txt"
        note.write_text("leite e pao", encoding="utf-8")
        (docs / "relatorio_final.txt").write_text("ok", encoding="utf-8")
        config = {"locations": {"documentos": str(docs)}}
        found = find_named_file("lista de compras", "documentos", config)
        assert found == note.resolve()
        with patch("voice.actions.dialog.open_path") as opener:
            path = open_file_handler(
                Intent("open_file", {"name": "lista de compras", "location": "documentos"}),
                config,
            )
            opener.assert_called_once()
            assert path == str(note.resolve())
        text = read_file_handler(
            Intent("read_file", {"name": "lista de compras", "location": "documentos"}),
            config,
        )
        assert "leite" in text
        summary = search_files_handler(
            Intent("search_files", {"query": "relatorio", "location": "documentos"}),
            config,
        )
        assert "relatorio_final.txt" in summary


def test_reveal_last():
    with tempfile.TemporaryDirectory() as tmp:
        note = Path(tmp) / "nota.txt"
        note.write_text("x", encoding="utf-8")
        with patch("voice.actions.files.LAST_SAVED_FILE", Path(tmp) / "last.txt"):
            with patch("voice.actions.files.RECENT_FILES", Path(tmp) / "recent.json"):
                with patch("voice.actions.files.LOGS_DIR", Path(tmp)):
                    remember_saved_path(note)
                    with patch("voice.actions.files.reveal_in_explorer") as reveal:
                        path = reveal_last_file_handler(Intent("reveal_last_file"))
                        reveal.assert_called_once()
                        assert path == str(note.resolve())


def test_delete_requires_confirm_then_trashes():
    with tempfile.TemporaryDirectory() as tmp:
        note = Path(tmp) / "nota.txt"
        note.write_text("x", encoding="utf-8")
        config = {"locations": {"documentos": str(tmp)}}
        with patch("voice.actions.files.LAST_SAVED_FILE", Path(tmp) / "last.txt"):
            with patch("voice.actions.files.RECENT_FILES", Path(tmp) / "recent.json"):
                with patch("voice.actions.files.LOGS_DIR", Path(tmp)):
                    remember_saved_path(note)
                    try:
                        delete_file_handler(
                            Intent("delete_file", {"confirmed": False}), config
                        )
                        assert False, "should require confirm"
                    except ValueError:
                        pass
                    with patch("voice.actions.dialog.send_to_recycle_bin") as trash:
                        path = delete_file_handler(
                            Intent(
                                "delete_file",
                                {"confirmed": True, "path": str(note)},
                            ),
                            config,
                        )
                        trash.assert_called_once()
                        assert path == str(note.resolve())


def test_list_recent_handler():
    with tempfile.TemporaryDirectory() as tmp:
        a = Path(tmp) / "a.txt"
        b = Path(tmp) / "b.txt"
        a.write_text("1", encoding="utf-8")
        b.write_text("2", encoding="utf-8")
        with patch("voice.actions.files.LAST_SAVED_FILE", Path(tmp) / "last.txt"):
            with patch("voice.actions.files.RECENT_FILES", Path(tmp) / "recent.json"):
                with patch("voice.actions.files.LOGS_DIR", Path(tmp)):
                    remember_saved_path(a)
                    remember_saved_path(b)
                    summary = list_recent_files_handler(
                        Intent("list_recent_files"), {"recent_limit": 10}
                    )
                    assert "b.txt" in summary
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


def test_parser_new_file_commands():
    parser = IntentParser()
    assert parser.parse("mostrar onde esta o ultimo arquivo").name == "reveal_last_file"
    assert parser.parse("arquivos recentes").name == "list_recent_files"
    open_named = parser.parse("abrir lista de compras em documentos")
    assert open_named.name == "open_file"
    assert open_named.params["name"] == "lista de compras"
    assert open_named.params["location"] == "documentos"
    read_named = parser.parse("ler lista de compras em documentos")
    assert read_named.name == "read_file"
    assert read_named.params["name"] == "lista de compras"
    search = parser.parse("procurar relatorio em documentos")
    assert search.name == "search_files"
    assert search.params["query"] == "relatorio"
    assert search.params["location"] == "documentos"
    delete_last = parser.parse("apagar ultimo arquivo")
    assert delete_last.name == "delete_file"
    assert delete_last.params.get("confirmed") is False
    delete_named = parser.parse("apagar lista de compras em documentos")
    assert delete_named.name == "delete_file"
    assert delete_named.params["name"] == "lista de compras"
    dirs = parser.parse("listar pastas em downloads")
    assert dirs.name == "list_folder"
    assert dirs.params["kind"] == "dirs"
    txts = parser.parse("listar textos em documentos")
    assert txts.name == "list_folder"
    assert txts.params["kind"] == "txt"
    confirm = parser.parse_delete_confirm("confirmar")
    assert confirm.name == "delete_file"
    assert confirm.params["confirmed"] is True


def test_parser_create_and_list():
    parser = IntentParser()
    create = parser.parse("criar pasta TCC em documentos")
    assert create.name == "create_folder"
    assert create.params["name"] == "tcc"
    assert create.params["location"] == "documentos"
    listing = parser.parse("o que tem em downloads")
    assert listing.name == "list_folder"
    assert listing.params["location"] == "downloads"
    assert listing.params.get("kind", "all") == "all"


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


def test_loop_delete_confirmation_gate():
    from voice.loop import Loop

    listener = MagicMock()
    listener.last_timings = {"ms_listen": 0, "ms_stt": 0}
    parser = IntentParser()
    executor = MagicMock()
    executor.save_config = {
        "locations": {},
    }
    executor.browser_session.on_youtube = False
    loop = Loop(listener, parser, executor)
    loop.cooldown = 0

    with tempfile.TemporaryDirectory() as tmp:
        note = Path(tmp) / "nota.txt"
        note.write_text("x", encoding="utf-8")
        with patch("voice.actions.files.LAST_SAVED_FILE", Path(tmp) / "last.txt"):
            with patch("voice.actions.files.RECENT_FILES", Path(tmp) / "recent.json"):
                with patch("voice.actions.files.LOGS_DIR", Path(tmp)):
                    remember_saved_path(note)
                    intent = loop.handle_utterance("apagar ultimo arquivo")
                    assert intent is not None
                    assert intent.name == "delete_file"
                    assert loop.awaiting_delete is True
                    assert loop.pending_delete_path == note.resolve()
                    executor.execute.assert_not_called()

                    loop.handle_utterance("confirmar")
                    executor.execute.assert_called_once()
                    called = executor.execute.call_args[0][0]
                    assert called.params.get("confirmed") is True
                    assert called.params.get("path") == str(note.resolve())
                    assert loop.awaiting_delete is False


if __name__ == "__main__":
    test_sanitize_filename()
    test_save_named_to_downloads()
    test_save_to_documentos_and_project()
    test_remember_and_open_last()
    test_recent_history_keeps_n()
    test_create_and_list_folder()
    test_open_read_search_by_name()
    test_reveal_last()
    test_delete_requires_confirm_then_trashes()
    test_list_recent_handler()
    test_parser_save_named()
    test_parser_save_documentos_projeto()
    test_parser_open_read_last()
    test_parser_new_file_commands()
    test_parser_create_and_list()
    test_sanitize_dirname()
    test_save_notepad_handler_passes_name()
    test_loop_delete_confirmation_gate()
    print("Todos os testes passaram.")
