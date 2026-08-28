"""Push-to-talk: toggle escuta com Ctrl+Shift+Space.

Lazy-imports pynput so the rest of the package never hard-depends on it.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from voice.logger import setup_logging

if TYPE_CHECKING:
    from voice.listener import HybridListener


class PushToTalk:
    """Toggle escuta com Ctrl+Shift+Space."""

    def __init__(self, listener: HybridListener) -> None:
        self._hybrid_listener = listener
        self._logger = setup_logging()
        self._listener: object | None = None  # pynput keyboard.Listener (lazy)
        self._hotkey: object | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start listening for the hotkey. No-op if already running."""
        if self._running:
            return

        from pynput import keyboard  # lazy import (W13)

        self._hotkey = keyboard.HotKey(
            keyboard.HotKey.parse("<ctrl>+<shift>+<space>"),
            self._toggle,
        )

        def _on_press(key: keyboard.Key | keyboard.KeyCode) -> None:
            try:
                self._hotkey.press(key)  # type: ignore[union-attr]
            except (AttributeError, TypeError):
                pass

        def _on_release(key: keyboard.Key | keyboard.KeyCode) -> None:
            try:
                self._hotkey.release(key)  # type: ignore[union-attr]
            except (AttributeError, TypeError):
                pass

        listener = keyboard.Listener(on_press=_on_press, on_release=_on_release)
        listener.daemon = True
        listener.start()
        self._listener = listener
        self._running = True
        self._logger.info("Push-to-talk: Ctrl+Shift+Space")

    def stop(self) -> None:
        """Stop the pynput keyboard listener. No-op if not started."""
        if not self._running:
            return
        if self._listener is not None and self._listener.is_alive():  # type: ignore[union-attr]
            self._listener.stop()  # type: ignore[union-attr]
            self._listener.join(timeout=2.0)  # type: ignore[union-attr]
        self._listener = None
        self._hotkey = None
        self._running = False

    @property
    def enabled(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _toggle(self) -> None:
        self._hybrid_listener.set_paused(not self._hybrid_listener.paused)
