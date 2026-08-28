"""Testes do TTS async (subprocess mockado)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.tts import speak_async, _speak_sapi


def test_speak_async_noop_when_disabled():
    with patch("voice.tts.threading.Thread") as thread:
        speak_async("ola", enabled=False)
        thread.assert_not_called()


def test_speak_async_starts_thread():
    with patch("voice.tts.threading.Thread") as thread:
        speak_async("ola", enabled=True)
        thread.assert_called_once()
        kwargs = thread.call_args.kwargs
        assert kwargs["daemon"] is True
        thread.return_value.start.assert_called_once()


def test_speak_sapi_escapes_quotes():
    with patch("voice.tts.subprocess.run") as run:
        _speak_sapi("it's ok")
        cmd = run.call_args[0][0]
        assert "it''s ok" in cmd[-1]


def test_shutdown_sets_flag_and_joins():
    """After tts.shutdown(), new speak_async calls are no-ops."""
    import voice.tts as tts_mod
    tts_mod._shutdown = False
    tts_mod._active.clear()
    with patch("voice.tts.threading.Thread") as MockThread:
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = False
        MockThread.return_value = mock_thread
        tts_mod.speak_async("hello")
        assert len(tts_mod._active) == 1
        tts_mod.shutdown(timeout=1.0)
        assert tts_mod._shutdown is True
        tts_mod.speak_async("world")
        assert len(tts_mod._active) == 1  # no new thread
        tts_mod._shutdown = False  # reset for other tests


if __name__ == "__main__":
    test_speak_async_noop_when_disabled()
    test_speak_async_starts_thread()
    test_speak_sapi_escapes_quotes()
    test_shutdown_sets_flag_and_joins()
    print("Todos os testes passaram.")
