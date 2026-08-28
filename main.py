"""Unified entry point: wizard -> app -> hotkey -> tray -> mainloop."""

from __future__ import annotations

import queue
import sys
import threading

from gui.app import App
from gui.hotkeys import HotkeyListener
from gui.tray import TrayIcon
from gui.widgets.wizard import SetupWizard


def main() -> None:
    """Launch the TCC-App.

    Flow:
        1. Run the first-launch wizard if ``config/app_state.json`` is missing
           or invalid.  If the user cancels, exit immediately.
        2. Create the App window.
        3. Load persisted settings and create background threads.
        4. Wire thread queues to the App, start hotkey + tray.
        5. Enter the CTk mainloop (blocks until ``quit_app()`` is called).
        6. Clean up threads, hotkey and tray on exit.
    """

    # 1. Wizard — only on first launch or corrupt config.
    #    Run BEFORE creating the main App window so the wizard is truly modal
    #    and the main window doesn't flash behind it.
    if SetupWizard.should_run(None):
        # Create a temporary hidden root for the wizard
        import customtkinter as ctk
        temp_root = ctk.CTk()
        temp_root.withdraw()  # Hide the temporary root
        wizard = SetupWizard(temp_root)
        temp_root.wait_window(wizard)
        temp_root.destroy()
        if not wizard.result:
            return

    # 2. Create the App window.
    app = App()

    # 3. Load persisted settings.
    settings = SetupWizard.load_settings()
    hotkey_combo: str = settings.get("hotkey", "F9")

    # 4. Create background recognition threads.
    #    Lazy import so that missing gesture/voice deps don't crash the app
    #    at import time — the thread classes themselves handle ImportError.
    #    Threads are stored in a mutable dict so the settings page can
    #    recreate them at runtime with a new camera/mic.
    state: dict = {"gesture_thread": None, "voice_thread": None}
    shared_error_queue: queue.Queue = queue.Queue(maxsize=1)

    def _create_threads(camera_index, mic_device_id, pause_threshold):
        """(Re)create the gesture and voice threads with the given devices."""
        gesture_thread = None
        voice_thread = None
        try:
            from gui.threads import GestureThread, VoiceThread

            gesture_thread = GestureThread(camera_index=camera_index)
            voice_thread = VoiceThread(
                mic_device_id=mic_device_id,
                pause_threshold=pause_threshold,
            )
        except Exception as exc:
            print(
                f"[main] Aviso: não foi possível criar as threads de reconhecimento: {exc}",
                file=sys.stderr,
            )

        # Both threads share a single error queue so the App polls one queue
        # and shows a dialog regardless of which thread reported the error.
        if gesture_thread is not None:
            gesture_thread.error_queue = shared_error_queue
        if voice_thread is not None:
            voice_thread.error_queue = shared_error_queue

        state["gesture_thread"] = gesture_thread
        state["voice_thread"] = voice_thread
        return gesture_thread, voice_thread

    _create_threads(
        settings.get("camera_index", 0),
        settings.get("mic_device_id"),
        settings.get("pause_threshold"),
    )

    # 5. Connect thread queues to the App (safe even if threads are None
    #    — the queues will just never receive data).
    def _wire_queues() -> None:
        gt = state["gesture_thread"]
        vt = state["voice_thread"]
        if gt is not None and vt is not None:
            app.set_queues(
                frame_queue=gt.frame_queue,
                gesture_queue=gt.gesture_queue,
                log_queue=gt.log_queue,
                action_queue=gt.action_queue,
                voice_status_queue=vt.status_queue,
                transcript_queue=vt.transcript_queue,
                error_queue=shared_error_queue,
            )

    _wire_queues()

    # 6. Wire start/stop callbacks — these fire when the user clicks
    #    Start / Stop in the status bar.
    def _on_start() -> None:
        gt = state["gesture_thread"]
        vt = state["voice_thread"]
        if gt is not None:
            gt.start()
        if vt is not None:
            vt.start()
            # Bridge voice log queue → app log queue (drained by _poll_log)
            _drain_voice_logs()

    def _stop_worker() -> None:
        """Stop both recognition threads (runs on a daemon thread).

        The joins inside ``GestureThread.stop()`` (≤5s) and
        ``VoiceThread.stop()`` (≤12s) must never run on the main thread —
        they would freeze the UI.  This worker is spawned by ``_on_stop``,
        ``_cleanup`` and the settings-change handler so the main thread
        returns immediately.
        """
        gt = state["gesture_thread"]
        vt = state["voice_thread"]
        if gt is not None:
            try:
                gt.stop()
            except Exception:
                pass
        if vt is not None:
            try:
                vt.stop()
            except Exception:
                pass

    def _on_stop() -> None:
        threading.Thread(
            target=_stop_worker, name="stop-worker", daemon=True
        ).start()

    app.on_start = _on_start
    app.on_stop = _on_stop

    # Helper: forward voice log entries into the app's log queue
    # so the GUI's _poll_log can display them in the Log page.
    def _drain_voice_logs() -> None:
        """Periodically bridge voice_thread.log_queue → app._log_queue.

        Schedules itself via ``after()`` while the app is running so that
        voice log entries are continuously forwarded to the GUI.
        """
        vt = state["voice_thread"]
        if vt is None:
            return
        try:
            while True:
                message, module = vt.log_queue.get_nowait()
                try:
                    app._log_queue.put_nowait((message, module))
                except Exception:
                    break
        except Exception:
            pass
        if app.running:
            app.after(100, _drain_voice_logs)

    # Settings changed (camera/mic) — restart recognition threads.
    def _on_settings_changed(camera_index, mic_device_id) -> None:
        """Recreate the recognition threads with the new camera/mic.

        The old threads are stopped on a background worker (blocking joins
        must not run on the main thread).  Once they are fully stopped — which
        clears the ``VoiceAssistant`` process-wide singleton guard — the new
        threads are created, rewired and restarted on the main thread.
        """
        def _recreate() -> None:
            _create_threads(
                camera_index,
                mic_device_id,
                settings.get("pause_threshold"),
            )
            _wire_queues()
            if app.running:
                _on_start()

        def _worker() -> None:
            _stop_worker()  # blocking; clears the voice singleton guard
            app.after(0, _recreate)  # recreate on the main thread

        threading.Thread(
            target=_worker, name="settings-restart", daemon=True
        ).start()

    app.on_settings_changed = _on_settings_changed

    # 7. Start the global hotkey listener.
    listener: HotkeyListener | None = None
    try:
        listener = HotkeyListener(app, hotkey=hotkey_combo)
        listener.start()
    except Exception as exc:
        print(f"[main] Aviso: falha ao iniciar o ouvinte de atalho: {exc}", file=sys.stderr)

    # 8. Start the system-tray icon.
    tray: TrayIcon | None = None
    try:
        tray = TrayIcon(app)
        tray.start()
    except Exception as exc:
        print(f"[main] Aviso: falha ao iniciar o ícone da bandeja: {exc}", file=sys.stderr)

    # 9. Cleanup callback — invoked by app.quit_app().
    def _cleanup() -> None:
        # Stop recognition threads in the background so quitting is instant
        # (the joins can take up to several seconds).
        threading.Thread(
            target=_stop_worker, name="cleanup-stop", daemon=True
        ).start()
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass
        if tray is not None:
            try:
                tray.stop()
            except Exception:
                pass

    app.on_quit = _cleanup

    # 10. Enter mainloop — blocks until the user quits.
    app.mainloop()


if __name__ == "__main__":
    main()
