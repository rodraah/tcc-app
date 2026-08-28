"""Testes das ações de sistema (pyautogui mockado)."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.actions.system import (
    hotkey_handler,
    lock_pc_handler,
    open_a11y_handler,
    open_folder_handler,
    press_key_handler,
    run_dialog_handler,
    show_desktop_handler,
    switch_window_handler,
    volume_handler,
    window_action_handler,
    windows_search_handler,
)
from voice.models import Intent


def test_hotkey_requires_keys():
    try:
        hotkey_handler(Intent("hotkey", {}))
        assert False, "deveria falhar"
    except ValueError:
        pass


def test_hotkey_calls_pyautogui():
    with patch("voice.actions.system.pyautogui") as gui:
        hotkey_handler(Intent("hotkey", {"keys": ["ctrl", "a"]}))
        gui.hotkey.assert_called_once_with("ctrl", "a")


def test_press_key():
    with patch("voice.actions.system.pyautogui") as gui:
        press_key_handler(Intent("press_key", {"key": "enter"}))
        gui.press.assert_called_once_with("enter")


def test_window_actions_without_app_use_foreground():
    """Sem app conhecido: Win32 na janela em foco (nunca Win+Up, que faz Snap)."""
    with patch("voice.actions.system.pyautogui") as gui:
        with patch(
            "voice.actions.window.foreground_window_state", return_value=True
        ) as fg:
            assert window_action_handler(
                Intent("window_action", {"action": "maximize"})
            ) is True
            fg.assert_called_once_with("maximize")
        gui.hotkey.assert_not_called()


def test_window_action_uses_titles():
    with patch("voice.actions.window.set_window_state", return_value=True) as setter:
        ok = window_action_handler(
            Intent(
                "window_action",
                {"action": "maximize", "titles": ["notepad"]},
            )
        )
        assert ok is True
        setter.assert_called_once_with(["notepad"], "maximize")


def test_window_action_invalid():
    try:
        window_action_handler(Intent("window_action", {"action": "fly"}))
        assert False
    except ValueError:
        pass


def test_switch_window_next_and_prev():
    with patch("voice.actions.system.pyautogui") as gui:
        with patch("voice.actions.system.time.sleep"):
            switch_window_handler(Intent("switch_window", {"direction": "next"}))
            gui.hotkey.assert_called_with("alt", "tab")
            switch_window_handler(Intent("switch_window", {"direction": "prev"}))
            gui.hotkey.assert_called_with("alt", "shift", "tab")


def test_volume_up_presses_multiple():
    with patch("voice.actions.system.pyautogui") as gui:
        volume_handler(Intent("volume", {"action": "up"}))
        assert gui.press.call_count == 4
        gui.press.assert_called_with("volumeup")


def test_volume_mute_once():
    with patch("voice.actions.system.pyautogui") as gui:
        volume_handler(Intent("volume", {"action": "mute"}))
        assert gui.press.call_count == 1
        gui.press.assert_called_with("volumemute")


def test_show_desktop_and_lock():
    with patch("voice.actions.system.pyautogui") as gui:
        show_desktop_handler(Intent("show_desktop"))
        gui.hotkey.assert_called_with("win", "d")
    with patch("voice.actions.system.ctypes") as ct:
        ct.windll.user32.LockWorkStation.return_value = 1
        lock_pc_handler(Intent("lock_pc", {"confirmed": True}))
        ct.windll.user32.LockWorkStation.assert_called_once_with()


def test_open_a11y():
    with patch("voice.actions.system.subprocess.Popen") as popen:
        open_a11y_handler(Intent("open_a11y", {"app": "magnify"}))
        popen.assert_called_once()


def test_run_dialog():
    with patch("voice.actions.system.pyautogui") as gui:
        with patch("voice.actions.system.time.sleep"):
            with patch("voice.actions.keyboard.type_text") as type_text:
                run_dialog_handler(Intent("run_dialog", {"command": "notepad"}))
                gui.hotkey.assert_called_with("win", "r")
                type_text.assert_called_once_with("notepad", focus_window=False)
                gui.press.assert_called_with("enter")


def test_open_folder():
    with patch("voice.actions.system.subprocess.Popen") as popen:
        open_folder_handler(Intent("open_folder", {"path": "shell:Downloads"}))
        popen.assert_called_once()
        assert "shell:Downloads" in popen.call_args.args[0]


def test_windows_search():
    with patch("voice.actions.system.pyautogui") as gui:
        with patch("voice.actions.system.time.sleep"):
            with patch("voice.actions.keyboard.type_text") as type_text:
                windows_search_handler(
                    Intent("windows_search", {"query": "calculadora"})
                )
                gui.hotkey.assert_called_with("win", "s")
                type_text.assert_called_once_with("calculadora", focus_window=False)
                gui.press.assert_called_with("enter")


if __name__ == "__main__":
    test_hotkey_requires_keys()
    test_hotkey_calls_pyautogui()
    test_press_key()
    test_window_actions_without_app_use_foreground()
    test_window_action_uses_titles()
    test_window_action_invalid()
    test_switch_window_next_and_prev()
    test_volume_up_presses_multiple()
    test_volume_mute_once()
    test_show_desktop_and_lock()
    test_open_a11y()
    test_run_dialog()
    test_open_folder()
    test_windows_search()
    print("Todos os testes passaram.")
