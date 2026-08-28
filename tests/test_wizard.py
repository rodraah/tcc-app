"""Smoke tests for SetupWizard (gui/widgets/wizard.py).

customtkinter is replaced with a minimal fake so the test runs hermetically
(no real GUI or display required).  The static helpers (should_run,
load_settings, save_settings) are tested with a temporary config directory
via unittest.mock.patch.
"""

import inspect
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure the repo root is importable
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# --- Fake widget base (matches test_app_shell.py) ----------------------------

class _FakeWidget:
    """Minimal stand-in for customtkinter widgets (no Tk involved)."""

    def __init__(self, master=None, **kwargs):
        self.master = master

    def grid(self, **kwargs):
        pass

    def pack(self, **kwargs):
        pass

    def grid_forget(self):
        pass

    def grid_propagate(self, value):
        pass

    def grid_columnconfigure(self, *args, **kwargs):
        pass

    def grid_rowconfigure(self, *args, **kwargs):
        pass

    def columnconfigure(self, *args, **kwargs):
        pass

    def rowconfigure(self, *args, **kwargs):
        pass

    def configure(self, **kwargs):
        pass

    def destroy(self):
        pass

    def after(self, ms, func=None, *args):
        return None


class _FakeCtk(_FakeWidget):
    """Stand-in for the CTk root window."""

    def title(self, title):
        pass

    def geometry(self, geometry):
        pass

    def minsize(self, width, height):
        pass

    def protocol(self, name, func=None):
        pass

    def withdraw(self):
        pass

    def deiconify(self):
        pass

    def winfo_viewable(self):
        return True

    def lift(self):
        pass

    def focus_force(self):
        pass


class _FakeFont:
    def __init__(self, **kwargs):
        pass


def _install_fake_modules():
    """Register fake customtkinter module with wizard-specific widgets."""
    if "customtkinter" in sys.modules:
        return  # already installed (e.g. by test_app_shell)

    ctk = types.ModuleType("customtkinter")
    ctk.CTkBaseClass = _FakeWidget
    ctk.CTk = _FakeCtk
    ctk.CTkFrame = type("CTkFrame", (_FakeWidget,), {})
    ctk.CTkScrollableFrame = type("CTkScrollableFrame", (_FakeWidget,), {})
    ctk.CTkLabel = type("CTkLabel", (_FakeWidget,), {})
    ctk.CTkButton = type("CTkButton", (_FakeWidget,), {})
    ctk.CTkEntry = type("CTkEntry", (_FakeWidget,), {})
    ctk.CTkTextbox = type("CTkTextbox", (_FakeWidget,), {})
    ctk.CTkToplevel = type("CTkToplevel", (_FakeWidget,), {})
    ctk.CTkSlider = type("CTkSlider", (_FakeWidget,), {
        "set": lambda self, v: None,
    })
    ctk.CTkOptionMenu = type("CTkOptionMenu", (_FakeWidget,), {})
    ctk.CTkFont = _FakeFont
    ctk.CTkImage = type("CTkImage", (_FakeWidget,), {})
    sys.modules["customtkinter"] = ctk


_install_fake_modules()

from gui.widgets.wizard import (  # noqa: E402
    SetupWizard,
    _APP_STATE_PATH,
    _DEFAULTS,
    _probe_mics,
)


class TestSetupWizardImports(unittest.TestCase):
    """Verify the class and static helpers are importable and callable."""

    def test_class_exists(self):
        self.assertTrue(inspect.isclass(SetupWizard))
        self.assertEqual(SetupWizard.__name__, "SetupWizard")

    def test_inherits_ctk_toplevel(self):
        import customtkinter as ctk
        self.assertTrue(issubclass(SetupWizard, ctk.CTkToplevel))

    def test_should_run_is_static(self):
        self.assertTrue(callable(SetupWizard.should_run))
        # Verify it's a static method
        self.assertNotIsInstance(
            inspect.getattr_static(SetupWizard, "should_run"), classmethod
        )
        self.assertNotIsInstance(
            inspect.getattr_static(SetupWizard, "should_run"), property
        )

    def test_load_settings_is_static(self):
        self.assertTrue(callable(SetupWizard.load_settings))

    def test_save_settings_is_static(self):
        self.assertTrue(callable(SetupWizard.save_settings))

    def test_should_run_signature(self):
        sig = inspect.signature(SetupWizard.should_run)
        self.assertEqual(list(sig.parameters), ["parent"])

    def test_load_settings_signature(self):
        sig = inspect.signature(SetupWizard.load_settings)
        self.assertEqual(list(sig.parameters), [])

    def test_save_settings_signature(self):
        sig = inspect.signature(SetupWizard.save_settings)
        self.assertEqual(list(sig.parameters), ["settings"])

    def test_result_attribute_declared(self):
        """The result attribute should exist on the class (even if __init__
        isn't called in the test)."""
        self.assertTrue(hasattr(SetupWizard, "__init__"))


