"""Queue-based OpenCV → CTkImage renderer."""

import queue
import threading

import customtkinter as ctk
import cv2
from PIL import Image


class VideoFeed(ctk.CTkLabel):
    """A CTkLabel that displays OpenCV frames from a background thread.

    Usage:
        feed = VideoFeed(parent, width=640, height=480)
        feed.start()  # begins polling
        # From background thread: feed.update_frame(frame)
        feed.stop()
    """

    def __init__(self, master, width=640, height=480, refresh_ms=30, **kwargs):
        super().__init__(master, text="", **kwargs)
        self._width = width
        self._height = height
        self._refresh_ms = refresh_ms
        self._frame_queue: queue.Queue = queue.Queue(maxsize=1)
        self._running = False
        self._current_image: ctk.CTkImage | None = None

    def update_frame(self, frame):
        """Push a new BGR frame from a background thread (non-blocking)."""
        try:
            self._frame_queue.put_nowait(frame)
        except queue.Full:
            pass  # drop old frame

    def start(self):
        """Start the polling loop on the main thread."""
        self._running = True
        self._poll()

    def stop(self):
        """Stop the polling loop."""
        self._running = False

    def _poll(self):
        """Poll the queue for new frames (runs on main thread)."""
        if not self._running:
            return
        try:
            frame = self._frame_queue.get_nowait()
            self._render(frame)
        except queue.Empty:
            pass
        self.after(self._refresh_ms, self._poll)

    def _render(self, frame):
        """Convert a BGR OpenCV frame to CTkImage and display it."""
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(frame_rgb)
        pil_img = pil_img.resize((self._width, self._height), Image.LANCZOS)
        ctk_img = ctk.CTkImage(
            light_image=pil_img,
            dark_image=pil_img,
            size=(self._width, self._height),
        )
        self.configure(image=ctk_img, text="")
        self._current_image = ctk_img  # prevent GC
