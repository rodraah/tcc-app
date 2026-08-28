"""Core listen → parse → execute loop for the voice assistant.

The state machine lives here; ``process_text()`` in ``VoiceAssistant`` calls
``handle_utterance()`` directly (no cooldown / dialog / lock state).
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Optional

from voice.logger import log_transcript, setup_logging

if TYPE_CHECKING:
    from voice.executor import Executor
    from voice.intent_parser import IntentParser
    from voice.listener import HybridListener
    from voice.models import Callbacks, Intent


class Loop:
    """Automated listen → parse → execute loop."""

    def __init__(
        self,
        listener: HybridListener,
        parser: IntentParser,
        executor: Executor,
        *,
        callbacks: Optional[Callbacks] = None,
    ) -> None:
        self._logger = setup_logging()
        self._listener = listener
        self._parser = parser
        self._executor = executor
        self._callbacks = callbacks

        # --- State moved from main.py:79-90 --------------------------------
        config = self._parser.config
        self.cooldown: float = float(config.get("cooldown_seconds", 0.5))
        self.cooldown_exempt: set = set(config.get("cooldown_exempt", []))
        audio_config = config.get("audio", {})
        self.recalibrate_every: int = audio_config.get(
            "recalibrate_every",
            config.get("recalibrate_every", 30),
        )
        self.last_command_time: float = 0.0
        self.awaiting_dialog: bool = False
        self.awaiting_lock: bool = False
        self._last_engine: str | None = None  # engine-switch detection (W2)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run(self, stop_event: threading.Event) -> None:
        """Main loop — runs on daemon thread. Blocks until *stop_event* is set."""
        while not stop_event.is_set():
            try:
                self._iteration(stop_event)
            except KeyboardInterrupt:
                # B4 FIX: do NOT let KI kill the daemon thread silently
                self._emit_status("interrupted")
                stop_event.set()
                break
            except Exception as exc:
                self._emit_error(exc, "loop")

    # ------------------------------------------------------------------
    # Core iteration
    # ------------------------------------------------------------------

    def _iteration(self, stop_event: threading.Event) -> None:
        """Single listen → parse → execute cycle."""
        # Pass the stop event down so listen_once() can interrupt a blocked
        # recognizer.listen() promptly when the assistant is being stopped.
        text = self._listener.listen_once(stop_event=stop_event)
        if not text:
            return

        # Emit raw transcript callback
        self._emit_transcript(text)

        # Engine-switch detection (W2)
        current_engine = self._listener.engine_name
        if (
            self._last_engine is not None
            and current_engine != self._last_engine
        ):
            self._emit_status("engine_switched", current_engine)
        self._last_engine = current_engine

        self.handle_utterance(text)

    def handle_utterance(self, text: str) -> Optional[Intent]:
        """Process a single utterance through the full state machine.

        Returns the :class:`Intent` if one was executed, ``None`` otherwise.
        Used by both the automated loop and manual-mode ``process_text()``.
        """
        self._logger.info(f"Ouvido: {text}")
        t_parse0 = time.perf_counter()

        # --- Parse -------------------------------------------------------
        if self.awaiting_lock:
            intent = self._parser.parse_lock_confirm(text)
        else:
            intent = self._parser.parse(
                text,
                dialog_mode=self.awaiting_dialog,
                youtube_mode=self._executor.browser_session.on_youtube,
            )

        ms_parse = (time.perf_counter() - t_parse0) * 1000

        # --- No intent ---------------------------------------------------
        if not intent:
            log_transcript(text)
            if self.awaiting_dialog:
                self._logger.info("Diga: salvar, nao salvar ou cancelar.")
            elif self.awaiting_lock:
                self._logger.info("Diga: confirmar ou cancelar.")
            else:
                self._logger.info(
                    "Comando ignorado (sem wake word ou intent desconhecida)."
                )
            return None

        # Emit intent callback (before execute)
        self._emit_intent(intent, text)

        # --- Cooldown check -----------------------------------------------
        now = time.time()
        exempt = intent.name in self.cooldown_exempt
        if (
            not self.awaiting_dialog
            and not self.awaiting_lock
            and not exempt
            and now - self.last_command_time < self.cooldown
        ):
            self._logger.info("Cooldown ativo, comando ignorado.")
            return None

        log_transcript(text, intent.name)

        # --- Lock confirmation gate ---------------------------------------
        if intent.name == "lock_pc" and not intent.params.get("confirmed"):
            self.awaiting_lock = True
            self._executor.speak("Confirme: diga confirmar para bloquear.")
            self._logger.info("Aguardando confirmação para bloquear o PC.")
            self.last_command_time = now
            return intent

        # --- Execute ------------------------------------------------------
        t_exec0 = time.perf_counter()
        result = self._executor.execute(intent)
        ms_exec = (time.perf_counter() - t_exec0) * 1000

        # --- Timings log --------------------------------------------------
        timings = self._listener.last_timings
        self._logger.info(
            "timing "
            f"ms_listen={timings.get('ms_listen', 0):.0f} "
            f"ms_stt={timings.get('ms_stt', 0):.0f} "
            f"ms_parse={ms_parse:.0f} "
            f"ms_exec={ms_exec:.0f}"
        )

        # --- State transitions --------------------------------------------
        if intent.name == "cancel":
            self.awaiting_dialog = False
            self.awaiting_lock = False
        elif intent.name == "close_app" and result:
            self.awaiting_dialog = True
            self._logger.info(
                "Diálogo detectado. Diga: salvar, nao salvar ou cancelar."
            )
        elif intent.name == "dialog_choice":
            self.awaiting_dialog = False
            if result:
                self._logger.info(f"Arquivo salvo: {result}")
                self._executor.speak(f"Salvo em {result}")
        elif intent.name == "lock_pc" and intent.params.get("confirmed"):
            self.awaiting_lock = False
        elif intent.name == "help" and result:
            self._logger.info(result)

        self.last_command_time = now
        self._listener.recalibrate_if_needed(self.recalibrate_every)
        return intent

    # ------------------------------------------------------------------
    # Callback helpers (W10: never let a broken callback kill the loop)
    # ------------------------------------------------------------------

    def _emit_transcript(self, text: str) -> None:
        cb = self._callbacks.on_transcript if self._callbacks else None
        if cb:
            try:
                cb(text)
            except Exception:
                self._logger.exception("on_transcript callback failed")

    def _emit_intent(self, intent: Intent, text: str) -> None:
        cb = self._callbacks.on_intent if self._callbacks else None
        if cb:
            try:
                cb(intent, text)
            except Exception:
                self._logger.exception("on_intent callback failed")

    def _emit_status(self, status: str, detail: str | None = None) -> None:
        cb = self._callbacks.on_status if self._callbacks else None
        if cb:
            try:
                cb(status, detail)
            except Exception:
                self._logger.exception("on_status callback failed")

    def _emit_error(self, exc: Exception, context: str) -> None:
        cb = self._callbacks.on_error if self._callbacks else None
        if cb:
            try:
                cb(exc, context)
            except Exception:
                self._logger.exception("on_error callback failed")
