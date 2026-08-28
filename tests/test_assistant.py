"""Testes do VoiceAssistant facade (sem hardware real)."""

import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.models import Callbacks, Intent


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _reset_singleton():
    """Reset the process-wide singleton guard between tests."""
    import voice.assistant as _asm
    with _asm._instance_lock:
        _asm._active_instance = None


def _build_assistant(**kwargs):
    """Create a VoiceAssistant with mocked listener and PTT.

    Uses push_to_talk=False by default to avoid pynput dependency.
    Patches HybridListener at the module level so the mic is never opened.
    """
    _reset_singleton()
    mock_listener = MagicMock()
    mock_listener.paused = False
    mock_listener.last_timings = {}
    defaults = {"engine": "google", "push_to_talk": False}
    defaults.update(kwargs)
    with patch("voice.assistant.HybridListener", return_value=mock_listener):
        from voice.assistant import VoiceAssistant
        va = VoiceAssistant(**defaults)
    return va


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

def test_construction():
    """VoiceAssistant constructs successfully; running starts False."""
    va = _build_assistant()
    assert va.running is False
    assert va._shutdown_done is False
    assert isinstance(va.config, dict)
    # Shutdown cleans up and clears singleton
    va.shutdown()
    import voice.assistant as _asm
    assert _asm._active_instance is None


def test_singleton_guard():
    """Second VoiceAssistant() raises RuntimeError when first is active."""
    va1 = _build_assistant()
    try:
        va2 = type(va1)(engine="google", push_to_talk=False)
        assert False, "Should have raised RuntimeError"
    except RuntimeError as exc:
        assert "already active" in str(exc)
    finally:
        va1.shutdown()


def test_failed_construction_releases_singleton():
    """B3: If construction fails mid-way, singleton is NOT permanently poisoned."""
    _reset_singleton()
    # First: successful construction
    va1 = _build_assistant()
    va1.shutdown()

    _reset_singleton()
    # Second: force HybridListener to raise
    with patch("voice.assistant.HybridListener", side_effect=RuntimeError("mic fail")):
        from voice.assistant import VoiceAssistant
        try:
            VoiceAssistant(engine="google", push_to_talk=False)
            assert False, "Should have raised"
        except RuntimeError:
            pass

    # Singleton should be clear — a third construction succeeds
    va3 = _build_assistant()
    assert va3.running is False
    va3.shutdown()


def test_start_stop_lifecycle():
    """start() sets _started=True, stop() sets _started=False. Idempotent."""
    mock_listener = MagicMock()
    mock_listener.paused = False
    mock_listener.last_timings = {}

    _reset_singleton()
    with patch("voice.assistant.HybridListener", return_value=mock_listener):
        from voice.assistant import VoiceAssistant
        va = VoiceAssistant(engine="google", push_to_talk=False)

    # listen_once returns None so the loop iterates but doesn't block
    mock_listener.listen_once.return_value = None

    va.start()
    assert va._started is True
    # Idempotent start
    va.start()
    assert va._started is True

    va.stop()
    assert va._started is False
    # Idempotent stop
    va.stop()
    assert va._started is False

    va.shutdown()


def test_callbacks_invoked():
    """process_text triggers on_intent callback with correct args."""
    received = []
    cb = Callbacks(on_intent=lambda intent, text: received.append((intent, text)))
    va = _build_assistant(callbacks=cb)

    # Parser should match "ajuda" → help intent
    result = va.process_text("assistente ajuda")
    assert result is not None
    assert result.name == "help"
    assert len(received) == 1
    assert received[0][0].name == "help"
    assert "ajuda" in received[0][1]

    va.shutdown()


def test_manual_mode_guard():
    """listen_once / process_text raise RuntimeError when loop is running."""
    mock_listener = MagicMock()
    mock_listener.paused = False
    mock_listener.last_timings = {}

    _reset_singleton()
    with patch("voice.assistant.HybridListener", return_value=mock_listener):
        from voice.assistant import VoiceAssistant
        va = VoiceAssistant(engine="google", push_to_talk=False)

    mock_listener.listen_once.return_value = None
    va.start()

    try:
        va.listen_once()
        assert False, "Should have raised RuntimeError"
    except RuntimeError as exc:
        assert "manual mode" in str(exc).lower() or "loop is running" in str(exc).lower()

    try:
        va.process_text("test")
        assert False, "Should have raised RuntimeError"
    except RuntimeError as exc:
        assert "manual mode" in str(exc).lower() or "loop is running" in str(exc).lower()

    va.stop()
    va.shutdown()


def test_shutdown_idempotency():
    """Multiple shutdown() calls are safe, no exceptions."""
    va = _build_assistant()
    va.shutdown()
    va.shutdown()  # second call — should be no-op
    va.shutdown()  # third call — still safe


def test_keyboard_interrupt_graceful_stop():
    """B4: KeyboardInterrupt in loop is caught; wait() returns True."""
    mock_listener = MagicMock()
    mock_listener.paused = False
    mock_listener.last_timings = {}

    _reset_singleton()
    with patch("voice.assistant.HybridListener", return_value=mock_listener):
        from voice.assistant import VoiceAssistant
        va = VoiceAssistant(engine="google", push_to_talk=False)

    # listen_once returns text, then the executor raises KeyboardInterrupt
    call_count = [0]
    def fake_listen(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return "abrir notepad"
        return None

    mock_listener.listen_once.side_effect = fake_listen
    va._executor.execute = MagicMock(side_effect=KeyboardInterrupt)

    va.start()
    result = va.wait(timeout=5)
    assert result is True, "wait() should return True after KI graceful stop"

    va.shutdown()


def test_process_text_direct():
    """W9: process_text does direct parse+execute via handle_utterance."""
    va = _build_assistant()
    # Patch parser.parse and executor.execute to track calls
    parse_result = Intent("help")
    with patch.object(va._parser, "parse", return_value=parse_result) as mock_parse, \
         patch.object(va._executor, "execute", return_value="ok") as mock_exec:
        result = va.process_text("assistente ajuda")
        mock_parse.assert_called_once()
        mock_exec.assert_called_once()
        assert result is parse_result

    va.shutdown()


def test_wait_never_started():
    """wait() returns True immediately when never started."""
    va = _build_assistant()
    result = va.wait(timeout=0)
    assert result is True
    va.shutdown()


# ------------------------------------------------------------------
# Runner
# ------------------------------------------------------------------

if __name__ == "__main__":
    test_construction()
    print("  test_construction OK")
    test_singleton_guard()
    print("  test_singleton_guard OK")
    test_failed_construction_releases_singleton()
    print("  test_failed_construction_releases_singleton OK")
    test_start_stop_lifecycle()
    print("  test_start_stop_lifecycle OK")
    test_callbacks_invoked()
    print("  test_callbacks_invoked OK")
    test_manual_mode_guard()
    print("  test_manual_mode_guard OK")
    test_shutdown_idempotency()
    print("  test_shutdown_idempotency OK")
    test_keyboard_interrupt_graceful_stop()
    print("  test_keyboard_interrupt_graceful_stop OK")
    test_process_text_direct()
    print("  test_process_text_direct OK")
    test_wait_never_started()
    print("  test_wait_never_started OK")
    print("Todos os testes passaram.")