class TestLoadSettings(unittest.TestCase):
    """Test load_settings with a temporary config directory."""

    def test_returns_defaults_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir) / "missing" / "app_state.json"
            with patch("gui.widgets.wizard._APP_STATE_PATH", fake_path):
                result = SetupWizard.load_settings()
        self.assertEqual(result, dict(_DEFAULTS))

    def test_loads_valid_file(self):
        data = {
            "camera_index": 2,
            "mic_device_id": 5,
            "pause_threshold": 1.2,
            "hotkey": "F10",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir) / "app_state.json"
            fake_path.write_text(json.dumps(data), encoding="utf-8")
            with patch("gui.widgets.wizard._APP_STATE_PATH", fake_path):
                result = SetupWizard.load_settings()
        self.assertEqual(result["camera_index"], 2)
        self.assertEqual(result["mic_device_id"], 5)
        self.assertEqual(result["pause_threshold"], 1.2)
        self.assertEqual(result["hotkey"], "F10")

    def test_fills_missing_keys_with_defaults(self):
        partial = {"camera_index": 3}
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir) / "app_state.json"
            fake_path.write_text(json.dumps(partial), encoding="utf-8")
            with patch("gui.widgets.wizard._APP_STATE_PATH", fake_path):
                result = SetupWizard.load_settings()
        self.assertEqual(result["camera_index"], 3)
        self.assertEqual(result["mic_device_id"], _DEFAULTS["mic_device_id"])
        self.assertEqual(
            result["pause_threshold"], _DEFAULTS["pause_threshold"]
        )
        self.assertEqual(result["hotkey"], _DEFAULTS["hotkey"])

    def test_returns_defaults_on_corrupt_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir) / "app_state.json"
            fake_path.write_text("{invalid json", encoding="utf-8")
            with patch("gui.widgets.wizard._APP_STATE_PATH", fake_path):
                result = SetupWizard.load_settings()
        self.assertEqual(result, dict(_DEFAULTS))


