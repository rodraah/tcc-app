"""Janelas Windows: Win32 (ctypes) para min/max/foco; pywinauto só em diálogos."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32

SW_MINIMIZE = 6
SW_MAXIMIZE = 3
SW_RESTORE = 9
GW_OWNER = 4
WM_CLOSE = 0x0010

_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def focus_active_window(title: str | None = None) -> bool:
    """Foca janela por título via Win32 (sem pywinauto)."""
    if title:
        hwnd = _find_hwnd([title])
        if not hwnd:
            return False
        user32.ShowWindow(hwnd, SW_RESTORE)
        return bool(user32.SetForegroundWindow(hwnd))
    hwnd = user32.GetForegroundWindow()
    return bool(hwnd)


def set_window_state(titles: list[str], action: str) -> bool:
    """Minimiza/maximiza/restaura/fecha por título parcial (inclui minimizadas)."""
    if not titles:
        return False
    hwnd = _find_hwnd(titles)
    if not hwnd:
        return False
    return _apply_state(hwnd, action)


def foreground_window_state(action: str) -> bool:
    """Mesma ação na janela em foco, via Win32 (Win+Up dispara Snap no Win11)."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False
    return _apply_state(int(hwnd), action)


def _apply_state(hwnd: int, action: str) -> bool:
    if action == "minimize":
        user32.ShowWindow(hwnd, SW_MINIMIZE)
    elif action == "maximize":
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.ShowWindow(hwnd, SW_MAXIMIZE)
        user32.SetForegroundWindow(hwnd)
    elif action == "restore":
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
    elif action == "close":
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    else:
        return False
    return True


def _find_hwnd(titles: list[str]) -> int | None:
    terms = [t.lower() for t in titles if t]
    if not terms:
        return None
    for hwnd, title in _iter_top_level_windows():
        low = title.lower()
        matched = next((term for term in terms if term in low), None)
        if not matched:
            continue
        if not _is_main_window(low, matched):
            continue
        return hwnd
    return None


# Janelas auxiliares que carregam o nome do processo no título e não são a UI real.
_HELPER_TITLE_MARKERS = ("gdi+ window", "dde server window", "desktopwindowxamlsource")


def _iter_top_level_windows() -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []

    def callback(hwnd: int, _lparam: int) -> bool:
        if user32.GetWindow(hwnd, GW_OWNER):
            return True
        if not user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()
        if not title:
            return True
        if any(marker in title.lower() for marker in _HELPER_TITLE_MARKERS):
            return True
        found.append((int(hwnd), title))
        return True

    user32.EnumWindows(_WNDENUMPROC(callback), 0)
    return found


def close_window_by_titles(titles: list[str]) -> bool:
    """Fecha janela cujo título contém um dos termos informados."""
    if set_window_state(titles, "close"):
        return True
    try:
        from pywinauto import Desktop

        desktop = Desktop(backend="uia")
        candidates = []
        for win in desktop.windows(visible_only=True):
            win_title = win.window_text().lower()
            for term in titles:
                if term.lower() in win_title and _is_main_window(win_title, term):
                    candidates.append(win)
                    break

        for win in candidates:
            if _has_editor_area(win):
                win.close()
                return True

        if candidates:
            candidates[0].close()
            return True
    except Exception:
        pass
    return False


def _has_editor_area(win) -> bool:
    try:
        for ctrl_type in ("Document", "Edit"):
            if win.descendants(control_type=ctrl_type):
                return True
    except Exception:
        pass
    return False


def _is_main_window(win_title: str, term: str) -> bool:
    if term.lower() not in win_title:
        return False
    dialog_markers = ("salvar como", "save as", "confirmar")
    return not any(marker in win_title for marker in dialog_markers)


def _iter_confirm_save_dialogs():
    from pywinauto import Desktop

    desktop = Desktop(backend="uia")
    for win in desktop.windows(visible_only=True):
        title = win.window_text().lower()
        if any(skip in title for skip in ("gerenciador de tarefas", "task manager")):
            continue
        try:
            buttons = win.descendants(control_type="Button")
        except Exception:
            continue
        if not buttons:
            continue
        labels = [b.window_text().lower().strip() for b in buttons]
        if _looks_like_confirm_save_dialog(labels):
            yield win, buttons


def _looks_like_confirm_save_dialog(button_labels: list[str]) -> bool:
    has_save = any("salvar" in lb or lb == "save" for lb in button_labels)
    has_cancel = any("cancel" in lb for lb in button_labels)
    has_discard = any("nao salvar" in lb or "don't save" in lb for lb in button_labels)
    return has_save and has_cancel and has_discard


def is_confirm_save_dialog_open() -> bool:
    try:
        return next(_iter_confirm_save_dialogs(), None) is not None
    except Exception:
        return False


def is_save_dialog_open() -> bool:
    return is_confirm_save_dialog_open()


DIALOG_BUTTON_LABELS = {
    "save": ["salvar", "save"],
    "discard": ["nao salvar", "don't save", "dont save", "do not save"],
    "cancel": ["cancelar", "cancel"],
}


def click_dialog_choice(choice: str) -> bool:
    """Clica em Salvar, Não salvar ou Cancelar no diálogo de confirmação."""
    labels = DIALOG_BUTTON_LABELS.get(choice, [])
    if not labels:
        return False

    try:
        from rapidfuzz import fuzz

        for win, buttons in _iter_confirm_save_dialogs():
            win.set_focus()
            for btn in buttons:
                text = btn.window_text().lower().strip()
                for label in labels:
                    if label in text or fuzz.ratio(label, text) >= 80:
                        btn.click()
                        return True
    except Exception:
        pass
    return False
