"""Public facade for the voice assistant.

Usage::

    from voice.assistant import VoiceAssistant
    from voice.models import Callbacks

    va = VoiceAssistant(engine="vosk", callbacks=Callbacks(on_transcript=print))
    va.start()
    va.wait()
    va.shutdown()
"""

from __future__ import annotations

import atexit
import threading
from pathlib import Path


from voice import tts as _tts
from voice.executor import Executor
from voice.intent_parser import IntentParser
from voice.listener import HybridListener
from voice.logger import setup_logging
from voice.loop import Loop
from voice.models import Callbacks, Intent
from voice.paths import DEFAULT_CONFIG

_active_instance: VoiceAssistant | None = None  # process-wide singleton guard
_instance_lock = threading.Lock()


class VoiceAssistant:
    """Public facade for the voice assistant."""

    def __init__(
        self,
        *,
        engine: str | None = None,
        config_path: str | Path | None = None,
        callbacks: Callbacks | None = None,
        push_to_talk: bool = True,
        mic_device_id: int | None = None,
        pause_threshold: float | None = None,
    ) -> None:
        global _active_instance  # noqa: PLW0603

        # B3 FIX: singleton guard — set ONLY after successful init
        with _instance_lock:
            if _active_instance is not None:
                raise RuntimeError(
                    "A VoiceAssistant instance is already active. "
                    "Shut it down first."
                )

        try:
            self._init_internal(
                engine,
                config_path,
                callbacks,
                push_to_talk,
                mic_device_id,
                pause_threshold,
            )
        except Exception:
            # Clear guard on failed construction
            with _instance_lock:
                _active_instance = None
            raise

        # Set singleton only after successful init
        with _instance_lock:
            _active_instance = self

        # atexit safety net (register AFTER successful init, W7)
        atexit.register(self._atexit_shutdown)

    # ------------------------------------------------------------------
    # Internal init (isolated so the except/raise above works)
    # ------------------------------------------------------------------

    def _init_internal(
        self,
        engine: str | None,
        config_path: str | Path | None,
        callbacks: Callbacks | None,
        push_to_talk: bool,
        mic_device_id: int | None,
        pause_threshold: float | None,
    ) -> None:
        setup_logging()

        self._config_path = Path(config_path) if config_path else DEFAULT_CONFIG
        self._callbacks = callbacks or Callbacks()

        # Load config via IntentParser
        self._parser = IntentParser(self._config_path)
        config = self._parser.config

        # Create executor (builds BrowserSession lazily)
        self._executor = Executor(config, on_error=self._callbacks.on_error)

        # Create listener (opens mic + calibrates)
        self._listener = HybridListener(
            config,
            engine_name=engine,
            mic_device_id=mic_device_id,
            pause_threshold=pause_threshold,
            on_error=self._callbacks.on_error,
        )

        # Create loop
        self._loop = Loop(self._listener, self._parser, self._executor,
                          callbacks=self._callbacks)

        # Push-to-talk (W13: lazy pynput import via src.push_to_talk)
        self._ptt: PushToTalk | None = None
        if push_to_talk:
            from voice.push_to_talk import PushToTalk

            self._ptt = PushToTalk(self._listener)
            self._ptt.start()

        # Thread state
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._started = False
        self._shutdown_done = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the automated listen→parse→execute loop on a daemon thread."""
        if self._started:
            return  # idempotent
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop.run,
            args=(self._stop_event,),
            name="voice-assistant-loop",
            daemon=True,
        )
        self._thread.start()
        self._started = True
        self._emit_status("started")

    def stop(self, timeout: float | None = None) -> None:
        """Stop the loop. Idempotent."""
        if not self._started:
            return
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout or 12.0)
        self._started = False
        self._emit_status("stopped")

    def wait(self, timeout: float | None = None) -> bool:
        """Block until stopped. Returns True if stopped, False on timeout."""
        if not self._started:
            return True
        return self._stop_event.wait(timeout)

    def shutdown(self) -> None:
        """Full cleanup. Idempotent and terminal."""
        global _active_instance  # noqa: PLW0603
        if self._shutdown_done:
            return

        # Step 1: Stop the loop (MUST join before closing mic)
        self.stop()

        # Step 2: Stop push-to-talk
        if self._ptt:
            self._ptt.stop()

        # Step 3: Close mic
        try:
            self._listener.close()
        except Exception:
            pass

        # Step 4: Close browser / executor
        try:
            self._executor.shutdown()
        except Exception:
            pass

        # Step 5: Shut down TTS
        try:
            _tts.shutdown(timeout=5.0)
        except Exception:
            pass

        # Step 6: Clear singleton guard
        with _instance_lock:
            _active_instance = None

        self._shutdown_done = True
        self._emit_status("shutdown")

    def _atexit_shutdown(self) -> None:
        """atexit safety net."""
        try:
            self.shutdown()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Push-to-talk / pause
    # ------------------------------------------------------------------

    def set_push_to_talk(self, enabled: bool) -> None:
        if self._ptt is None:
            return
        if enabled and not self._ptt.enabled:
            self._ptt.start()
        elif not enabled and self._ptt.enabled:
            self._ptt.stop()

    @property
    def push_to_talk_enabled(self) -> bool:
        return self._ptt is not None and self._ptt.enabled

    def set_paused(self, paused: bool) -> None:
        self._listener.set_paused(paused)

    @property
    def paused(self) -> bool:
        return self._listener.paused

    # ------------------------------------------------------------------
    # Manual mode (W9: direct parse+execute, no state machine)
    # ------------------------------------------------------------------

    def listen_once(self, timeout: float | None = None) -> str | None:
        """Single listen cycle. Raises RuntimeError if loop is running."""
        if self._started:
            raise RuntimeError(
                "Cannot use manual mode while the loop is running. "
                "Call stop() first."
            )
        return self._listener.listen_once(timeout=timeout)

    def process_text(self, text: str) -> Intent | None:
        """Parse and execute a single utterance. No state machine.
        Raises RuntimeError if loop is running."""
        if self._started:
            raise RuntimeError(
                "Cannot use manual mode while the loop is running. "
                "Call stop() first."
            )
        return self._loop.handle_utterance(text)

    def parse(
        self,
        text: str,
        *,
        dialog_mode: bool = False,
        youtube_mode: bool | None = None,
    ) -> Intent | None:
        """Parse text to Intent without executing."""
        return self._parser.parse(
            text, dialog_mode=dialog_mode, youtube_mode=youtube_mode
        )

    def execute(self, intent: Intent) -> bool | str | None:
        """Execute an Intent directly."""
        return self._executor.execute(intent)

    def speak(self, text: str) -> None:
        """Speak text via TTS."""
        _tts.speak_async(text)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def listener(self) -> HybridListener:
        return self._listener

    @property
    def parser(self) -> IntentParser:
        return self._parser

    @property
    def executor(self) -> Executor:
        return self._executor

    @property
    def browser(self):
        return self._executor.browser_session

    @property
    def config(self) -> dict:
        return self._parser.config

    @property
    def running(self) -> bool:
        return self._started and self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Internal callback helpers
    # ------------------------------------------------------------------

    def _emit_status(self, status: str, detail: str | None = None) -> None:
        cb = self._callbacks.on_status
        if cb:
            try:
                cb(status, detail)
            except Exception:
                pass





