import pyautogui
import pyperclip

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


def type_text(text: str, focus_window: bool = False) -> None:
    # ponytail: sem pywinauto no hot path — foco já vem do usuário; UIA trava/STA warning
    if focus_window:
        from voice.actions.window import focus_active_window

        focus_active_window()

    if text.isascii():
        pyautogui.write(text, interval=0.02)
    else:
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
