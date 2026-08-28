"""Camera page: live video feed + gesture/voice status overlay."""

import customtkinter as ctk

from gui.widgets.video_feed import VideoFeed


class CameraPage(ctk.CTkFrame):
    """Page displaying the live camera feed with gesture and voice status."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- Header ---
        header = ctk.CTkLabel(
            self,
            text="Câmera e Reconhecimento",
            font=ctk.CTkFont(size=20, weight="bold"),
            anchor="w",
        )
        header.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="w")

        # --- Video feed ---
        self.video_feed = VideoFeed(self, width=640, height=480)
        self.video_feed.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")

        # --- Status overlays ---
        overlay = ctk.CTkFrame(self, fg_color="transparent")
        overlay.grid(row=2, column=0, padx=20, pady=(0, 15), sticky="ew")

        # Gesture status
        self.gesture_frame = ctk.CTkFrame(overlay)
        self.gesture_frame.pack(side="left", padx=(0, 10), fill="x", expand=True)
        ctk.CTkLabel(
            self.gesture_frame, text="Gesto", font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w", padx=10, pady=(5, 0))
        self.gesture_name = ctk.CTkLabel(
            self.gesture_frame, text="--", font=ctk.CTkFont(size=16)
        )
        self.gesture_name.pack(anchor="w", padx=10, pady=(0, 5))
        self.gesture_origin = ctk.CTkLabel(
            self.gesture_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="gray60",
        )
        self.gesture_origin.pack(anchor="w", padx=10, pady=(0, 5))

        # Voice status (placeholder)
        self.voice_frame = ctk.CTkFrame(overlay)
        self.voice_frame.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            self.voice_frame, text="Voz", font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w", padx=10, pady=(5, 0))
        self.voice_status = ctk.CTkLabel(
            self.voice_frame, text="Não conectado", font=ctk.CTkFont(size=14)
        )
        self.voice_status.pack(anchor="w", padx=10, pady=(0, 5))
        self.voice_command = ctk.CTkLabel(
            self.voice_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="gray60",
        )
        self.voice_command.pack(anchor="w", padx=10, pady=(0, 5))

        # Recognized speech transcript — single-line field, distinct styling
        self.voice_transcript_frame = ctk.CTkFrame(
            self.voice_frame, border_width=1, border_color="gray40"
        )
        self.voice_transcript_frame.pack(
            anchor="w", padx=10, pady=(0, 5), fill="x"
        )
        self.voice_transcript = ctk.CTkLabel(
            self.voice_transcript_frame,
            text="Aguardando fala...",
            font=ctk.CTkFont(size=15),
            anchor="w",
        )
        self.voice_transcript.pack(fill="x", padx=8, pady=4)

    # --- Public update methods (called from main thread via after()) ---

    def update_gesture(self, name: str, confidence: float = 0.0, origin: str = ""):
        """Update the gesture display."""
        self.gesture_name.configure(text=name if name else "--")
        if confidence > 0 and origin:
            self.gesture_origin.configure(text=f"{confidence:.2f} ({origin})")
        else:
            self.gesture_origin.configure(text="")

    def update_voice(self, status: str, command: str = ""):
        """Update the voice status display."""
        self.voice_status.configure(text=status)
        self.voice_command.configure(text=command)

    def update_voice_transcript(self, text: str):
        """Update the recognized-speech transcript display."""
        self.voice_transcript.configure(text=text if text else "Aguardando fala...")

    def push_frame(self, frame):
        """Push a BGR frame to the video feed (thread-safe)."""
        self.video_feed.update_frame(frame)

    def start_feed(self):
        self.video_feed.start()

    def stop_feed(self):
        self.video_feed.stop()
