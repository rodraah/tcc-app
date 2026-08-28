"""Smoke tests for main.py — the unified entry point.

Reuses the fake-module infrastructure from test_app_shell.py so that
both test files use the same stub classes (avoids identity conflicts
when run together).
"""

import inspect
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure the repo root is importable
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Trigger test_app_shell to load first — it installs the canonical fakes
# and creates SetupWizard with the canonical CTkToplevel.  We must NOT
# call _install_fake_modules() again because that creates a *new* set of
# fake classes, breaking issubclass() checks in test_app_shell.
# ---------------------------------------------------------------------------
import tests.test_app_shell  # noqa: E402, F401  (installs fakes at module level)

from main import main  # noqa: E402  (must come after fake installation)


class TestMainFunction(unittest.TestCase):
    """Verify that the main() entry point exists and is well-formed."""

    def test_main_is_callable(self):
        self.assertTrue(callable(main))

    def test_main_has_no_required_params(self):
        sig = inspect.signature(main)
        required = [
            p for p in sig.parameters.values()
            if p.default is inspect.Parameter.empty
        ]
        self.assertEqual(required, [], "main() should take no required arguments")


class TestMainFlowNoWizard(unittest.TestCase):
    """When should_run() returns False, wizard is skipped and the full
    startup sequence (hotkey + tray + mainloop) is exercised."""

    @patch("main.TrayIcon")
    @patch("main.HotkeyListener")
    @patch("main.SetupWizard")
    @patch("main.App")
    def test_full_startup_skips_wizard(
        self, MockApp, MockWizard, MockHotkey, MockTray
    ):
        mock_app = MockApp.return_value
        MockWizard.should_run.return_value = False
        MockWizard.load_settings.return_value = {"hotkey": "F9"}

        main()

        # App was created
        MockApp.assert_called_once()

        # Wizard was not shown
        MockWizard.assert_not_called()

        # Hotkey started
        mock_listener = MockHotkey.return_value
        MockHotkey.assert_called_once_with(mock_app, hotkey="F9")
        mock_listener.start.assert_called_once()

        # Tray started
        mock_tray = MockTray.return_value
        MockTray.assert_called_once_with(mock_app)
        mock_tray.start.assert_called_once()

        # mainloop was entered
        mock_app.mainloop.assert_called_once()

        # on_quit was set (to a callable)
        self.assertTrue(callable(mock_app.on_quit))


class TestMainFlowWizardCompleted(unittest.TestCase):
    """When should_run() returns True and the user completes the wizard,
    the settings from the wizard file are used."""

    @patch("main.TrayIcon")
    @patch("main.HotkeyListener")
    @patch("main.SetupWizard")
    @patch("main.App")
    def test_wizard_completes_with_hotkey(
        self, MockApp, MockWizard, MockHotkey, MockTray
    ):
        mock_app = MockApp.return_value
        MockWizard.should_run.return_value = True

        # Simulate a completed wizard
        mock_wizard = MagicMock()
        mock_wizard.result = True
        MockWizard.return_value = mock_wizard

        # after wait_window, settings are loadable
        MockWizard.load_settings.return_value = {"hotkey": "Ctrl+Alt+G"}

        main()

        # Wizard was created (with a temporary root, not the app)
        MockWizard.assert_called_once()
        # The first arg should be a CTk instance (temp root)
        call_args = MockWizard.call_args[0]
        self.assertIsNotNone(call_args[0])

        # Hotkey uses the wizard-saved combo
        MockHotkey.assert_called_once_with(mock_app, hotkey="Ctrl+Alt+G")
        MockHotkey.return_value.start.assert_called_once()

        mock_app.mainloop.assert_called_once()


class TestMainFlowWizardCancelled(unittest.TestCase):
    """When the user cancels the wizard, the app exits immediately."""

    @patch("main.TrayIcon")
    @patch("main.HotkeyListener")
    @patch("main.SetupWizard")
    @patch("main.App")
    def test_wizard_cancelled_quits_app(
        self, MockApp, MockWizard, MockHotkey, MockTray
    ):
        MockWizard.should_run.return_value = True

        mock_wizard = MagicMock()
        mock_wizard.result = False  # user cancelled
        MockWizard.return_value = mock_wizard

        main()

        # App was quit immediately — no hotkey/tray/mainloop
        # Note: App is never created when wizard is cancelled
        MockApp.assert_not_called()
        MockHotkey.assert_not_called()
        MockTray.assert_not_called()


class TestMainCleanupOnQuit(unittest.TestCase):
    """The on_quit callback registered on the app should stop hotkey + tray."""

    @patch("main.TrayIcon")
    @patch("main.HotkeyListener")
    @patch("main.SetupWizard")
    @patch("main.App")
    def test_cleanup_stops_hotkey_and_tray(
        self, MockApp, MockWizard, MockHotkey, MockTray
    ):
        mock_app = MockApp.return_value
        MockWizard.should_run.return_value = False
        MockWizard.load_settings.return_value = {"hotkey": "F9"}

        main()

        # Grab the cleanup function that was set as on_quit
        cleanup_fn = mock_app.on_quit
        self.assertTrue(callable(cleanup_fn))

        # Call it — should stop both listener and tray
        cleanup_fn()
        MockHotkey.return_value.stop.assert_called_once()
        MockTray.return_value.stop.assert_called_once()


class TestMainHotkeyFailureContinues(unittest.TestCase):
    """If the hotkey listener fails to start, the app still launches."""

    @patch("main.TrayIcon")
    @patch("main.HotkeyListener")
    @patch("main.SetupWizard")
    @patch("main.App")
    def test_hotkey_failure_does_not_block_app(
        self, MockApp, MockWizard, MockHotkey, MockTray
    ):
        mock_app = MockApp.return_value
        MockWizard.should_run.return_value = False
        MockWizard.load_settings.return_value = {"hotkey": "F9"}

        MockHotkey.return_value.start.side_effect = RuntimeError("no permission")

        main()

        # Tray and mainloop still started
        MockTray.return_value.start.assert_called_once()
        mock_app.mainloop.assert_called_once()


class TestMainTrayFailureContinues(unittest.TestCase):
    """If the tray icon fails to start, the app still launches."""

    @patch("main.TrayIcon")
    @patch("main.HotkeyListener")
    @patch("main.SetupWizard")
    @patch("main.App")
    def test_tray_failure_does_not_block_app(
        self, MockApp, MockWizard, MockHotkey, MockTray
    ):
        mock_app = MockApp.return_value
        MockWizard.should_run.return_value = False
        MockWizard.load_settings.return_value = {"hotkey": "F9"}

        MockTray.return_value.start.side_effect = RuntimeError("no tray")

        main()

        # Hotkey and mainloop still started
        MockHotkey.return_value.start.assert_called_once()
        mock_app.mainloop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