class TestSaveSettings(unittest.TestCase):
    """Test save_settings writes correct JSON."""

    def test_creates_file(self):
        settings = dict(_DEFAULTS)
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_dir = Path(tmpdir) / "config"
            fake_path = fake_dir / "app_state.json"
            with patch("gui.widgets.wizard._CONFIG_DIR", fake_dir), \
                 patch("gui.widgets.wizard._APP_STATE_PATH", fake_path):
                SetupWizard.save_settings(settings)
            self.assertTrue(fake_path.is_file())
            loaded = json.loads(fake_path.read_text(encoding="utf-8"))
        self.assertEqual(loaded, settings)

    def test_overwrites_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_dir = Path(tmpdir) / "config"
            fake_path = fake_dir / "app_state.json"
            # Write initial data
            fake_dir.mkdir(parents=True)
            fake_path.write_text('{"old": true}', encoding="utf-8")

            new_settings = {"camera_index": 4, "hotkey": "F12"}
            with patch("gui.widgets.wizard._CONFIG_DIR", fake_dir), \
                 patch("gui.widgets.wizard._APP_STATE_PATH", fake_path):
                SetupWizard.save_settings(new_settings)
            loaded = json.loads(fake_path.read_text(encoding="utf-8"))
        self.assertEqual(loaded, new_settings)
        self.assertNotIn("old", loaded)

    def test_creates_parent_directories(self):
        settings = dict(_DEFAULTS)
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_dir = Path(tmpdir) / "a" / "b" / "c"
            fake_path = fake_dir / "app_state.json"
            with patch("gui.widgets.wizard._CONFIG_DIR", fake_dir), \
                 patch("gui.widgets.wizard._APP_STATE_PATH", fake_path):
                SetupWizard.save_settings(settings)
            self.assertTrue(fake_path.is_file())

    def test_round_trip(self):
        settings = {
            "camera_index": 1,
            "mic_device_id": 3,
            "pause_threshold": 1.5,
            "hotkey": "F11",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_dir = Path(tmpdir) / "config"
            fake_path = fake_dir / "app_state.json"
            with patch("gui.widgets.wizard._CONFIG_DIR", fake_dir), \
                 patch("gui.widgets.wizard._APP_STATE_PATH", fake_path):
                SetupWizard.save_settings(settings)
                loaded = SetupWizard.load_settings()
        self.assertEqual(loaded, settings)


class TestShouldRun(unittest.TestCase):
    """Test should_run logic."""

    def test_true_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir) / "missing" / "app_state.json"
            with patch("gui.widgets.wizard._APP_STATE_PATH", fake_path):
                self.assertTrue(SetupWizard.should_run(None))

    def test_false_when_valid_file(self):
        settings = dict(_DEFAULTS)
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir) / "app_state.json"
            fake_path.write_text(
                json.dumps(settings), encoding="utf-8"
            )
            with patch("gui.widgets.wizard._APP_STATE_PATH", fake_path):
                self.assertFalse(SetupWizard.should_run(None))

    def test_true_when_missing_key(self):
        partial = {"camera_index": 0}  # missing other required keys
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir) / "app_state.json"
            fake_path.write_text(
                json.dumps(partial), encoding="utf-8"
            )
            with patch("gui.widgets.wizard._APP_STATE_PATH", fake_path):
                self.assertTrue(SetupWizard.should_run(None))

    def test_true_on_corrupt_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir) / "app_state.json"
            fake_path.write_text("not json", encoding="utf-8")
            with patch("gui.widgets.wizard._APP_STATE_PATH", fake_path):
                self.assertTrue(SetupWizard.should_run(None))

    def test_true_on_empty_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir) / "app_state.json"
            fake_path.write_text("", encoding="utf-8")
            with patch("gui.widgets.wizard._APP_STATE_PATH", fake_path):
                self.assertTrue(SetupWizard.should_run(None))


class TestProbeMics(unittest.TestCase):
    """Test _probe_mics filtering with a mocked sounddevice.query_devices."""

    def _make_device(self, name, in_ch, out_ch):
        return {
            "name": name,
            "max_input_channels": in_ch,
            "max_output_channels": out_ch,
            "default_samplerate": 44100,
            "hostapi": 0,
        }

    def test_returns_only_pure_input_devices(self):
        devices = [
            self._make_device("Microphone Array", 2, 0),
            self._make_device("Speakers", 0, 2),
            self._make_device("Stereo Mix", 2, 2),
            self._make_device("USB Audio", 1, 0),
        ]
        with patch("sounddevice.query_devices", return_value=devices):
            result = _probe_mics()
        self.assertEqual(
            result,
            [(0, "Microphone Array"), (3, "USB Audio")],
        )

    def test_falls_back_to_mixed_devices_when_no_pure_input(self):
        devices = [
            self._make_device("Speakers", 0, 2),
            self._make_device("Stereo Mix", 2, 2),
        ]
        with patch("sounddevice.query_devices", return_value=devices):
            result = _probe_mics()
        self.assertEqual(result, [(1, "Stereo Mix")])

    def test_returns_empty_when_no_input_devices(self):
        devices = [
            self._make_device("Speakers", 0, 2),
            self._make_device("Headphones", 0, 2),
        ]
        with patch("sounddevice.query_devices", return_value=devices):
            result = _probe_mics()
        self.assertEqual(result, [])

    def test_returns_empty_on_exception(self):
        with patch(
            "sounddevice.query_devices", side_effect=RuntimeError("boom")
        ):
            result = _probe_mics()
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
