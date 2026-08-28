"""Bottom status bar: gesture status display + start/stop buttons."""

import customtkinter as ctk


class StatusBar(ctk.CTkFrame):
    """Status bar at the bottom of the main window.

    Displays the current gesture, its confidence, and start/stop controls.
    """

    def __init__(self, master, on_start=None, on_stop=None, **kwargs):
        super().__init__(master, height=50, corner_radius=0, **kwargs)
        self.grid_propagate(False)

        # Gesture status label
        self.gesture_label = ctk.CTkLabel(
            self,
            text="Nenhum gesto",
            anchor="w",
            font=ctk.CTkFont(size=14),
        )
        self.gesture_label.grid(row=0, column=0, padx=15, pady=10, sticky="w")

        # Confidence label
        self.confidence_label = ctk.CTkLabel(
            self,
            text="",
            anchor="w",
            font=ctk.CTkFont(size=12),
            text_color="gray60",
        )
        self.confidence_label.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        # Start button
        self.start_btn = ctk.CTkButton(
            self,
            text="Iniciar",
            width=80,
            height=30,
            fg_color="green",
            hover_color="darkgreen",
            command=on_start,
        )
        self.start_btn.grid(row=0, column=2, padx=5, pady=10, sticky="e")

        # Stop button
        self.stop_btn = ctk.CTkButton(
            self,
            text="Parar",
            width=80,
            height=30,
            fg_color="red",
            hover_color="darkred",
            command=on_stop,
        )
        self.stop_btn.grid(row=0, column=3, padx=5, pady=10, sticky="e")

        self.columnconfigure(1, weight=1)

    def update_gesture(self, name: str, confidence: float = 0.0, origin: str = ""):
        """Update the gesture display."""
        display = name if name else "Nenhum gesto"
        self.gesture_label.configure(text=display)

        if confidence > 0:
            suffix = f" ({origin})" if origin else ""
            self.confidence_label.configure(text=f"{confidence:.2f}{suffix}")
        else:
            self.confidence_label.configure(text="")

    def set_running(self, running: bool):
        """Enable/disable buttons based on running state."""
        if running:
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
        else:
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
