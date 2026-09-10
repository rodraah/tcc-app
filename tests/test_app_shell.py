"""Smoke tests for the App shell (gui/app.py).

customtkinter, cv2 and PIL are replaced with minimal fakes so the test runs
hermetically — no real GUI stack or display is required. We only verify that
the module imports and exposes the expected API; widget behavior is not
exercised here.
"""

import inspect
import sys
import types
import unittest
from unittest.mock import Mock, MagicMock
from pathlib import Path

# Ensure the repo root is importable regardless of how pytest is invoked
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# --- Fake widget base -------------------------------------------------------

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

    def after_cancel(self, job):
        pass


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

    def wait_window(self, window):
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


class _FakeImage:
    def __init__(self, **kwargs):
        pass


def _install_fake_modules():
    """Register fake customtkinter/cv2/PIL/pystray/keyboard modules."""
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
    ctk.CTkProgressBar = type("CTkProgressBar", (_FakeWidget,), {
        "set": lambda self, v: None,
    })
    ctk.CTkSwitch = type("CTkSwitch", (_FakeWidget,), {})
    ctk.BooleanVar = lambda value=False: types.SimpleNamespace(
        get=lambda: value, set=lambda v: None
    )
    ctk.CTkFont = _FakeFont
    ctk.CTkImage = _FakeImage
    sys.modules["customtkinter"] = ctk

    cv2 = types.ModuleType("cv2")
    cv2.cvtColor = lambda *args, **kwargs: None
    cv2.COLOR_BGR2RGB = 0
    sys.modules["cv2"] = cv2

    pil_pkg = types.ModuleType("PIL")
    pil_pkg.__path__ = []  # mark as package so `from PIL import Image` works
    pil_image = types.ModuleType("PIL.Image")
    pil_image.Image = type("Image", (), {"LANCZOS": 0})
    pil_image.fromarray = lambda *args, **kwargs: None
    sys.modules["PIL"] = pil_pkg
    sys.modules["PIL.Image"] = pil_image

    pil_imagedraw = types.ModuleType("PIL.ImageDraw")
    pil_imagedraw.ImageDraw = type("ImageDraw", (), {})
    sys.modules["PIL.ImageDraw"] = pil_imagedraw

    # --- Fake pystray ---
    pystray = types.ModuleType("pystray")

    class _FakeMenu:
        def __init__(self, *args, **kwargs):
            pass

    class _FakeMenuItem:
        def __init__(self, *args, **kwargs):
            pass

    class _FakeIcon:
        def __init__(self, *args, **kwargs):
            pass

        def run(self):
            pass

        def stop(self):
            pass

    pystray.Menu = _FakeMenu
    pystray.MenuItem = _FakeMenuItem
    pystray.Icon = _FakeIcon
    sys.modules["pystray"] = pystray

    # --- Fake keyboard ---
    kb = types.ModuleType("keyboard")
    kb.add_hotkey = lambda *a, **kw: None
    kb.remove_hotkey = lambda *a, **kw: None
    kb.wait = lambda *a, **kw: None
    sys.modules["keyboard"] = kb


_install_fake_modules()

from gui.app import App  # noqa: E402  (must come after fake installation)
from gui.tray import TrayIcon  # noqa: E402
from gui.hotkeys import HotkeyListener  # noqa: E402
from gui.widgets.wizard import SetupWizard  # noqa: E402
from gui.pages.gesture_map import GestureMapPage  # noqa: E402
from gui.pages.camera import CameraPage  # noqa: E402
from gui.widgets.status_bar import StatusBar  # noqa: E402


