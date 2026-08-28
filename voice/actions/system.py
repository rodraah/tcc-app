"""Atalhos de teclado e ações de sistema Windows."""

from __future__ import annotations

import ctypes
import subprocess
import time

import pyautogui

from voice.models import Intent


def hotkey_handler(intent: Intent) -> None:
    keys = intent.params.get("keys")
    if not keys:
        raise ValueError("Parâmetro 'keys' ausente.")
    pyautogui.hotkey(*[str(k) for k in keys])


def press_key_handler(intent: Intent) -> None:
    key = intent.params.get("key")
    if not key:
        raise ValueError("Parâmetro 'key' ausente.")
    pyautogui.press(str(key))


def window_action_handler(intent: Intent, close_config: dict | None = None) -> bool:
    """Ação de janela via Win32; Win+Up/Down cai no Snap do Win11, então não usamos."""
    action = intent.params.get("action")
    if action not in ("minimize", "maximize", "restore", "close"):
        raise ValueError(f"Ação de janela inválida: {action}")

    titles = list(intent.params.get("titles") or [])
    app = intent.params.get("app")
    if not titles and app and close_config:
        titles = list((close_config.get(app) or {}).get("titles") or [])

    from voice.actions.window import foreground_window_state, set_window_state

    if titles and set_window_state(titles, action):
        return True
    return foreground_window_state(action)


def switch_window_handler(intent: Intent) -> None:
    direction = intent.params.get("direction", "next")
    if direction == "prev":
        pyautogui.hotkey("alt", "shift", "tab")
    else:
        pyautogui.hotkey("alt", "tab")
    time.sleep(0.15)
    pyautogui.press("enter")


def volume_handler(intent: Intent) -> None:
    action = intent.params.get("action")
    key_map = {
        "up": "volumeup",
        "down": "volumedown",
        "mute": "volumemute",
        "unmute": "volumemute",
    }
    key = key_map.get(action)
    if not key:
        raise ValueError(f"Ação de volume inválida: {action}")
    presses = 4 if action in ("up", "down") else 1
    for _ in range(presses):
        pyautogui.press(key)


def show_desktop_handler(intent: Intent) -> None:
    pyautogui.hotkey("win", "d")


def lock_pc_handler(intent: Intent) -> None:
    # Win+L simulado (pyautogui) é ignorado pelo Windows; LockWorkStation é a API certa.
    if not ctypes.windll.user32.LockWorkStation():
        raise OSError("LockWorkStation falhou.")


def open_a11y_handler(intent: Intent) -> None:
    app = intent.params.get("app")
    if not app:
        raise ValueError("Parâmetro 'app' ausente.")
    subprocess.Popen(str(app), shell=True)


def run_dialog_handler(intent: Intent) -> None:
    command = intent.params.get("command")
    if not command:
        raise ValueError("Parâmetro 'command' ausente.")
    pyautogui.hotkey("win", "r")
    time.sleep(0.25)
    from voice.actions.keyboard import type_text

    type_text(str(command), focus_window=False)
    pyautogui.press("enter")


def focus_app_handler(intent: Intent, close_config: dict | None = None) -> bool:
    from voice.actions.window import focus_active_window

    app = intent.params.get("app")
    titles = intent.params.get("titles")
    if not titles and app and close_config:
        titles = (close_config.get(app) or {}).get("titles", [])
    if not titles and app:
        titles = [str(app)]
    for title in titles or []:
        if focus_active_window(str(title)):
            return True
    return False


def open_folder_handler(intent: Intent) -> None:
    """Abre pasta conhecida via shell: (localizado no Explorer)."""
    target = intent.params.get("path")
    if not target:
        raise ValueError("Parâmetro 'path' ausente.")
    # shell:Downloads etc. — explorer interpreta o GUID localizado.
    subprocess.Popen(f'explorer "{target}"', shell=True)


def windows_search_handler(intent: Intent) -> None:
    """Abre a busca do Windows (Win+S) e digita a query."""
    query = intent.params.get("query")
    if not query:
        raise ValueError("Parâmetro 'query' ausente.")
    pyautogui.hotkey("win", "s")
    time.sleep(0.35)
    from voice.actions.keyboard import type_text

    type_text(str(query), focus_window=False)
    pyautogui.press("enter")
