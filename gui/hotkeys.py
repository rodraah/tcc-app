"""Global hotkey listener for the TCC-App.

Registers a system-wide hotkey (default F9) that toggles the main window
visibility.  The listener runs in a daemon thread; all GUI updates go
through ``app.after(0, ...)``.
"""

import threading

import keyboard


class HotkeyListener:
    """Global hotkey listener for F9 toggle."""

    def __init__(self, app, hotkey="F9"):
        """app: the App instance; hotkey: key combo string (default "F9")"""
        self._app = app
        self._hotkey = hotkey
        self._thread: threading.Thread | None = None
        self._hotkey_registered = None  # return value from keyboard.add_hotkey

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Start the hotkey listener in a daemon thread."""

        def _listener_loop():
            self._hotkey_registered = keyboard.add_hotkey(
                self._hotkey, self._toggle_visibility
            )
            keyboard.wait()  # blocks until the thread is killed

        self._thread = threading.Thread(
            target=_listener_loop,
            daemon=True,
            name="hotkey-listener",
        )
        self._thread.start()

    def stop(self):
        """Stop listening."""
        if self._hotkey_registered is not None:
            keyboard.remove_hotkey(self._hotkey_registered)
            self._hotkey_registered = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    # ------------------------------------------------------------------
    # Internal callback (runs on the hotkey thread)
    # ------------------------------------------------------------------

    def _toggle_visibility(self):
        """Toggle main window visibility (thread-safe via app.after)."""

        def _do_toggle():
            if self._app.winfo_viewable():
                self._app.withdraw()
            else:
                self._app.show_and_start()

        self._app.after(0, _do_toggle)
