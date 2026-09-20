"""TTS: edge-tts Francisca (neural); fallback SAPI se offline."""

from __future__ import annotations

import asyncio
import ctypes
import os
import socket
import subprocess
import tempfile
import threading
import time

from voice.logger import setup_logging

_lock = threading.Lock()
_logger = setup_logging()
_active: set = set()
_shutdown: bool = False
_voice = "pt-BR-FranciscaNeural"
_skip_edge_until = 0.0
# ponytail: 30s skip after fail; upgrade: health-check the TTS endpoint.
_EDGE_SKIP_S = 30.0
_EDGE_TIMEOUT_S = 10.0


def configure(cfg: dict | None = None) -> None:
    global _voice
    if not cfg:
        return
    voice = cfg.get("voice")
    if voice:
        _voice = str(voice)


def speak_async(text: str, enabled: bool = True) -> None:
    if _shutdown:
        return
    if not enabled or not text or not str(text).strip():
        return
    t = threading.Thread(
        target=_speak,
        args=(str(text).strip(),),
        daemon=True,
        name="tts",
    )
    _active.add(t)
    t.start()


def _speak(text: str) -> None:
    try:
        with _lock:
            if not _speak_edge(text):
                _speak_sapi(text)
    finally:
        _active.discard(threading.current_thread())


def _edge_reachable() -> bool:
    try:
        socket.create_connection(("speech.platform.bing.com", 443), timeout=1.5)
        return True
    except OSError:
        return False


def _speak_edge(text: str) -> bool:
    global _skip_edge_until
    if time.monotonic() < _skip_edge_until:
        return False
    if not _edge_reachable():
        _skip_edge_until = time.monotonic() + _EDGE_SKIP_S
        return False
    path = None
    try:
        import edge_tts

        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)

        async def _synth() -> None:
            communicate = edge_tts.Communicate(text, _voice)
            await communicate.save(path)

        asyncio.run(asyncio.wait_for(_synth(), timeout=_EDGE_TIMEOUT_S))
        _play_mp3(path)
        _skip_edge_until = 0.0
        return True
    except Exception as exc:
        _logger.warning(f"edge-tts falhou, usando SAPI: {exc}")
        _skip_edge_until = time.monotonic() + _EDGE_SKIP_S
        return False
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


def _play_mp3(path: str) -> None:
    alias = "tcc_tts"
    buf = ctypes.create_unicode_buffer(256)
    abs_path = os.path.abspath(path)
    err = ctypes.windll.winmm.mciSendStringW(
        f'open "{abs_path}" type mpegvideo alias {alias}', buf, 255, 0
    )
    if err:
        raise RuntimeError(f"mci open {err}")
    try:
        err = ctypes.windll.winmm.mciSendStringW(
            f"play {alias} wait", buf, 255, 0
        )
        if err:
            raise RuntimeError(f"mci play {err}")
    finally:
        ctypes.windll.winmm.mciSendStringW(f"close {alias}", buf, 255, 0)


def _speak_sapi(text: str) -> None:
    # Escapa aspas simples para PowerShell single-quoted string.
    safe = text.replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.Speak('{safe}')"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            check=False,
            capture_output=True,
            timeout=30,
        )
    except Exception as exc:
        _logger.warning(f"TTS falhou: {exc}")


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
