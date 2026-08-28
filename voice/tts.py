"""TTS via SAPI (System.Speech) em thread — não bloqueia a escuta."""

from __future__ import annotations

import subprocess
import threading
import time

from voice.logger import setup_logging

_lock = threading.Lock()
_logger = setup_logging()
_active: set = set()
_shutdown: bool = False


def speak_async(text: str, enabled: bool = True) -> None:
    if _shutdown:
        return
    if not enabled or not text or not str(text).strip():
        return
    t = threading.Thread(
        target=_speak_sapi,
        args=(str(text).strip(),),
        daemon=True,
        name="tts-sapi",
    )
    _active.add(t)
    t.start()


def _speak_sapi(text: str) -> None:
    # Escapa aspas simples para PowerShell single-quoted string.
    safe = text.replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.Speak('{safe}')"
    )
    with _lock:
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                check=False,
                capture_output=True,
                timeout=30,
            )
        except Exception as exc:
            _logger.warning(f"TTS falhou: {exc}")
    _active.discard(threading.current_thread())


def shutdown(timeout: float = 5.0) -> None:
    """Shut down the TTS subsystem. Safe to call multiple times."""
    global _shutdown
    if _shutdown:
        return
    _shutdown = True
    deadline = time.monotonic() + timeout
    for t in list(_active):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        t.join(timeout=max(remaining, 0.1))
