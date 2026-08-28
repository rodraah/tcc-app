"""Scrolling action/gesture log page."""

import queue
from datetime import datetime

import customtkinter as ctk


class LogPage(ctk.CTkFrame):
    """Page displaying a scrolling log of gestures and fired actions."""

    def __init__(self, master, max_lines=500, **kwargs):
        super().__init__(master, **kwargs)
        self._max_lines = max_lines
        self._paused = False
        self._log_queue: queue.Queue = queue.Queue(maxsize=100)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- Header ---
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="ew")

        ctk.CTkLabel(
            header,
            text="Log de Ações",
            font=ctk.CTkFont(size=20, weight="bold"),
            anchor="w",
        ).pack(side="left")

        self.pause_btn = ctk.CTkButton(
            header,
            text="Pausar",
            width=70,
            command=self._toggle_pause,
        )
        self.pause_btn.pack(side="right")

        ctk.CTkButton(
            header,
            text="Limpar",
            width=70,
            command=self._clear_log,
        ).pack(side="right", padx=(0, 5))

        # --- Log text area ---
        self.log_text = ctk.CTkTextbox(
            self,
            state="disabled",
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word",
        )
        self.log_text.grid(row=1, column=0, padx=20, pady=(0, 15), sticky="nsew")

        # Start polling for log entries
        self._poll_log()

    def add_entry(self, message: str, module: str = "sistema"):
        """Add a log entry. Thread-safe — can be called from any thread."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] [{module}] {message}"
        try:
            self._log_queue.put_nowait(entry)
        except queue.Full:
            pass

    def _poll_log(self):
        """Poll the log queue and append entries to the text widget."""
        try:
            while True:
                entry = self._log_queue.get_nowait()
                self._append_text(entry)
        except queue.Empty:
            pass
        self.after(100, self._poll_log)

    def _append_text(self, text: str):
        """Append a line of text to the log widget."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")

        # Trim old lines if over max
        line_count = int(self.log_text.index("end-1c").split(".")[0])
        if line_count > self._max_lines:
            self.log_text.delete("1.0", f"{line_count - self._max_lines}.0")

        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _toggle_pause(self):
        """Toggle auto-scroll pause."""
        self._paused = not self._paused
        self.pause_btn.configure(text="Retomar" if self._paused else "Pausar")

    def _clear_log(self):
        """Clear all log entries."""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
