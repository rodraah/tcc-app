"""Testes do Executor (handlers, repeat, cancel) sem UI real."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.executor import Executor
from voice.intent_parser import IntentParser
from voice.models import Intent


def _executor() -> Executor:
    config = IntentParser().config
    config = {**config, "tts": {"enabled": False}}
    return Executor(config)


def test_handlers_cover_roadmap_intents():
    ex = _executor()
    required = {
        "hotkey",
        "press_key",
        "window_action",
        "switch_window",
        "focus_app",
        "volume",
        "show_desktop",
        "lock_pc",
        "open_a11y",
        "run_dialog",
        "help",
        "repeat_last",
        "cancel",
        "browser_forward",
        "browser_refresh",
        "browser_new_tab",
        "browser_close_tab",
        "browser_click_text",
        "browser_zoom",
        "browser_switch_tab",
        "browser_goto",
        "browser_find",
        "browser_click_role",
        "browser_youtube",
        "open_folder",
        "windows_search",
    }
    assert required <= set(ex._handlers)


def test_execute_hotkey_delegates():
    ex = _executor()
    with patch("voice.actions.system.pyautogui") as gui:
        ex.execute(Intent("hotkey", {"keys": ["ctrl", "c"]}))
        gui.hotkey.assert_called_once_with("ctrl", "c")


def test_repeat_last_replays():
    ex = _executor()
    with patch("voice.actions.system.pyautogui") as gui:
        ex.execute(Intent("hotkey", {"keys": ["ctrl", "v"]}))
        gui.hotkey.reset_mock()
        ex.execute(Intent("repeat_last"))
        gui.hotkey.assert_called_once_with("ctrl", "v")


def test_repeat_last_empty():
    ex = _executor()
    assert ex.execute(Intent("repeat_last")) is None


def test_cancel_clears_without_error():
    ex = _executor()
    assert ex.execute(Intent("cancel")) is None


def test_help_returns_summary():
    ex = _executor()
    result = ex.execute(Intent("help"))
    assert isinstance(result, str)
    assert "apps" in result.lower() or "digitar" in result.lower()


def test_browser_handlers_call_session():
    ex = _executor()
    session = MagicMock()
    ex.browser_session = session
    ex.execute(Intent("browser_forward"))
    session.go_forward.assert_called_once()
    ex.execute(Intent("browser_refresh"))
    session.refresh.assert_called_once()
    ex.execute(Intent("browser_new_tab"))
    session.new_tab.assert_called_once()
    ex.execute(Intent("browser_close_tab"))
    session.close_tab.assert_called_once()
    ex.execute(Intent("browser_zoom", {"direction": "in"}))
    session.zoom.assert_called_once_with("in")
    ex.execute(Intent("browser_click_text", {"text": "foo"}))
    session.click_text.assert_called_once_with("foo")
    ex.execute(Intent("browser_switch_tab", {"direction": "next"}))
    session.switch_tab.assert_called_once_with(
        direction="next", index=None, title=None
    )
    ex.execute(Intent("browser_goto", {"url": "github.com"}))
    session.navigate.assert_called_once_with("https://github.com")
    ex.execute(Intent("browser_find", {"text": "x"}))
    session.find_in_page.assert_called_once_with("x")
    ex.execute(Intent("browser_click_role", {"role": "button", "name": "ok"}))
    session.click_role.assert_called_once_with("button", "ok")
    ex.execute(Intent("browser_youtube", {"action": "play_pause"}))
    session.youtube.assert_called_once_with("play_pause")


def test_open_url_starts_with_target():
    """'abrir youtube' não deve abrir Bing antes."""
    ex = _executor()
    session = MagicMock()
    session.is_active = False
    ex.browser_session = session
    ex.execute(Intent("open_url", {"url": "https://www.youtube.com"}))
    session.start.assert_called_once_with("https://www.youtube.com")
    session.navigate.assert_not_called()


def test_open_url_navigates_when_already_open():
    ex = _executor()
    session = MagicMock()
    session.is_active = True
    ex.browser_session = session
    ex.execute(Intent("open_url", {"url": "https://www.youtube.com"}))
    session.start.assert_not_called()
    session.navigate.assert_called_once_with("https://www.youtube.com")


def test_unknown_intent_returns_none():
    ex = _executor()
    assert ex.execute(Intent("nao_existe")) is None


def test_default_stt_engine_is_google():
    assert IntentParser().config["stt"]["engine"] == "google"


if __name__ == "__main__":
    test_handlers_cover_roadmap_intents()
    test_execute_hotkey_delegates()
    test_repeat_last_replays()
    test_repeat_last_empty()
    test_cancel_clears_without_error()
    test_help_returns_summary()
    test_browser_handlers_call_session()
    test_open_url_starts_with_target()
    test_open_url_navigates_when_already_open()
    test_unknown_intent_returns_none()
    test_default_stt_engine_is_google()
    print("Todos os testes passaram.")
