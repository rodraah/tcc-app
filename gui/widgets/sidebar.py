"""Sidebar navigation widget."""

import customtkinter as ctk


class Sidebar(ctk.CTkFrame):
    """Vertical sidebar with navigation buttons.

    Usage:
        sidebar = Sidebar(parent)
        sidebar.add_button("Camera", callback=show_camera)
        sidebar.add_button("Map", callback=show_map)
        sidebar.set_active("Camera")
    """

    BUTTON_WIDTH = 120
    BUTTON_HEIGHT = 40
    PADDING = 8
    # Frame must fit the button plus left/right padding, otherwise the
    # right border is clipped by the main content column.
    SIDEBAR_WIDTH = BUTTON_WIDTH + 2 * PADDING

    # Accent palette for the active item (light, dark)
    _ACCENT_FG = ("#2E86C1", "#1F6AA5")
    _ACCENT_HOVER = ("#2E86C1", "#1F6AA5")
    _ACCENT_BORDER = ("#2471A3", "#144870")
    _ACCENT_TEXT = ("white", "white")

    # Idle button palette (light, dark)
    _IDLE_FG = ("gray90", "gray20")
    _IDLE_HOVER = ("gray85", "gray25")
    _IDLE_BORDER = ("gray80", "gray28")
    _IDLE_TEXT = ("gray10", "gray90")

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            width=self.SIDEBAR_WIDTH,
            corner_radius=0,
            fg_color=("gray92", "gray16"),
            **kwargs,
        )
        self.grid_propagate(False)
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._active_button: str | None = None
        self._row = 0

    def add_button(self, label: str, command=None) -> ctk.CTkButton:
        """Add a navigation button to the sidebar."""
        btn = ctk.CTkButton(
            self,
            text=label,
            width=self.BUTTON_WIDTH,
            height=self.BUTTON_HEIGHT,
            corner_radius=8,
            border_width=1,
            border_color=self._IDLE_BORDER,
            fg_color=self._IDLE_FG,
            hover_color=self._IDLE_HOVER,
            text_color=self._IDLE_TEXT,
            command=command,
        )
        btn.grid(row=self._row, column=0, padx=self.PADDING, pady=8)
        self._buttons[label] = btn
        self._row += 1
        return btn

    def set_active(self, label: str):
        """Highlight the active button, un-highlight others."""
        self._active_button = label
        for name, btn in self._buttons.items():
            if name == label:
                btn.configure(
                    fg_color=self._ACCENT_FG,
                    hover_color=self._ACCENT_HOVER,
                    border_color=self._ACCENT_BORDER,
                    text_color=self._ACCENT_TEXT,
                )
            else:
                btn.configure(
                    fg_color=self._IDLE_FG,
                    hover_color=self._IDLE_HOVER,
                    border_color=self._IDLE_BORDER,
                    text_color=self._IDLE_TEXT,
                )

    def add_spacer(self):
        """Add an expanding spacer to push subsequent buttons to the bottom."""
        self._row += 1
        self.grid_rowconfigure(self._row, weight=1)
        self._row += 1