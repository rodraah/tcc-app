"""Camera page: live video feed + gesture/voice status overlay."""

import customtkinter as ctk

from gui.widgets.video_feed import VideoFeed


class CameraPage(ctk.CTkFrame):
    """Page displaying the live camera feed with gesture and voice status."""

    # Shared visual constants (light, dark) for the status cards and video
    _CARD_BG = ("gray95", "gray18")
    _CARD_BORDER = ("gray80", "gray30")
    _TRANSCRIPT_BG = ("gray90", "gray22")
    _TRANSCRIPT_BORDER = ("gray75", "gray30")
    _TITLE_COLOR = ("gray40", "gray65")
    _SECONDARY_COLOR = ("gray45", "gray60")
    _PLACEHOLDER_COLOR = ("gray50", "gray55")
    _ACTIVE_TEXT_COLOR = ("gray15", "gray85")

    def __init__(
        self,
        master,
        on_camera_enabled=None,
        on_voice_enabled=None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_camera_enabled = on_camera_enabled
        self.on_voice_enabled = on_voice_enabled
        self._camera_enabled = ctk.BooleanVar(value=True)
        self._voice_enabled = ctk.BooleanVar(value=True)

        # Vertical distribution: the video row absorbs the extra space while
        # the cards keep their natural height.
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- Header (title + enable switch) ---
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=24, pady=(10, 4), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="Câmera e Reconhecimento",
            font=ctk.CTkFont(size=23, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        self.camera_switch = ctk.CTkSwitch(
            header,
            text="Ativar",
            variable=self._camera_enabled,
            command=self._emit_camera_enabled,
            onvalue=True,
            offvalue=False,
        )
        self.camera_switch.grid(row=0, column=1, sticky="e")

        # --- Video feed (inside a padded, rounded container) ---
        video_container = ctk.CTkFrame(
            self,
            fg_color=self._CARD_BG,
            border_width=1,
            border_color=self._CARD_BORDER,
            corner_radius=12,
        )
        video_container.grid(row=1, column=0, padx=24, pady=(4, 14), sticky="nsew")
        video_container.grid_columnconfigure(0, weight=1)
        video_container.grid_rowconfigure(0, weight=1)

        self.video_feed = VideoFeed(video_container, width=640, height=480)
        self.video_feed.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")

        # --- Status cards (Gesto | Voz) ---
        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.grid(row=2, column=0, padx=24, pady=(0, 16), sticky="ew")
        cards.grid_columnconfigure(0, weight=1)
        cards.grid_columnconfigure(1, weight=1)

        # Gesture card
        self.gesture_frame = ctk.CTkFrame(
            cards,
            fg_color=self._CARD_BG,
            border_width=1,
            border_color=self._CARD_BORDER,
            corner_radius=12,
        )
        self.gesture_frame.grid(row=0, column=0, padx=(0, 8), sticky="nsew")
        self.gesture_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self.gesture_frame,
            text="Gesto",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self._TITLE_COLOR,
            anchor="w",
        ).grid(row=0, column=0, padx=16, pady=(14, 2), sticky="w")
        self.gesture_name = ctk.CTkLabel(
            self.gesture_frame,
            text="--",
            font=ctk.CTkFont(size=19, weight="bold"),
        )
        self.gesture_name.grid(row=1, column=0, padx=16, pady=(2, 2), sticky="w")
        self.gesture_origin = ctk.CTkLabel(
            self.gesture_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=self._SECONDARY_COLOR,
        )
        self.gesture_origin.grid(row=2, column=0, padx=16, pady=(2, 2), sticky="w")
        self.hold_bar = ctk.CTkProgressBar(
            self.gesture_frame,
            height=8,
            corner_radius=4,
            progress_color=("#2E86C1", "#5DADE2"),
        )
        self.hold_bar.grid(row=3, column=0, padx=16, pady=(4, 2), sticky="ew")
        self.hold_bar.set(0)
        self.gesture_action = ctk.CTkLabel(
            self.gesture_frame,
            text="",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=("#2E86C1", "#5DADE2"),
            anchor="w",
        )
        self.gesture_action.grid(row=4, column=0, padx=16, pady=(2, 14), sticky="w")

        # Voice card
        self.voice_frame = ctk.CTkFrame(
            cards,
            fg_color=self._CARD_BG,
            border_width=1,
            border_color=self._CARD_BORDER,
            corner_radius=12,
        )
        self.voice_frame.grid(row=0, column=1, padx=(8, 0), sticky="nsew")
        self.voice_frame.grid_columnconfigure(0, weight=1)

        voice_header = ctk.CTkFrame(self.voice_frame, fg_color="transparent")
        voice_header.grid(row=0, column=0, padx=16, pady=(14, 2), sticky="ew")
        voice_header.grid_columnconfigure(1, weight=1)
        self.listen_dot = ctk.CTkLabel(
            voice_header,
            text="●",
            width=18,
            font=ctk.CTkFont(size=14),
            text_color=self._PLACEHOLDER_COLOR,
        )
        self.listen_dot.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            voice_header,
            text="Voz",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self._TITLE_COLOR,
            anchor="w",
        ).grid(row=0, column=1, padx=(4, 0), sticky="w")
        self.voice_switch = ctk.CTkSwitch(
            voice_header,
            text="Ativar",
            variable=self._voice_enabled,
            command=self._emit_voice_enabled,
            onvalue=True,
            offvalue=False,
        )
        self.voice_switch.grid(row=0, column=2, sticky="e")

        self.voice_status = ctk.CTkLabel(
            self.voice_frame,
            text="Não conectado",
            font=ctk.CTkFont(size=19, weight="bold"),
        )
        self.voice_status.grid(row=1, column=0, padx=16, pady=(2, 2), sticky="w")
        self.voice_command = ctk.CTkLabel(
            self.voice_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=self._SECONDARY_COLOR,
        )
        self.voice_command.grid(row=2, column=0, padx=16, pady=(2, 2), sticky="w")

        # Recognized speech transcript — inner block of the voice card
        self.voice_transcript_frame = ctk.CTkFrame(
            self.voice_frame,
            fg_color=self._TRANSCRIPT_BG,
            border_width=1,
            border_color=self._TRANSCRIPT_BORDER,
            corner_radius=8,
        )
        self.voice_transcript_frame.grid(
            row=3, column=0, padx=16, pady=(6, 14), sticky="ew"
        )
        self.voice_transcript_frame.grid_columnconfigure(0, weight=1)
        self.voice_transcript = ctk.CTkLabel(
            self.voice_transcript_frame,
            text="Aguardando fala...",
            font=ctk.CTkFont(size=14),
            text_color=self._PLACEHOLDER_COLOR,
            anchor="w",
        )
        self.voice_transcript.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

        self._listening = False
        self._pulse_on = False
        self._pulse_job = None

    @property
    def camera_enabled(self) -> bool:
        return bool(self._camera_enabled.get())

    @property
    def voice_enabled(self) -> bool:
        return bool(self._voice_enabled.get())

    def _emit_camera_enabled(self):
        if self.on_camera_enabled:
            self.on_camera_enabled(self.camera_enabled)

    def _emit_voice_enabled(self):
        if self.on_voice_enabled:
            self.on_voice_enabled(self.voice_enabled)

    # --- Public update methods (called from main thread via after()) ---

    def update_gesture(
        self,
        name: str,
        confidence: float = 0.0,
        origin: str = "",
        action: str = "",
        hold: float = 0.0,
    ):
        """Update the gesture display and hold-to-confirm progress bar."""
        self.gesture_name.configure(text=name if name else "--")
        if confidence > 0 and origin:
            self.gesture_origin.configure(text=f"{confidence:.2f} ({origin})")
        else:
            self.gesture_origin.configure(text="")
        self.hold_bar.set(max(0.0, min(1.0, float(hold or 0.0))))
        if action:
            self.gesture_action.configure(text=f"→ {action}")
        else:
            self.gesture_action.configure(text="")

    def update_voice(self, status: str, command: str = ""):
        """Update the voice status display and listening pulse."""
        self.voice_status.configure(text=status)
        self.voice_command.configure(text=command)
        # Pulse while actively listening (Portuguese label or raw code).
        key = (status or "").strip().lower()
        self.set_listening(key in ("ouvindo", "started"))

    def set_listening(self, active: bool):
        """Start/stop the green pulse on the voice card listening dot."""
        if active == self._listening:
            return
        self._listening = active
        if active:
            self._pulse_on = False
            self._pulse()
            return
        if self._pulse_job is not None:
            try:
                self.after_cancel(self._pulse_job)
            except Exception:
                pass
            self._pulse_job = None
        self.listen_dot.configure(text_color=self._PLACEHOLDER_COLOR)

    def _pulse(self):
        """Toggle the listening-dot color; reschedules while listening."""
        if not self._listening:
            return
        self._pulse_on = not self._pulse_on
        color = (
            ("#2e8b57", "#2f9e63") if self._pulse_on else ("#90c9a8", "#4a7a5c")
        )
        self.listen_dot.configure(text_color=color)
        self._pulse_job = self.after(500, self._pulse)

    def update_voice_transcript(self, text: str):
        """Update the recognized-speech transcript display."""
        if text:
            self.voice_transcript.configure(
                text=text, text_color=self._ACTIVE_TEXT_COLOR
            )
        else:
            self.voice_transcript.configure(
                text="Aguardando fala...", text_color=self._PLACEHOLDER_COLOR
            )

    def push_frame(self, frame):
        """Push a BGR frame to the video feed (thread-safe)."""
        self.video_feed.update_frame(frame)

    def start_feed(self):
        self.video_feed.start()

    def stop_feed(self):
        self.video_feed.stop()