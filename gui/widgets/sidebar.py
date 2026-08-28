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

    BUTTON_WIDTH = 140
    BUTTON_HEIGHT = 40
    PADDING = 10

    def __init__(self, master, **kwargs):
        super().__init__(master, width=self.BUTTON_WIDTH, corner_radius=0, **kwargs)
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
            corner_radius=4,
            command=command,
            text_color=("gray10", "gray90"),
        )
        btn.grid(row=self._row, column=0, padx=self.PADDING, pady=4)
        self._buttons[label] = btn
        self._row += 1
        return btn

    def set_active(self, label: str):
        """Highlight the active button, un-highlight others."""
        self._active_button = label
        for name, btn in self._buttons.items():
            if name == label:
                btn.configure(fg_color=("gray75", "gray30"), text_color=("gray10", "gray90"))
            else:
                btn.configure(fg_color=("gray90", "gray20"), text_color=("gray10", "gray90"))

    def add_spacer(self):
        """Add an expanding spacer to push subsequent buttons to the bottom."""
        self._row += 1
        self.grid_rowconfigure(self._row, weight=1)
        self._row += 1
