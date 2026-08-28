"""First-launch setup wizard.

Modal CTkToplevel dialog that guides the user through initial configuration:
camera, microphone, pause threshold, and hotkey.  Settings are persisted to
``config/app_state.json``.

Usage::

    from gui.widgets.wizard import SetupWizard

    if SetupWizard.should_run(parent_app):
        wizard = SetupWizard(parent_app)
        parent_app.wait_window(wizard)
        if wizard.result:
            settings = wizard.settings
"""

import json
import queue
import threading
from pathlib import Path

import customtkinter as ctk
from PIL import Image

# Resolve config directory relative to project root
_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
_APP_STATE_PATH = _CONFIG_DIR / "app_state.json"

_DEFAULTS = {
    "camera_index": 0,
    "mic_device_id": None,
    "pause_threshold": 0.7,
    "hotkey": "F9",
}


# ---------------------------------------------------------------------------
# Hardware probing helpers (graceful fallback on import/runtime errors)
# ---------------------------------------------------------------------------

def _probe_cameras():
    """Return list of available camera indices (0-4)."""
    try:
        import cv2

        cameras = []
        for i in range(5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                cameras.append(i)
                cap.release()
        return cameras
    except Exception:
        return []


def _probe_mics():
    """Return list of (device_id, name) for input devices.

    Only devices that can actually be used as a microphone are returned.
    Pure input devices (``max_input_channels > 0`` and
    ``max_output_channels == 0``) are preferred and listed first.  If no
    pure input device is found, devices that report both input and output
    channels are included as a fallback so a real mic is never hidden.
    """
    try:
        import sounddevice as sd

        devices = sd.query_devices()
        pure_inputs = []
        mixed = []
        for i, d in enumerate(devices):
            if d["max_input_channels"] > 0:
                if d["max_output_channels"] == 0:
                    pure_inputs.append((i, d["name"]))
                else:
                    mixed.append((i, d["name"]))
        # Prefer genuine input-only devices; fall back to mixed ones only
        # when no pure input device is available.
        return pure_inputs if pure_inputs else mixed
    except Exception:
        return []


# ---------------------------------------------------------------------------
# SetupWizard
# ---------------------------------------------------------------------------

class SetupWizard(ctk.CTkToplevel):
    """Modal first-launch setup wizard.

    Attributes:
        result: ``True`` if the user completed the wizard, ``False`` if
            cancelled.
        settings: The final settings dict (only meaningful when ``result``
            is ``True``).
    """

    # Page titles (order matters)
    _STEP_KEYS = ("welcome", "camera", "mic", "pause", "hotkey", "finish")
    _STEP_TITLES = {
        "welcome": "Bem-vindo ao TCC-App",
        "camera": "Seleção de Câmera",
        "mic": "Seleção de Microfone",
        "pause": "Limiar de Pausa",
        "hotkey": "Tecla de Atalho Global",
        "finish": "Pronto para Iniciar",
    }

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        # --- Window setup ---
        self.title("Assistente de Configuração do TCC-App")
        self.geometry("520x480")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.result: bool = False
        self.settings: dict = {}

        # Collected values (editable across steps)
        self._camera_index: int = 0
        self._mic_device_id: int | None = None
        self._pause_threshold: float = 0.7
        self._hotkey: str = "F9"

        # Probed hardware lists (populated lazily)
        self._cameras: list[int] = []
        self._mics: list[tuple[int, str]] = []

        # Current step index
        self._step_index: int = 0

        # Live camera preview state
        self._preview_running: bool = False
        self._preview_thread: threading.Thread | None = None
        self._preview_cap = None
        self._preview_queue: queue.Queue = queue.Queue(maxsize=1)
        self._current_image = None  # keep CTkImage reference alive (prevent GC)

        # --- Layout ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Step title
        self._title_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=20, weight="bold"),
            anchor="w",
        )
        self._title_label.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="w")

        # Content area (one frame per step, toggled via grid)
        self._content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._content_frame.grid(row=1, column=0, padx=20, pady=5, sticky="nsew")
        self._content_frame.grid_columnconfigure(0, weight=1)
        self._content_frame.grid_rowconfigure(0, weight=1)

        # Navigation bar
        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.grid(row=2, column=0, padx=20, pady=(5, 15), sticky="ew")
        nav.grid_columnconfigure(1, weight=1)

        self._back_btn = ctk.CTkButton(
            nav, text="Voltar", width=90, command=self._go_back
        )
        self._back_btn.grid(row=0, column=0, sticky="w")

        self._cancel_btn = ctk.CTkButton(
            nav,
            text="Cancelar",
            width=90,
            fg_color="gray50",
            hover_color="gray40",
            command=self._cancel,
        )
        self._cancel_btn.grid(row=0, column=1, sticky="w", padx=(10, 0))

        self._next_btn = ctk.CTkButton(
            nav, text="Próximo", width=90, command=self._go_next
        )
        self._next_btn.grid(row=0, column=2, sticky="e")

        # Build all step frames (hidden by default)
        self._step_frames: dict[str, ctk.CTkFrame] = {}
        self._build_welcome()
        self._build_camera()
        self._build_mic()
        self._build_pause()
        self._build_hotkey()
        self._build_finish()

        # Show first step
        self._show_step(0)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _show_step(self, index: int):
        """Display the step at *index*, update nav buttons."""
        key = self._STEP_KEYS[index]
        self._step_index = index
        self._title_label.configure(text=self._STEP_TITLES[key])

        # Start/stop the live camera preview based on the visible step
        if key == "camera":
            self._start_preview()
        else:
            self._stop_preview()

        # Hide all frames, show current
        for k, frame in self._step_frames.items():
            frame.grid_forget()
        self._step_frames[key].grid(row=0, column=0, sticky="nsew")

        # Navigation button visibility
        self._back_btn.configure(state="normal" if index > 0 else "disabled")
        self._cancel_btn.configure(state="normal")

        if key == "finish":
            self._next_btn.configure(text="Iniciar")
            self._update_finish_summary()
        else:
            self._next_btn.configure(text="Próximo")

    def _go_next(self):
        """Advance to the next step, or finish."""
        key = self._STEP_KEYS[self._step_index]

        # Collect values from the current step before advancing
        self._collect_step(key)

        if key == "finish":
            self._finish()
        else:
            self._show_step(self._step_index + 1)

    def _go_back(self):
        """Return to the previous step."""
        if self._step_index > 0:
            # Collect current step values before going back
            key = self._STEP_KEYS[self._step_index]
            self._collect_step(key)
            self._show_step(self._step_index - 1)

    def _cancel(self):
        """Cancel the wizard."""
        self.result = False
        self._stop_preview()
        self.grab_release()
        self.destroy()

    def _finish(self):
        """Save settings and close."""
        self.settings = {
            "camera_index": self._camera_index,
            "mic_device_id": self._mic_device_id,
            "pause_threshold": self._pause_threshold,
            "hotkey": self._hotkey,
        }
        self.save_settings(self.settings)
        self.result = True
        self._stop_preview()
        self.grab_release()
        self.destroy()

    # ------------------------------------------------------------------
    # Step builders
    # ------------------------------------------------------------------

    def _build_welcome(self):
        frame = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        self._step_frames["welcome"] = frame

        ctk.CTkLabel(
            frame,
            text="Bem-vindo ao TCC-App!",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(anchor="w", pady=(20, 10))

        description = (
            "O TCC-App permite controlar o Windows usando gestos de mão\n"
            "e comandos de voz através da sua webcam e microfone.\n\n"
            "Este assistente ajudará você a configurar seus dispositivos\n"
            "e preferências. Você pode alterar essas configurações depois\n"
            "pelo aplicativo."
        )
        ctk.CTkLabel(
            frame,
            text=description,
            font=ctk.CTkFont(size=14),
            justify="left",
        ).pack(anchor="w", pady=10)

    def _build_camera(self):
        frame = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        self._step_frames["camera"] = frame

        ctk.CTkLabel(
            frame,
            text="Selecione a câmera para reconhecimento de gestos:",
            font=ctk.CTkFont(size=14),
            justify="left",
        ).pack(anchor="w", pady=(10, 10))

        self._cameras = _probe_cameras()

        if self._cameras:
            labels = [f"Câmera {i}" for i in self._cameras]
            self._camera_menu = ctk.CTkOptionMenu(
                frame,
                values=labels,
                width=280,
                command=self._on_camera_select,
            )
            self._camera_menu.pack(anchor="w", pady=5)
            self._camera_index = self._cameras[0]

            # Live preview label (rendered via after() polling)
            self._preview_label = ctk.CTkLabel(
                frame,
                text="Pré-visualização ao vivo",
                font=ctk.CTkFont(size=12),
                text_color="gray60",
                width=320,
                height=240,
            )
            self._preview_label.pack(anchor="w", pady=(5, 0))
        else:
            ctk.CTkLabel(
                frame,
                text="Nenhuma câmera detectada.\n"
                     "Conecte uma câmera e reinicie o assistente.",
                text_color="orange",
                font=ctk.CTkFont(size=13),
                justify="left",
            ).pack(anchor="w", pady=10)
            self._camera_menu = None
            self._preview_label = None

    def _on_camera_select(self, choice: str):
        """Handle camera dropdown selection."""
        idx = int(choice.split()[-1])
        self._camera_index = idx
        # Restart the live preview with the newly selected camera
        self._start_preview()

    # ------------------------------------------------------------------
    # Live camera preview
    # ------------------------------------------------------------------

    def _start_preview(self):
        """Start the live camera preview for the selected camera.

        Stops any existing preview first, then spawns a daemon thread that
        reads frames and pushes them onto a single-slot queue.  The main
        thread polls the queue via ``after()`` and renders each frame.
        """
        self._stop_preview()

        if not self._cameras or self._preview_label is None:
            return

        self._preview_running = True
        self._preview_thread = threading.Thread(
            target=self._preview_loop, daemon=True
        )
        self._preview_thread.start()
        # Schedule the first poll; subsequent polls reschedule themselves.
        self.after(30, self._poll_preview)

    def _preview_loop(self):
        """Background thread: open the camera and push frames to the queue."""
        try:
            import cv2

            cap = cv2.VideoCapture(self._camera_index)
            if not cap.isOpened():
                self._preview_running = False
                return
            self._preview_cap = cap
            while self._preview_running:
                ret, frame = cap.read()
                if not ret or frame is None:
                    continue
                frame = cv2.flip(frame, 1)  # mirror for natural interaction
                try:
                    self._preview_queue.put_nowait(frame)
                except queue.Full:
                    pass  # drop old frame
        except Exception:
            self._preview_running = False
        finally:
            self._preview_cap = None

    def _poll_preview(self):
        """Main-thread poll: render the latest frame to the preview label."""
        if not self._preview_running:
            return
        try:
            frame = self._preview_queue.get_nowait()
        except queue.Empty:
            # No new frame yet; keep polling.
            self.after(30, self._poll_preview)
            return

        try:
            import cv2

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(frame_rgb)
            ctk_img = ctk.CTkImage(
                light_image=pil_img, dark_image=pil_img, size=(320, 240)
            )
            self._preview_label.configure(image=ctk_img, text="")
            self._current_image = ctk_img  # prevent GC
        except Exception:
            pass

        if self._preview_running:
            self.after(30, self._poll_preview)

    def _stop_preview(self):
        """Stop the preview thread and release the camera cleanly."""
        self._preview_running = False
        if self._preview_cap is not None:
            try:
                self._preview_cap.release()
            except Exception:
                pass
            self._preview_cap = None
        if self._preview_thread is not None:
            self._preview_thread.join(timeout=1.0)
            self._preview_thread = None
        # Clear the queue so a stale frame isn't rendered on restart
        while True:
            try:
                self._preview_queue.get_nowait()
            except queue.Empty:
                break

    def _build_mic(self):
        frame = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        self._step_frames["mic"] = frame

        ctk.CTkLabel(
            frame,
            text="Selecione o microfone para comandos de voz:",
            font=ctk.CTkFont(size=14),
            justify="left",
        ).pack(anchor="w", pady=(10, 10))

        self._mics = _probe_mics()

        if self._mics:
            labels = [name for _, name in self._mics]
            self._mic_menu = ctk.CTkOptionMenu(
                frame,
                values=labels,
                width=360,
                command=self._on_mic_select,
            )
            self._mic_menu.pack(anchor="w", pady=5)
            self._mic_device_id = self._mics[0][0]
        else:
            ctk.CTkLabel(
                frame,
                text="Nenhum microfone detectado.\n"
                     "Comandos de voz não estarão disponíveis.",
                text_color="orange",
                font=ctk.CTkFont(size=13),
                justify="left",
            ).pack(anchor="w", pady=10)
            self._mic_menu = None
            self._mic_device_id = None

    def _on_mic_select(self, choice: str):
        """Handle mic dropdown selection."""
        for dev_id, name in self._mics:
            if name == choice:
                self._mic_device_id = dev_id
                break

    def _build_pause(self):
        frame = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        self._step_frames["pause"] = frame

        ctk.CTkLabel(
            frame,
            text="Defina o limite de pausa entre palavras\n"
                 "para o reconhecimento de voz (em segundos):",
            font=ctk.CTkFont(size=14),
            justify="left",
        ).pack(anchor="w", pady=(10, 10))

        slider_row = ctk.CTkFrame(frame, fg_color="transparent")
        slider_row.pack(fill="x", pady=5)
        slider_row.grid_columnconfigure(0, weight=1)

        self._pause_value_label = ctk.CTkLabel(
            slider_row,
            text=f"{self._pause_threshold:.1f}s",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=60,
        )

        self._pause_slider = ctk.CTkSlider(
            slider_row,
            from_=0.1,
            to=2.0,
            number_of_steps=19,
            width=300,
            command=self._on_pause_change,
        )
        self._pause_slider.set(self._pause_threshold)
        self._pause_slider.grid(row=0, column=0, padx=(0, 10), sticky="w")
        self._pause_value_label.grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            frame,
            text="Valores menores tornam a detecção de voz mais responsiva.\n"
                 "Valores maiores reduzem disparos falsos por ruído de fundo.",
            font=ctk.CTkFont(size=12),
            text_color="gray60",
            justify="left",
        ).pack(anchor="w", pady=(15, 0))

    def _on_pause_change(self, value: float):
        """Update the displayed slider value."""
        self._pause_threshold = round(value, 1)
        self._pause_value_label.configure(text=f"{self._pause_threshold:.1f}s")

    def _build_hotkey(self):
        frame = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        self._step_frames["hotkey"] = frame

        ctk.CTkLabel(
            frame,
            text="Defina o atalho global para mostrar/ocultar a janela do aplicativo:",
            font=ctk.CTkFont(size=14),
            justify="left",
        ).pack(anchor="w", pady=(10, 10))

        entry_row = ctk.CTkFrame(frame, fg_color="transparent")
        entry_row.pack(anchor="w", pady=5)

        ctk.CTkLabel(
            entry_row, text="Atalho:", font=ctk.CTkFont(size=14)
        ).pack(side="left", padx=(0, 10))

        self._hotkey_entry = ctk.CTkEntry(
            entry_row, width=120, placeholder_text="F9"
        )
        self._hotkey_entry.insert(0, self._hotkey)
        self._hotkey_entry.pack(side="left")

        ctk.CTkLabel(
            frame,
            text="Pressione esta tecla em qualquer lugar do sistema\n"
                 "para mostrar/ocultar a janela do TCC-App.",
            font=ctk.CTkFont(size=12),
            text_color="gray60",
            justify="left",
        ).pack(anchor="w", pady=(15, 0))

    def _build_finish(self):
        frame = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        self._step_frames["finish"] = frame

        ctk.CTkLabel(
            frame,
            text="Configuração concluída!",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor="w", pady=(20, 10))

        ctk.CTkLabel(
            frame,
            text="Revise suas configurações abaixo e clique em Iniciar.",
            font=ctk.CTkFont(size=14),
        ).pack(anchor="w", pady=(0, 15))

        self._summary_frame = ctk.CTkFrame(frame)
        self._summary_frame.pack(fill="x", pady=5)
        self._summary_frame.grid_columnconfigure(1, weight=1)

        self._summary_labels: dict[str, ctk.CTkLabel] = {}
        fields = [
            ("camera_index", "Câmera"),
            ("mic_device_id", "Microfone"),
            ("pause_threshold", "Limite de Pausa"),
            ("hotkey", "Atalho"),
        ]
        for i, (key, label) in enumerate(fields):
            ctk.CTkLabel(
                self._summary_frame,
                text=f"{label}:",
                font=ctk.CTkFont(weight="bold"),
                anchor="w",
            ).grid(row=i, column=0, padx=10, pady=4, sticky="w")
            val_label = ctk.CTkLabel(
                self._summary_frame,
                text="",
                font=ctk.CTkFont(size=13),
                anchor="w",
            )
            val_label.grid(row=i, column=1, padx=10, pady=4, sticky="w")
            self._summary_labels[key] = val_label

    def _update_finish_summary(self):
        """Refresh the summary text on the Finish page."""
        cam = self._cameras
        cam_text = (
            f"Camera {self._camera_index}"
            if self._camera_index in cam
            else f"Camera {self._camera_index} (not detected)"
        )
        self._summary_labels["camera_index"].configure(text=cam_text)

        mic_text = "Not selected"
        if self._mic_device_id is not None:
            for dev_id, name in self._mics:
                if dev_id == self._mic_device_id:
                    mic_text = name
                    break
        self._summary_labels["mic_device_id"].configure(text=mic_text)

        self._summary_labels["pause_threshold"].configure(
            text=f"{self._pause_threshold:.1f} seconds"
        )
        self._summary_labels["hotkey"].configure(text=self._hotkey)

    # ------------------------------------------------------------------
    # Step value collection (called before navigation)
    # ------------------------------------------------------------------

    def _collect_step(self, key: str):
        """Read current widget values for the given step."""
        if key == "hotkey":
            raw = self._hotkey_entry.get().strip()
            self._hotkey = raw if raw else "F9"

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def should_run(parent) -> bool:
        """Return ``True`` if ``config/app_state.json`` doesn't exist or is
        invalid (missing required keys)."""
        if not _APP_STATE_PATH.is_file():
            return True
        try:
            data = json.loads(_APP_STATE_PATH.read_text(encoding="utf-8"))
            # Validate that all required keys are present
            for key in _DEFAULTS:
                if key not in data:
                    return True
            return False
        except (json.JSONDecodeError, UnicodeDecodeError):
            return True

    @staticmethod
    def load_settings() -> dict:
        """Load settings from ``config/app_state.json``.

        Returns defaults if the file is missing or invalid.
        """
        defaults = dict(_DEFAULTS)
        if not _APP_STATE_PATH.is_file():
            return defaults
        try:
            data = json.loads(_APP_STATE_PATH.read_text(encoding="utf-8"))
            # Merge with defaults so missing keys are filled
            for key, value in defaults.items():
                data.setdefault(key, value)
            return data
        except (json.JSONDecodeError, UnicodeDecodeError):
            return defaults

    @staticmethod
    def save_settings(settings: dict):
        """Persist settings dict to ``config/app_state.json``."""
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _APP_STATE_PATH.write_text(
            json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