class TestAppShell(unittest.TestCase):
    """Smoke tests: App imports and exposes its public API."""

    def test_app_class_importable(self):
        self.assertTrue(inspect.isclass(App))
        self.assertEqual(App.__name__, "App")

    def test_key_methods_exist(self):
        for method in (
            "show_page",
            "quit_app",
            "update_gesture_status",
            "update_voice_status",
            "push_video_frame",
            "add_log_entry",
        ):
            attr = getattr(App, method, None)
            self.assertTrue(callable(attr), f"missing method: {method}")

    def test_constructor_accepts_callbacks(self):
        params = inspect.signature(App.__init__).parameters
        for param in ("on_start", "on_stop", "on_quit"):
            self.assertIn(param, params)

    def test_update_method_signatures(self):
        sig = inspect.signature(App.update_gesture_status)
        self.assertEqual(
            list(sig.parameters),
            ["self", "name", "confidence", "origin", "action", "hold"],
        )
        self.assertEqual(sig.parameters["confidence"].default, 0.0)
        self.assertEqual(sig.parameters["origin"].default, "")
        self.assertEqual(sig.parameters["action"].default, "")
        self.assertEqual(sig.parameters["hold"].default, 0.0)

        sig = inspect.signature(App.update_voice_status)
        self.assertEqual(list(sig.parameters), ["self", "status", "command"])
        self.assertEqual(sig.parameters["command"].default, "")

        sig = inspect.signature(App.add_log_entry)
        self.assertEqual(list(sig.parameters), ["self", "message", "module"])
        self.assertEqual(sig.parameters["module"].default, "system")

    def test_gesture_update_methods_accept_action(self):
        """CameraPage/StatusBar update_gesture accept an ``action`` param."""
        sig = inspect.signature(CameraPage.update_gesture)
        self.assertEqual(
            list(sig.parameters),
            ["self", "name", "confidence", "origin", "action", "hold"],
        )
        self.assertEqual(sig.parameters["action"].default, "")
        self.assertEqual(sig.parameters["hold"].default, 0.0)

        sig = inspect.signature(StatusBar.update_gesture)
        self.assertEqual(
            list(sig.parameters),
            ["self", "name", "confidence", "origin", "action"],
        )
        self.assertEqual(sig.parameters["action"].default, "")

    def test_show_page_takes_page_name(self):
        sig = inspect.signature(App.show_page)
        self.assertEqual(list(sig.parameters), ["self", "name"])


class TestTrayIcon(unittest.TestCase):
    """Smoke tests: TrayIcon imports and exposes its public API."""

    def test_class_importable(self):
        self.assertTrue(inspect.isclass(TrayIcon))
        self.assertEqual(TrayIcon.__name__, "TrayIcon")

    def test_constructor_takes_app(self):
        params = inspect.signature(TrayIcon.__init__).parameters
        self.assertIn("app", params)

    def test_key_methods_exist(self):
        for method in ("start", "stop", "hide_app"):
            attr = getattr(TrayIcon, method, None)
            self.assertTrue(callable(attr), f"missing method: {method}")


class TestHotkeyListener(unittest.TestCase):
    """Smoke tests: HotkeyListener imports and exposes its public API."""

    def test_class_importable(self):
        self.assertTrue(inspect.isclass(HotkeyListener))
        self.assertEqual(HotkeyListener.__name__, "HotkeyListener")

    def test_constructor_takes_app_and_hotkey(self):
        params = inspect.signature(HotkeyListener.__init__).parameters
        self.assertIn("app", params)
        self.assertIn("hotkey", params)
        self.assertEqual(params["hotkey"].default, "F9")

    def test_key_methods_exist(self):
        for method in ("start", "stop"):
            attr = getattr(HotkeyListener, method, None)
            self.assertTrue(callable(attr), f"missing method: {method}")


