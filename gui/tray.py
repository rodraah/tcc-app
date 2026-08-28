"""System tray icon for the TCC-App.

Hides the main window to the tray on action fire; context menu offers
Show / Quit.  All GUI touches go through ``app.after(0, ...)``.
"""

import threading

import pystray
from PIL import Image, ImageDraw


def _create_icon_image(size: int = 64) -> Image.Image:
    """Return a simple solid-circle PIL image for the tray icon."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Draw a filled circle (dark grey on transparent)
    draw.ellipse(
        [4, 4, size - 4, size - 4],
        fill=(50, 50, 50, 255),
        outline=(200, 200, 200, 255),
        width=2,
    )
    return img


class TrayIcon:
    """System tray icon that hides/shows the main window."""

    def __init__(self, app):
        """app: the App instance from gui.app"""
        self._app = app
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Start the tray icon in a daemon thread."""
        menu = pystray.Menu(
            pystray.MenuItem("Mostrar", self._on_show, default=True),
            pystray.MenuItem("Sair", self._on_quit),
        )
        self._icon = pystray.Icon(
            "TCC-App",
            _create_icon_image(),
            "TCC-App — Controle por Gestos e Voz",
            menu,
        )
        self._thread = threading.Thread(
            target=self._icon.run, daemon=True, name="tray-icon"
        )
        self._thread.start()

    def hide_app(self):
        """Hide the main window (called when an action fires).

        Must use ``app.after(0, app.withdraw)`` for thread safety.
        """
        self._app.after(0, self._app.withdraw)

    def stop(self):
        """Stop the tray icon."""
        if self._icon is not None:
            self._icon.stop()
            self._icon = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    # ------------------------------------------------------------------
    # Internal callbacks (run on the tray thread)
    # ------------------------------------------------------------------

    def _on_show(self, icon, item):
        """Restore the main window via thread-safe scheduling."""
        self._app.after(0, self._app.deiconify)

    def _on_quit(self, icon, item):
        """Fully quit the application."""
        self._app.after(0, self._app.quit_app)
