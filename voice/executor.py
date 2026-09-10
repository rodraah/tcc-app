from typing import Callable, Optional

from voice.actions.browser import (
    browser_back_handler,
    browser_click_link_handler,
    browser_click_role_handler,
    browser_click_text_handler,
    browser_close_tab_handler,
    browser_find_handler,
    browser_forward_handler,
    browser_goto_handler,
    browser_new_tab_handler,
    browser_open_handler,
    browser_refresh_handler,
    browser_scroll_handler,
    browser_search_handler,
    browser_switch_tab_handler,
    browser_youtube_handler,
    browser_zoom_handler,
)
from voice.actions.close_app import close_app_handler
from voice.actions.dialog import (
    create_folder_handler,
    dialog_choice_handler,
    list_folder_handler,
    open_last_file_handler,
    read_last_file_handler,
    save_notepad_handler,
)
from voice.actions.open_app import open_app_handler
from voice.actions.system import (
    focus_app_handler,
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
from voice.actions.type_text import type_text_handler
from voice.browser_session import BrowserSession
from voice.logger import setup_logging
from voice.models import Intent
from voice.tts import speak_async


class Executor:
    def __init__(
        self,
        config: dict | None = None,
        on_error: Optional[Callable[[Exception, str], None]] = None,
    ) -> None:
        self.logger = setup_logging()
        self.config = config or {}
        self.close_config = self.config.get("app_close", {})
        self.save_config = self.config.get("save", {})
        self.tts_enabled = self.config.get("tts", {}).get("enabled", True)
        self.browser_session = BrowserSession(self.config)
        self.last_intent: Intent | None = None
        self._last_window_app: str | None = None
        self._on_error = on_error
        self._handlers = {
            "open_app": self._open_app,
            "close_app": self._close_app,
            "dialog_choice": self._dialog_choice,
            "save_notepad": self._save_notepad,
            "open_last_file": self._open_last_file,
            "read_last_file": self._read_last_file,
            "create_folder": self._create_folder,
            "list_folder": self._list_folder,
            "open_url": self._open_url,
            "type_text": type_text_handler,
            "browser_open": self._browser_open,
            "browser_search": self._browser_search,
            "browser_click_link": self._browser_click_link,
            "browser_click_text": self._browser_click_text,
            "browser_back": self._browser_back,
            "browser_forward": self._browser_forward,
            "browser_refresh": self._browser_refresh,
            "browser_new_tab": self._browser_new_tab,
            "browser_close_tab": self._browser_close_tab,
            "browser_scroll": self._browser_scroll,
            "browser_zoom": self._browser_zoom,
            "browser_switch_tab": self._browser_switch_tab,
            "browser_goto": self._browser_goto,
            "browser_find": self._browser_find,
            "browser_click_role": self._browser_click_role,
            "browser_youtube": self._browser_youtube,
            "hotkey": hotkey_handler,
            "press_key": press_key_handler,
            "window_action": self._window_action,
            "switch_window": switch_window_handler,
            "focus_app": self._focus_app,
            "volume": volume_handler,
            "show_desktop": show_desktop_handler,
            "lock_pc": lock_pc_handler,
            "open_a11y": open_a11y_handler,
            "run_dialog": run_dialog_handler,
            "open_folder": open_folder_handler,
            "windows_search": windows_search_handler,
            "help": self._help,
            "repeat_last": self._repeat_last,
            "cancel": self._cancel,
        }

    def speak(self, text: str) -> None:
        speak_async(text, enabled=self.tts_enabled)

    def _open_app(self, intent: Intent) -> None:
        app = intent.params.get("app")
        if app:
            self._last_window_app = app
        open_app_handler(intent)

    def _window_action(self, intent: Intent) -> bool:
        params = dict(intent.params)
        app = params.get("app") or self._last_window_app
        if app and not params.get("titles"):
            params["titles"] = (self.close_config.get(app) or {}).get("titles", [])
            params["app"] = app
        if app:
            self._last_window_app = app
        return window_action_handler(Intent("window_action", params), self.close_config)

    def _close_app(self, intent: Intent) -> bool:
        return close_app_handler(intent, self.close_config)

    def _dialog_choice(self, intent: Intent) -> str | None:
        saved_path = dialog_choice_handler(intent, self.save_config)
        if saved_path:
            self.logger.info(f"Salvo em: {saved_path}")
        return saved_path

    def _save_notepad(self, intent: Intent) -> str:
        saved_path = save_notepad_handler(intent, self.save_config)
        self.logger.info(f"Salvo em: {saved_path}")
        return saved_path

    def _open_last_file(self, intent: Intent) -> str:
        path = open_last_file_handler(intent)
        self.logger.info(f"Aberto: {path}")
        return path

    def _read_last_file(self, intent: Intent) -> str:
        text = read_last_file_handler(intent)
        self.logger.info("Lendo último arquivo salvo")
        return text

    def _create_folder(self, intent: Intent) -> str:
        path = create_folder_handler(intent, self.save_config)
        self.logger.info(f"Pasta criada: {path}")
        return path

    def _list_folder(self, intent: Intent) -> str:
        summary = list_folder_handler(intent, self.save_config)
        self.logger.info(summary)
        return summary

    def _open_url(self, intent: Intent) -> None:
        url = intent.params.get("url")
        if not url:
            raise ValueError("Parâmetro 'url' ausente.")
        # Abre direto no destino — start() sem URL ia pro Bing (default) antes.
        if not self.browser_session.is_active:
            self.browser_session.start(str(url))
        else:
            self.browser_session.navigate(str(url))

    def _browser_open(self, intent: Intent) -> None:
        browser_open_handler(intent, self.browser_session)

    def _browser_search(self, intent: Intent) -> None:
        browser_search_handler(intent, self.browser_session)

    def _browser_click_link(self, intent: Intent) -> None:
        browser_click_link_handler(intent, self.browser_session)

    def _browser_click_text(self, intent: Intent) -> None:
        browser_click_text_handler(intent, self.browser_session)

    def _browser_back(self, intent: Intent) -> None:
        browser_back_handler(intent, self.browser_session)

    def _browser_forward(self, intent: Intent) -> None:
        browser_forward_handler(intent, self.browser_session)

    def _browser_refresh(self, intent: Intent) -> None:
        browser_refresh_handler(intent, self.browser_session)

    def _browser_new_tab(self, intent: Intent) -> None:
        browser_new_tab_handler(intent, self.browser_session)

    def _browser_close_tab(self, intent: Intent) -> None:
        browser_close_tab_handler(intent, self.browser_session)

    def _browser_scroll(self, intent: Intent) -> None:
        browser_scroll_handler(intent, self.browser_session)

    def _browser_zoom(self, intent: Intent) -> None:
        browser_zoom_handler(intent, self.browser_session)

    def _browser_switch_tab(self, intent: Intent) -> None:
        browser_switch_tab_handler(intent, self.browser_session)

    def _browser_goto(self, intent: Intent) -> None:
        browser_goto_handler(intent, self.browser_session)

    def _browser_find(self, intent: Intent) -> None:
        browser_find_handler(intent, self.browser_session)

    def _browser_click_role(self, intent: Intent) -> None:
        browser_click_role_handler(intent, self.browser_session)

    def _browser_youtube(self, intent: Intent) -> None:
        browser_youtube_handler(intent, self.browser_session)

    def _focus_app(self, intent: Intent) -> bool:
        return focus_app_handler(intent, self.close_config)

    def _help(self, intent: Intent) -> str:
        summary = (
            "Abrir apps e pastas, busca windows, digitar, "
            "navegador com abas e youtube, volume e ajuda."
        )
        self.speak(summary)
        return summary

    def _repeat_last(self, intent: Intent) -> bool | str | None:
        if not self.last_intent or self.last_intent.name == "repeat_last":
            self.speak("Nenhum comando anterior.")
            return None
        return self.execute(self.last_intent, record=False)

    def _cancel(self, intent: Intent) -> None:
        self.speak("Cancelado.")

    def execute(
        self, intent: Intent, record: bool = True
    ) -> bool | str | None:
        handler = self._handlers.get(intent.name)
        if not handler:
            self.logger.warning(f"Intent desconhecida: {intent.name}")
            return None

        try:
            result = handler(intent)
            self.logger.info(f"Ação executada: {intent.name} {intent.params}")
            if record and intent.name not in ("repeat_last", "cancel", "help"):
                self.last_intent = intent
            return result
        except Exception as exc:
            self.logger.error(f"Erro ao executar {intent.name}: {exc}")
            self.speak(f"Erro: {exc}")
            if self._on_error:
                try:
                    self._on_error(exc, "execute")
                except Exception:
                    self.logger.exception("on_error callback failed")
            return None

    def shutdown(self) -> None:
        self.browser_session.close()
