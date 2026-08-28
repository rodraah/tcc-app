"""Testes Win32 de janela (sem pywinauto no hot path)."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.actions import window as window_mod


def test_set_window_state_empty_titles():
    assert window_mod.set_window_state([], "minimize") is False


def test_set_window_state_minimize_calls_showwindow():
    with patch.object(window_mod, "_find_hwnd", return_value=42):
        with patch.object(window_mod.user32, "ShowWindow") as show:
            assert window_mod.set_window_state(["notepad"], "minimize") is True
            show.assert_called_once_with(42, window_mod.SW_MINIMIZE)


def test_set_window_state_maximize_restore_then_max():
    with patch.object(window_mod, "_find_hwnd", return_value=7):
        with patch.object(window_mod.user32, "ShowWindow") as show:
            with patch.object(window_mod.user32, "SetForegroundWindow"):
                assert window_mod.set_window_state(["bloco"], "maximize") is True
                assert show.call_args_list[0].args == (7, window_mod.SW_RESTORE)
                assert show.call_args_list[1].args == (7, window_mod.SW_MAXIMIZE)


def test_find_hwnd_matches_partial_title():
    with patch.object(
        window_mod,
        "_iter_top_level_windows",
        return_value=[(1, "Sem título - Bloco de Notas"), (2, "Chrome")],
    ):
        assert window_mod._find_hwnd(["bloco de notas", "notepad"]) == 1


def test_find_hwnd_skips_save_as_dialog():
    with patch.object(
        window_mod,
        "_iter_top_level_windows",
        return_value=[(9, "Salvar como - Bloco de Notas")],
    ):
        assert window_mod._find_hwnd(["bloco de notas"]) is None


def test_find_hwnd_matches_english_title():
    """UI em inglês: 'Untitled - Notepad' precisa casar pelo termo 'notepad'."""
    with patch.object(
        window_mod,
        "_iter_top_level_windows",
        return_value=[(5, "Untitled - Notepad")],
    ):
        assert window_mod._find_hwnd(["bloco de notas", "notepad"]) == 5


def test_helper_windows_are_filtered():
    titles = [t for _, t in window_mod._iter_top_level_windows()]
    assert not any("GDI+ Window" in t for t in titles)
    assert not any("DDE Server Window" in t for t in titles)


def test_foreground_window_state_uses_foreground_hwnd():
    with patch.object(window_mod.user32, "GetForegroundWindow", return_value=99):
        with patch.object(window_mod, "_apply_state", return_value=True) as apply:
            assert window_mod.foreground_window_state("minimize") is True
            apply.assert_called_once_with(99, "minimize")


def test_foreground_window_state_no_window():
    with patch.object(window_mod.user32, "GetForegroundWindow", return_value=0):
        assert window_mod.foreground_window_state("minimize") is False


if __name__ == "__main__":
    test_set_window_state_empty_titles()
    test_set_window_state_minimize_calls_showwindow()
    test_set_window_state_maximize_restore_then_max()
    test_find_hwnd_matches_partial_title()
    test_find_hwnd_skips_save_as_dialog()
    test_find_hwnd_matches_english_title()
    test_helper_windows_are_filtered()
    test_foreground_window_state_uses_foreground_hwnd()
    test_foreground_window_state_no_window()
    print("Todos os testes passaram.")
