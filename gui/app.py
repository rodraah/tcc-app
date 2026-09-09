"""Main application shell: CTk root window with sidebar navigation."""

import queue

import customtkinter as ctk

from gui.pages.camera import CameraPage
from gui.pages.gesture_map import GestureMapPage
from gui.pages.log import LogPage
from gui.widgets.sidebar import Sidebar
from gui.widgets.status_bar import StatusBar


class App(ctk.CTk):
    """Main application window.

    Owns the layout (sidebar + content area + status bar), the three pages,
    and the recognition running state.

    Background threads must never touch widgets directly; they schedule calls
    to the public ``update_*`` methods via ``app.after(0, ...)`` instead.
    """

    # Sidebar button labels, keyed by page name
    PAGE_LABELS = {"camera": "Câmera", "map": "Configuração", "log": "Log"}

    def __init__(self, on_start=None, on_stop=None, on_quit=None):
        super().__init__()

        self.on_start = on_start
        self.on_stop = on_stop
        self.on_quit = on_quit
        self.on_settings_changed = None  # wired by main.py to restart threads
        # Optional per-modality hooks (wired by main.py)
        self.on_start_camera = None
        self.on_stop_camera = None
        self.on_start_voice = None
        self.on_stop_voice = None

        self.running = False
        self._current_page: str | None = None
        self._errors_polling = False  # error poll loop runs once, forever

        # --- Queues for background thread communication ---
        self._frame_queue: queue.Queue = queue.Queue(maxsize=1)
        self._gesture_queue: queue.Queue = queue.Queue(maxsize=1)
        self._log_queue: queue.Queue = queue.Queue(maxsize=50)
        self._action_queue: queue.Queue = queue.Queue(maxsize=5)
        self._voice_status_queue: queue.Queue = queue.Queue(maxsize=1)
        self._transcript_queue: queue.Queue = queue.Queue(maxsize=1)
        self._error_queue: queue.Queue = queue.Queue(maxsize=1)  # Critical errors for UI dialogs

        # --- Window ---
        self.title("TCC-App — Controle por Gestos e Voz")
        self.geometry("960x640")
        self.minsize(800, 500)

        # --- Layout grid ---
        # Column 0: sidebar (spans both rows). Column 1: content + status bar.
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Sidebar navigation ---
        self.sidebar = Sidebar(self)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        for page_name, label in self.PAGE_LABELS.items():
            self.sidebar.add_button(
                label, command=lambda n=page_name: self.show_page(n)
            )
        self.sidebar.add_spacer()

        # --- Pages (created once, switched via grid_forget/grid) ---
        self.pages: dict[str, ctk.CTkBaseClass] = {
            "camera": CameraPage(
                self,
                on_camera_enabled=self._handle_camera_enabled,
                on_voice_enabled=self._handle_voice_enabled,
            ),
            "map": GestureMapPage(
                self, on_settings_changed=self._on_settings_changed
            ),
            "log": LogPage(self),
        }

        # --- Status bar ---
        self.status_bar = StatusBar(
            self,
            on_start=self._handle_start,
            on_stop=self._handle_stop,
        )
        self.status_bar.grid(row=1, column=1, sticky="sew")

        # Closing the window hides to tray instead of destroying the app
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

        self.show_page("camera")

        # Stop starts disabled — fix found during testing
        self.status_bar.set_running(False)

    # --- Navigation ---

    def show_page(self, name: str):
        """Switch the visible page in the content area."""
        if name not in self.pages:
            return
        if self._current_page is not None:
            self.pages[self._current_page].grid_forget()
        self._current_page = name
        self.pages[name].grid(row=0, column=1, sticky="nsew")
        self.sidebar.set_active(self.PAGE_LABELS[name])

    # --- Public show-and-start (called from hotkey toggle) ---

    def show_and_start(self):
        """Show the window and start recognition if not already running.

        Designed to be called via ``app.after(0, ...)`` from the hotkey
        thread so it always executes on the main thread.
        """
        self.deiconify()
        self.lift()
        self.focus_force()
        if not self.running:
            self._handle_start()

    # --- Start/stop handling ---

    def _handle_start(self):
        """Start recognition for modalities that are currently enabled."""
        cam = self.pages["camera"]
        self.running = True
        self.status_bar.set_running(True)
        if cam.camera_enabled:
            cam.start_feed()
        if not cam.voice_enabled:
            cam.update_voice("Desativado")
            cam.update_voice_transcript("")
        self._start_polling()
        if self.on_start:
            self.on_start()

    def _handle_stop(self):
        """Stop gesture recognition (invoked by the Stop button)."""
        self.running = False
        self.status_bar.set_running(False)
        self.pages["camera"].stop_feed()
        if self.on_stop:
            self.on_stop()

    def _handle_camera_enabled(self, enabled: bool):
        """Toggle camera/gesture while recognition is running."""
        cam = self.pages["camera"]
        if not self.running:
            return
        if enabled:
            cam.start_feed()
            if self.on_start_camera:
                self.on_start_camera()
        else:
            cam.stop_feed()
            cam.update_gesture("")
            if self.on_stop_camera:
                self.on_stop_camera()

    def _handle_voice_enabled(self, enabled: bool):
        """Toggle voice while recognition is running."""
        cam = self.pages["camera"]
        if not self.running:
            if not enabled:
                cam.update_voice("Desativado")
                cam.update_voice_transcript("")
            else:
                cam.update_voice("Não conectado")
            return
        if enabled:
            if self.on_start_voice:
                self.on_start_voice()
        else:
            cam.update_voice("Desativado")
            cam.update_voice_transcript("")
            if self.on_stop_voice:
                self.on_stop_voice()

    def quit_app(self):
        """Fully exit the application (tray Quit / shutdown path)."""
        self.running = False
        self.pages["camera"].stop_feed()
        if self.on_quit:
            self.on_quit()
        self.destroy()

    def _on_settings_changed(
        self, camera_index: int, mic_device_id, pause_threshold=None
    ):
        """Forward a settings change from the settings page to main.py.

        ``main.py`` wires ``self.on_settings_changed`` to a handler that
        stops and recreates the recognition threads with the new devices.
        """
        if self.on_settings_changed:
            self.on_settings_changed(camera_index, mic_device_id, pause_threshold)

    # --- Queue wiring & polling ---

    def set_queues(
        self,
        frame_queue: queue.Queue,
        gesture_queue: queue.Queue,
        log_queue: queue.Queue,
        action_queue: queue.Queue,
        voice_status_queue: queue.Queue,
        transcript_queue: queue.Queue | None = None,
        error_queue: queue.Queue | None = None,
    ) -> None:
        """Connect background-thread queues to the GUI polling loops.

        Call once from ``main()`` before the mainloop starts.  The actual
        polling begins when the user clicks Start (``_handle_start``).
        """
        self._frame_queue = frame_queue
        self._gesture_queue = gesture_queue
        self._log_queue = log_queue
        self._action_queue = action_queue
        self._voice_status_queue = voice_status_queue
        if transcript_queue is not None:
            self._transcript_queue = transcript_queue
        if error_queue is not None:
            self._error_queue = error_queue

    def _start_polling(self) -> None:
        """Start all ``after()``-based polling loops (runs on main thread)."""
        self._poll_frames()
        self._poll_gesture_status()
        self._poll_log()
        self._poll_actions()
        self._poll_voice_status()
        self._poll_transcript()
        # The error poll loop is started once and keeps running even when
        # recognition is stopped — errors can arrive at any time.
        if not self._errors_polling:
            self._errors_polling = True
            self._poll_errors()

    # -- Individual polling loops ------------------------------------------------

    def _poll_frames(self) -> None:
        """Pull the latest BGR frame from the gesture thread and push it
        to the video feed widget."""
        try:
            frame = self._frame_queue.get_nowait()
            self.push_video_frame(frame)
        except queue.Empty:
            pass
        if self.running:
            self.after(30, self._poll_frames)  # ~33 fps

    def _poll_gesture_status(self) -> None:
        """Pull the latest gesture info and update the UI."""
        try:
            name, confidence, origin, action = self._gesture_queue.get_nowait()
            self.update_gesture_status(name, confidence, origin, action)
        except queue.Empty:
            pass
        if self.running:
            self.after(100, self._poll_gesture_status)

    def _poll_log(self) -> None:
        """Drain all buffered log entries into the log page."""
        try:
            while True:
                message, module = self._log_queue.get_nowait()
                self.add_log_entry(message, module)
        except queue.Empty:
            pass
        if self.running:
            self.after(100, self._poll_log)

    def _poll_actions(self) -> None:
        """When an action fires, stop recognition and hide the app to tray.

        One action at a time: after a gesture action fires, the camera and
        mic are turned off so the user can perform the action without the
        app continuing to listen.  Runs on the main thread (via ``after()``),
        so calling ``_handle_stop()`` here is thread-safe.
        """
        try:
            action_name = self._action_queue.get_nowait()
            self.add_log_entry(f"Ação disparada: {action_name}", "gesto")
            self._handle_stop()  # stop recognition (camera + mic off)
            self.withdraw()  # auto-hide to tray
        except queue.Empty:
            pass
        if self.running:
            self.after(100, self._poll_actions)

    def _poll_voice_status(self) -> None:
        """Pull voice module status and update the camera page display."""
        try:
            status, detail = self._voice_status_queue.get_nowait()
            self.update_voice_status(status, detail or "")
        except queue.Empty:
            pass
        if self.running:
            self.after(100, self._poll_voice_status)

    def _poll_transcript(self) -> None:
        """Pull the latest recognized speech and update the camera page."""
        try:
            text = self._transcript_queue.get_nowait()
            self.update_voice_transcript(text)
        except queue.Empty:
            pass
        if self.running:
            self.after(100, self._poll_transcript)

    def _poll_errors(self) -> None:
        """Check for critical errors from background threads and show dialogs.

        Unlike the other poll loops, this one keeps rescheduling itself even
        when ``self.running`` is False — a thread can fail right after Start
        or report a late error after Stop, and the user must still see it.
        """
        try:
            title, message = self._error_queue.get_nowait()
            # Show error dialog on main thread
            import tkinter.messagebox as mb
            mb.showerror(title, message, parent=self)
        except queue.Empty:
            pass
        self.after(100, self._poll_errors)

    # --- Public update methods ---

    def update_gesture_status(
        self, name: str, confidence: float = 0.0, origin: str = "", action: str = ""
    ):
        """Update the gesture display in the status bar and camera page."""
        if not self.pages["camera"].camera_enabled:
            return
        self.status_bar.update_gesture(name, confidence, origin, action)
        self.pages["camera"].update_gesture(name, confidence, origin, action)

    def update_voice_status(self, status: str, command: str = ""):
        """Update the voice status display on the camera page."""
        if not self.pages["camera"].voice_enabled:
            return
        self.pages["camera"].update_voice(status, command)

    def update_voice_transcript(self, text: str):
        """Update the recognized-speech transcript on the camera page."""
        if not self.pages["camera"].voice_enabled:
            return
        self.pages["camera"].update_voice_transcript(text)

    def push_video_frame(self, frame):
        """Push a BGR frame to the video feed."""
        if not self.pages["camera"].camera_enabled:
            return
        self.pages["camera"].push_frame(frame)

    def add_log_entry(self, message: str, module: str = "system"):
        """Add an entry to the log page."""
        self.pages["log"].add_entry(message, module)
