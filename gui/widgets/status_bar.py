"""Bottom status bar: gesture status display + start/stop buttons."""

import customtkinter as ctk


class StatusBar(ctk.CTkFrame):
    """Status bar at the bottom of the main window.

    Displays the current gesture, its confidence, and start/stop controls.
    """

    def __init__(self, master, on_start=None, on_stop=None, **kwargs):
        super().__init__(master, height=56, corner_radius=0, **kwargs)
        self.grid_propagate(False)

        # Gesture status label
        self.gesture_label = ctk.CTkLabel(
            self,
            text="Nenhum gesto",
            anchor="w",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.gesture_label.grid(row=0, column=0, padx=16, pady=10, sticky="w")

        # Confidence label
        self.confidence_label = ctk.CTkLabel(
            self,
            text="",
            anchor="w",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray60"),
        )
        self.confidence_label.grid(row=0, column=1, padx=8, pady=10, sticky="w")

        # Start button (primary action — soft teal/green)
        self.start_btn = ctk.CTkButton(
            self,
            text="Iniciar",
            width=96,
            height=34,
            fg_color=("#2e8b57", "#2f9e63"),
            hover_color=("#256f46", "#268a55"),
            text_color=("white", "white"),
            corner_radius=6,
            command=on_start,
        )
        self.start_btn.grid(row=0, column=2, padx=(0, 6), pady=10, sticky="e")

        # Stop button (stop action — soft terracotta/red)
        self.stop_btn = ctk.CTkButton(
            self,
            text="Parar",
            width=96,
            height=34,
            fg_color=("#c0563f", "#c95f47"),
            hover_color=("#a34834", "#b04f39"),
            text_color=("white", "white"),
            corner_radius=6,
            command=on_stop,
        )
        self.stop_btn.grid(row=0, column=3, padx=(6, 16), pady=10, sticky="e")

        self.columnconfigure(1, weight=1)

    def update_gesture(
        self, name: str, confidence: float = 0.0, origin: str = "", action: str = ""
    ):
        """Update the gesture display."""
        display = name if name else "Nenhum gesto"
        self.gesture_label.configure(text=display)

        if confidence > 0:
            suffix = f" ({origin})" if origin else ""
            action_suffix = f" → {action}" if action else ""
            self.confidence_label.configure(
                text=f"{confidence:.2f}{suffix}{action_suffix}"
            )
        else:
            self.confidence_label.configure(text="")

    def set_starting(self):
        """Disable both buttons and show a loading label while start finishes."""
        self.start_btn.configure(state="disabled", text="Carregando...")
        self.stop_btn.configure(state="disabled", text="Parar")

    def set_stopping(self):
        """Disable both buttons while stop finishes in the background."""
        self.start_btn.configure(state="disabled", text="Iniciar")
        self.stop_btn.configure(state="disabled", text="Parando...")

    def set_running(self, running: bool):
        """Enable/disable buttons based on running state."""
        if running:
            self.start_btn.configure(state="disabled", text="Iniciar")
            self.stop_btn.configure(state="normal", text="Parar")
        else:
            self.start_btn.configure(state="normal", text="Iniciar")
            self.stop_btn.configure(state="disabled", text="Parar")
