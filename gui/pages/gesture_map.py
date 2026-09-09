"""Gesture→action mapping editor + settings editor."""

import json

import customtkinter as ctk

from app_paths import MAPEAMENTO_PATH
from gui.widgets.wizard import SetupWizard, _probe_cameras, _probe_mics

# Path to the gesture→action mapping file
MAPPING_PATH = MAPEAMENTO_PATH


class GestureMapPage(ctk.CTkScrollableFrame):
    """Page for editing gesture-to-action bindings and app settings."""

    # Shared visual constants (light, dark) matching the camera page design
    _CARD_BG = ("gray95", "gray18")
    _CARD_BORDER = ("gray80", "gray30")
    _SECTION_TITLE_COLOR = ("gray25", "gray85")
    _SECONDARY_COLOR = ("gray45", "gray60")
    _ROW_BG = "transparent"

    # Button palettes
    _ADD_BTN = {
        "fg_color": ("#2E86C1", "#1F6AA5"),
        "hover_color": ("#2471A3", "#144870"),
        "text_color": ("white", "white"),
    }
    _REMOVE_BTN = {
        "fg_color": ("#c0563f", "#c95f47"),
        "hover_color": ("#a34834", "#b04f39"),
        "text_color": ("white", "white"),
    }
    _APPLY_BTN = {
        "fg_color": ("#2e8b57", "#2f9e63"),
        "hover_color": ("#256f46", "#268a55"),
        "text_color": ("white", "white"),
    }

    def __init__(self, master, on_settings_changed=None, **kwargs):
        super().__init__(master, **kwargs)
        self.on_settings_changed = on_settings_changed

        # --- Page title ---
        ctk.CTkLabel(
            self,
            text="Configurações",
            font=ctk.CTkFont(size=23, weight="bold"),
            anchor="w",
        ).pack(anchor="w", padx=24, pady=(10, 4))

        # --- Devices Section (camera + microphone selection) ---
        self._build_devices()

        # --- Settings Section ---
        self.settings_frame = ctk.CTkFrame(
            self,
            fg_color=self._CARD_BG,
            border_width=1,
            border_color=self._CARD_BORDER,
            corner_radius=12,
        )
        self.settings_frame.pack(fill="x", padx=24, pady=(8, 8))

        ctk.CTkLabel(
            self.settings_frame,
            text="Configurações",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self._SECTION_TITLE_COLOR,
            anchor="w",
        ).pack(anchor="w", padx=16, pady=(14, 4))

        self._settings_widgets: dict[str, ctk.CTkEntry] = {}
        self._build_settings()

        # --- Gesture→Action Mapping Section ---
        self.mapping_frame = ctk.CTkFrame(
            self,
            fg_color=self._CARD_BG,
            border_width=1,
            border_color=self._CARD_BORDER,
            corner_radius=12,
        )
        self.mapping_frame.pack(fill="x", padx=24, pady=(8, 16))

        ctk.CTkLabel(
            self.mapping_frame,
            text="Mapeamento Gesto → Ação",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self._SECTION_TITLE_COLOR,
            anchor="w",
        ).pack(anchor="w", padx=16, pady=(14, 4))

        self._mapping_entries: list[dict] = []
        self._load_mapping()

        # Add new binding row
        add_row = ctk.CTkFrame(self.mapping_frame, fg_color="transparent")
        add_row.pack(fill="x", padx=14, pady=(6, 14))

        self.new_gesture = ctk.CTkEntry(add_row, placeholder_text="Nome do gesto", width=180)
        self.new_gesture.pack(side="left", padx=(0, 5))

        ctk.CTkLabel(add_row, text="→").pack(side="left")

        self.new_action = ctk.CTkOptionMenu(
            add_row, values=self._available_actions(), width=180
        )
        self.new_action.pack(side="left", padx=(5, 5))

        ctk.CTkButton(
            add_row,
            text="Adicionar",
            width=60,
            corner_radius=6,
            command=self._add_binding,
            **self._ADD_BTN,
        ).pack(side="left", padx=5)

        # Page-level "apply all changes" button (settings + mapping)
        ctk.CTkButton(
            self,
            text="Aplicar Configurações",
            corner_radius=6,
            command=self._apply_settings,
            **self._APPLY_BTN,
        ).pack(padx=24, pady=(8, 16))

    # --- Mapping ---

    def _load_mapping(self):
        """Load gesture→action mapping from JSON file."""
        try:
            with open(MAPPING_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}

        # Support both old flat format and new nested format with "gesto_para_acao"
        mapping = data.get("gesto_para_acao", data)

        for gesture, action in mapping.items():
            self._add_mapping_row(gesture, action)

    def _add_mapping_row(self, gesture: str, action: str):
        """Add a single mapping row to the UI."""
        row = ctk.CTkFrame(self.mapping_frame, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=3)

        gesture_label = ctk.CTkLabel(row, text=gesture, width=180, anchor="w")
        gesture_label.pack(side="left")

        ctk.CTkLabel(row, text="→").pack(side="left", padx=5)

        available = self._available_actions()
        if available:
            action_menu = ctk.CTkOptionMenu(
                row,
                values=available,
                width=180,
                command=lambda choice, g=gesture: self._on_action_change(g, choice),
            )
            # Select the current action if it is still registered; otherwise
            # fall back to the first available action.
            action_menu.set(action if action in available else available[0])
            action_menu.pack(side="left")
            self._mapping_entries.append(
                {"gesture": gesture, "action_menu": action_menu, "row": row}
            )
        else:
            # Degraded mode: no registered actions available (gesture deps
            # missing) — show the action name as a plain label instead.
            action_label = ctk.CTkLabel(row, text=action, width=180, anchor="w")
            action_label.pack(side="left")
            self._mapping_entries.append(
                {"gesture": gesture, "action": action, "row": row}
            )

        remove_btn = ctk.CTkButton(
            row,
            text="×",
            width=30,
            corner_radius=6,
            command=lambda g=gesture: self._remove_binding(g),
            **self._REMOVE_BTN,
        )
        remove_btn.pack(side="right")

    def _available_actions(self) -> list[str]:
        """Registered action names for the comboboxes.

        Lazy import: pulls in the gesture package only when the page is built
        (keeps the GUI smoke tests hermetic).  Falls back to an empty list if
        the gesture deps are unavailable.
        """
        try:
            from gesture.acoes import listar_acoes
            return listar_acoes()
        except Exception:
            return []

    def _on_action_change(self, gesture: str, action: str):
        """Persist the mapping when the user picks a different action.

        ``gesture``/``action`` are kept for future use (e.g. logging); the
        current selection is read from the comboboxes by ``_save_mapping``.
        """
        self._save_mapping()

    def _add_binding(self):
        """Add a new gesture→action binding."""
        gesture = self.new_gesture.get().strip()
        action = self.new_action.get().strip()
        if not gesture or not action:
            return
        self._add_mapping_row(gesture, action)
        self.new_gesture.delete(0, "end")
        # Reset the action combobox to the first available action (if any).
        available = self._available_actions()
        if available:
            self.new_action.set(available[0])
        self._save_mapping()

    def _remove_binding(self, gesture: str):
        """Remove a gesture→action binding."""
        # Find and destroy the row widget
        for entry in self._mapping_entries:
            if entry["gesture"] == gesture:
                entry["row"].destroy()
                break
        # Update internal list
        self._mapping_entries = [
            e for e in self._mapping_entries if e["gesture"] != gesture
        ]
        self._save_mapping()

    def _save_mapping(self):
        """Persist the current mapping to JSON."""
        mapping = {
            e["gesture"]: (
                e["action_menu"].get() if "action_menu" in e else e["action"]
            )
            for e in self._mapping_entries
        }
        # Save in nested format with schema version
        data = {"schema": 1, "gesto_para_acao": mapping}
        with open(MAPPING_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # --- Settings ---

    def _build_settings(self):
        """Build the settings editor fields."""
        settings = [
            ("Duração do Hold (s)", "DURACAO_HOLD_SEGUNDOS", "3.0"),
            ("Confiança Mínima", "CONFIANCA_MINIMA_GESTO_PRONTO", "0.6"),
            ("Tolerância de Gap (frames)", "TOLERANCIA_GAP_FRAMES", "3"),
            ("Limiar da Pinça", "LIMIAR_PINCA", "0.04"),
            ("Índice da Câmera", "CAMERA_INDEX", "0"),
        ]

        for label, key, default in settings:
            row = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=3)

            ctk.CTkLabel(row, text=label, width=200, anchor="w").pack(side="left")

            entry = ctk.CTkEntry(row, width=100)
            entry.insert(0, default)
            entry.pack(side="left", padx=(10, 0))

            self._settings_widgets[key] = entry

    def _apply_settings(self):
        """Apply settings (placeholder — will update config singleton later)."""
        for key, entry in self._settings_widgets.items():
            value = entry.get()
            print(f"[Configurações] {key} = {value}")  # TODO: update config singleton

    # --- Devices (camera + microphone) ---

    def _build_devices(self):
        """Build the camera and microphone selectors.

        Pre-populated from ``config/app_state.json``.  Changing a selection
        persists it and notifies the app (via ``on_settings_changed``) so the
        running recognition threads are restarted with the new device.
        """
        self.devices_frame = ctk.CTkFrame(
            self,
            fg_color=self._CARD_BG,
            border_width=1,
            border_color=self._CARD_BORDER,
            corner_radius=12,
        )
        self.devices_frame.pack(fill="x", padx=24, pady=(8, 8))

        ctk.CTkLabel(
            self.devices_frame,
            text="Dispositivos",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self._SECTION_TITLE_COLOR,
            anchor="w",
        ).pack(anchor="w", padx=16, pady=(14, 4))

        settings = SetupWizard.load_settings()
        current_camera = settings.get("camera_index", 0)
        current_mic = settings.get("mic_device_id")

        # --- Camera selector ---
        cam_row = ctk.CTkFrame(self.devices_frame, fg_color="transparent")
        cam_row.pack(fill="x", padx=14, pady=3)
        ctk.CTkLabel(cam_row, text="Câmera", width=200, anchor="w").pack(
            side="left"
        )

        self._cameras = _probe_cameras()
        if self._cameras:
            # Ensure the persisted camera is selectable even if it wasn't
            # detected this time (it may be temporarily unavailable).
            if current_camera not in self._cameras:
                self._cameras.append(current_camera)
                self._cameras.sort()
            cam_labels = [f"Câmera {i}" for i in self._cameras]
            self._camera_menu = ctk.CTkOptionMenu(
                cam_row,
                values=cam_labels,
                width=200,
                command=self._on_camera_change,
            )
            self._camera_menu.set(f"Câmera {current_camera}")
            self._camera_menu.pack(side="left", padx=(10, 0))
        else:
            ctk.CTkLabel(
                cam_row,
                text="Nenhuma câmera detectada",
                text_color="orange",
            ).pack(side="left", padx=(10, 0))
            self._camera_menu = None

        # --- Microphone selector ---
        mic_row = ctk.CTkFrame(self.devices_frame, fg_color="transparent")
        mic_row.pack(fill="x", padx=14, pady=3)
        ctk.CTkLabel(mic_row, text="Microfone", width=200, anchor="w").pack(
            side="left"
        )

        self._mics = _probe_mics()
        if self._mics:
            mic_labels = [name for _, name in self._mics]
            self._mic_menu = ctk.CTkOptionMenu(
                mic_row,
                values=mic_labels,
                width=200,
                command=self._on_mic_change,
            )
            # Select the persisted mic if it's still present.
            current_mic_name = None
            for dev_id, name in self._mics:
                if dev_id == current_mic:
                    current_mic_name = name
                    break
            if current_mic_name:
                self._mic_menu.set(current_mic_name)
            self._mic_menu.pack(side="left", padx=(10, 0))
        else:
            ctk.CTkLabel(
                mic_row,
                text="Nenhum microfone detectado",
                text_color="orange",
            ).pack(side="left", padx=(10, 0))
            self._mic_menu = None

        # --- Pause threshold (same control as the first-launch wizard) ---
        pause_row = ctk.CTkFrame(self.devices_frame, fg_color="transparent")
        pause_row.pack(fill="x", padx=14, pady=(8, 3))
        ctk.CTkLabel(
            pause_row, text="Limiar de Pausa", width=200, anchor="w"
        ).pack(side="left")

        self._pause_threshold = float(settings.get("pause_threshold", 0.7))
        self._pause_save_job = None

        pause_controls = ctk.CTkFrame(pause_row, fg_color="transparent")
        pause_controls.pack(side="left", padx=(10, 0), fill="x", expand=True)
        pause_controls.grid_columnconfigure(0, weight=1)

        self._pause_slider = ctk.CTkSlider(
            pause_controls,
            from_=0.1,
            to=2.0,
            number_of_steps=19,
            command=self._on_pause_change,
        )
        self._pause_slider.set(self._pause_threshold)
        self._pause_slider.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self._pause_value_label = ctk.CTkLabel(
            pause_controls,
            text=f"{self._pause_threshold:.1f}s",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=50,
        )
        self._pause_value_label.grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            self.devices_frame,
            text="Menor = mais responsivo · Maior = menos disparos por ruído",
            font=ctk.CTkFont(size=11),
            text_color=self._SECONDARY_COLOR,
            anchor="w",
        ).pack(anchor="w", padx=14, pady=(0, 14))

    def _on_pause_change(self, value: float):
        """Update the label while dragging; commit after a short debounce."""
        self._pause_threshold = round(float(value), 1)
        self._pause_value_label.configure(text=f"{self._pause_threshold:.1f}s")
        if self._pause_save_job is not None:
            try:
                self.after_cancel(self._pause_save_job)
            except Exception:
                pass
        self._pause_save_job = self.after(500, self._commit_pause)

    def _commit_pause(self):
        """Persist pause_threshold and restart voice with the new value."""
        self._pause_save_job = None
        self._save_devices(pause_threshold=self._pause_threshold)

    def _on_camera_change(self, choice: str):
        """Handle camera dropdown selection."""
        idx = int(choice.split()[-1])
        self._save_devices(camera_index=idx)

    def _on_mic_change(self, choice: str):
        """Handle microphone dropdown selection."""
        mic_id = None
        for dev_id, name in self._mics:
            if name == choice:
                mic_id = dev_id
                break
        self._save_devices(mic_device_id=mic_id)

    def _save_devices(
        self, camera_index=None, mic_device_id=None, pause_threshold=None
    ):
        """Persist device/voice settings and notify the app to restart threads.

        Only the provided keys are updated; the rest of the settings are
        preserved.  ``on_settings_changed`` is invoked with the full current
        values so ``main.py`` can recreate the recognition threads.
        """
        settings = SetupWizard.load_settings()
        if camera_index is not None:
            settings["camera_index"] = camera_index
        if mic_device_id is not None:
            settings["mic_device_id"] = mic_device_id
        if pause_threshold is not None:
            settings["pause_threshold"] = pause_threshold
        SetupWizard.save_settings(settings)

        if self.on_settings_changed:
            self.on_settings_changed(
                settings.get("camera_index", 0),
                settings.get("mic_device_id"),
                settings.get("pause_threshold"),
            )
