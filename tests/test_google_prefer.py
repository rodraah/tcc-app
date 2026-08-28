"""Testes de preferência de alternativas do Google STT."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import speech_recognition as sr

from voice.stt_engines import (
    GoogleEngine,
    pick_preferred_transcript,
    prefer_phrases_from_config,
)


def test_pick_prefers_full_phrase_over_truncated():
    alts = ["selecionar", "selecionar tudo", "selecionar tubo"]
    assert (
        pick_preferred_transcript(alts, ["selecionar tudo", "selecione tudo"])
        == "selecionar tudo"
    )


def test_pick_falls_back_to_first():
    assert pick_preferred_transcript(["foo", "bar"], ["selecionar tudo"]) == "foo"


def test_prefer_phrases_includes_hotkeys():
    phrases = prefer_phrases_from_config(
        {"hotkeys": {"selecionar tudo": ["ctrl", "a"], "copiar": ["ctrl", "c"]}}
    )
    assert "selecionar tudo" in phrases
    assert "copiar" not in phrases  # só multi-palavra


def test_google_engine_uses_show_all_and_prefers():
    recognizer = MagicMock(spec=sr.Recognizer)
    recognizer.recognize_google.return_value = {
        "alternative": [
            {"transcript": "selecionar", "confidence": 0.9},
            {"transcript": "selecionar tudo", "confidence": 0.7},
        ]
    }
    engine = GoogleEngine(
        recognizer, prefer_phrases=["selecionar tudo", "selecione tudo"]
    )
    text = engine.transcribe(MagicMock(spec=sr.AudioData))
    assert text == "selecionar tudo"
    recognizer.recognize_google.assert_called_once()
    kwargs = recognizer.recognize_google.call_args.kwargs
    assert kwargs.get("show_all") is True


if __name__ == "__main__":
    test_pick_prefers_full_phrase_over_truncated()
    test_pick_falls_back_to_first()
    test_prefer_phrases_includes_hotkeys()
    test_google_engine_uses_show_all_and_prefers()
    print("Todos os testes passaram.")