class TestShowAndStart(unittest.TestCase):
    """Tests for App.show_and_start() and hotkey toggle integration."""

    def test_show_and_start_exists(self):
        self.assertTrue(callable(getattr(App, "show_and_start", None)))

    def test_show_and_start_deiconifies_and_starts(self):
        """When window is hidden and not running, show_and_start shows + starts."""
        app = App.__new__(App)
        app.running = False
        app.deiconify = unittest.mock.Mock()
        app.lift = unittest.mock.Mock()
        app.focus_force = unittest.mock.Mock()
        app._handle_start = unittest.mock.Mock()

        app.show_and_start()

        app.deiconify.assert_called_once()
        app.lift.assert_called_once()
        app.focus_force.assert_called_once()
        app._handle_start.assert_called_once()

    def test_show_and_start_skips_start_when_already_running(self):
        """When already running, show_and_start shows window but does NOT re-start."""
        app = App.__new__(App)
        app.running = True
        app.deiconify = unittest.mock.Mock()
        app.lift = unittest.mock.Mock()
        app.focus_force = unittest.mock.Mock()
        app._handle_start = unittest.mock.Mock()

        app.show_and_start()

        app.deiconify.assert_called_once()
        app.lift.assert_called_once()
        app.focus_force.assert_called_once()
        app._handle_start.assert_not_called()

    def test_hotkey_toggle_calls_show_and_start_when_hidden(self):
        """When the window is not viewable, _toggle_visibility dispatches show_and_start."""
        app = unittest.mock.MagicMock(spec=App)
        app.winfo_viewable.return_value = False

        listener = HotkeyListener(app, hotkey="F9")

        # Capture the callback passed to app.after
        captured_cb = []

        def fake_after(ms, func, *args):
            captured_cb.append(func)
            return None

        app.after = fake_after

        listener._toggle_visibility()

        self.assertEqual(len(captured_cb), 1)
        # Execute the captured callback and verify it calls show_and_start
        captured_cb[0]()
        app.show_and_start.assert_called_once()
        app.withdraw.assert_not_called()

    def test_hotkey_toggle_withdraws_when_viewable(self):
        """When the window is viewable, _toggle_visibility hides it (no start)."""
        app = unittest.mock.MagicMock(spec=App)
        app.winfo_viewable.return_value = True

        listener = HotkeyListener(app, hotkey="F9")

        captured_cb = []

        def fake_after(ms, func, *args):
            captured_cb.append(func)
            return None

        app.after = fake_after

        listener._toggle_visibility()

        self.assertEqual(len(captured_cb), 1)
        captured_cb[0]()
        app.withdraw.assert_called_once()
        app.show_and_start.assert_not_called()


class TestSetupWizard(unittest.TestCase):
    """Smoke tests: SetupWizard imports and exposes its public API."""

    def test_class_importable(self):
        self.assertTrue(inspect.isclass(SetupWizard))
        self.assertEqual(SetupWizard.__name__, "SetupWizard")

    def test_key_static_methods_exist(self):
        for method in ("should_run", "load_settings", "save_settings"):
            attr = getattr(SetupWizard, method, None)
            self.assertTrue(callable(attr), f"missing static method: {method}")

    def test_inherits_ctk_toplevel(self):
        import customtkinter as ctk
        self.assertTrue(issubclass(SetupWizard, ctk.CTkToplevel))


class TestGestureMapPage(unittest.TestCase):
    """Smoke tests: GestureMapPage imports and exposes its public API.

    The page is never instantiated here — the fake CTkOptionMenu has no
    get/set methods, and building the page would pull in the gesture package.
    """

    def test_class_importable(self):
        self.assertTrue(inspect.isclass(GestureMapPage))
        self.assertEqual(GestureMapPage.__name__, "GestureMapPage")

    def test_new_mapping_methods_exist(self):
        for method in ("_available_actions", "_on_action_change"):
            attr = getattr(GestureMapPage, method, None)
            self.assertTrue(callable(attr), f"missing method: {method}")

    def test_existing_mapping_api_preserved(self):
        for method in (
            "_save_mapping",
            "_add_mapping_row",
            "_add_binding",
            "_remove_binding",
        ):
            attr = getattr(GestureMapPage, method, None)
            self.assertTrue(callable(attr), f"missing method: {method}")


if __name__ == "__main__":
    unittest.main()
