import json
from pathlib import Path
from typing import Protocol

import numpy as np
import speech_recognition as sr
from vosk import KaldiRecognizer, Model

from voice.paths import PROJECT_ROOT, MODELS_DIR

DEFAULT_VOSK_MODEL = MODELS_DIR / "vosk-model-pt-fb-v0.1.1-pruned"
SAMPLE_RATE = 16000


class SttEngine(Protocol):
    def transcribe(self, audio: sr.AudioData) -> str: ...


def build_vosk_grammar(config: dict) -> str | None:
    """Vocabulário restrito para comandos fixos (desabilitado por padrão)."""
    stt = config.get("stt", {})
    if not stt.get("vosk_use_grammar", False):
        return None

    words: set[str] = set()
    words.add(config.get("wake_word", "assistente"))
    words.update(config.get("verbs", []))
    words.update(config.get("verb_aliases", {}).keys())
    words.update(config.get("apps", {}).keys())
    words.update(config.get("urls", {}).keys())
    words.update(config.get("type_prefixes", []))
    words.update(config.get("click_verbs", []))
    words.update(config.get("search_prefixes", []))
    words.update(config.get("hotkeys", {}).keys())
    words.update(config.get("press_keys", {}).keys())
    words.update(config.get("window_actions", {}).keys())
    words.update(config.get("help_phrases", []))
    words.update(config.get("cancel_phrases", []))
    words.update(config.get("volume", {}).keys())

    for alias in list(config.get("apps", {})) + list(config.get("hotkeys", {})):
        words.update(alias.split())

    return json.dumps(sorted(w for w in words if w), ensure_ascii=False)


class VoskEngine:
    def __init__(
        self,
        model_path: Path | str | None = None,
        grammar: str | None = None,
    ) -> None:
        path = Path(model_path) if model_path else DEFAULT_VOSK_MODEL
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if not path.exists():
            raise FileNotFoundError(
                f"Modelo Vosk não encontrado em '{path}'. "
                "Execute: python scripts/download_vosk_model.py"
            )
        self.model = Model(str(path))
        self.grammar = grammar

    def transcribe(self, audio: sr.AudioData) -> str:
        raw = audio.get_raw_data(convert_rate=SAMPLE_RATE, convert_width=2)
        if self.grammar:
            recognizer = KaldiRecognizer(self.model, SAMPLE_RATE, self.grammar)
        else:
            recognizer = KaldiRecognizer(self.model, SAMPLE_RATE)
        recognizer.AcceptWaveform(raw)
        result = json.loads(recognizer.FinalResult())
        return result.get("text", "").strip()


class GoogleEngine:
    def __init__(
        self,
        recognizer: sr.Recognizer,
        language: str = "pt-BR",
        prefer_phrases: list[str] | None = None,
    ) -> None:
        self.recognizer = recognizer
        self.language = language
        # Frases multi-palavra que preferimos se o Google listar como alternativa.
        self.prefer_phrases = [p.lower().strip() for p in (prefer_phrases or []) if p]

    def transcribe(self, audio: sr.AudioData) -> str:
        raw = self.recognizer.recognize_google(
            audio, language=self.language, show_all=True
        )
        if isinstance(raw, str):
            return raw.strip()
        if not isinstance(raw, dict):
            raise sr.UnknownValueError()
        alts = [
            (a.get("transcript") or "").strip()
            for a in raw.get("alternative", [])
            if (a.get("transcript") or "").strip()
        ]
        if not alts:
            raise sr.UnknownValueError()
        return pick_preferred_transcript(alts, self.prefer_phrases)


class WhisperEngine:
    """faster-whisper com lazy-load do modelo (cold start só no 1º uso)."""

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "pt",
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        # faster-whisper usa código ISO curto (pt), não pt-BR.
        self.language = (language or "pt").split("-")[0].lower()
        self._model = None

    def _ensure_model(self):
        if self._model is not None:
            return self._model
        from faster_whisper import WhisperModel

        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
        )
        return self._model

    def transcribe(self, audio: sr.AudioData) -> str:
        raw = audio.get_raw_data(convert_rate=SAMPLE_RATE, convert_width=2)
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if samples.size == 0:
            raise sr.UnknownValueError()
        model = self._ensure_model()
        segments, _info = model.transcribe(
            samples,
            language=self.language,
            vad_filter=True,
            beam_size=1,
        )
        text = " ".join(seg.text.strip() for seg in segments if seg.text).strip()
        if not text:
            raise sr.UnknownValueError()
        return text


def pick_preferred_transcript(
    alternatives: list[str], prefer_phrases: list[str]
) -> str:
    """Entre hipóteses do Google, prefere a que casa com frase conhecida completa."""
    if not alternatives:
        return ""
    if not prefer_phrases:
        return alternatives[0]
    lowered_prefs = [p.lower() for p in prefer_phrases]
    # 1) match exato com frase preferida
    for alt in alternatives:
        if alt.lower().strip() in lowered_prefs:
            return alt
    # 2) alternativa que contém uma preferida (mais longa = melhor)
    best = None
    best_len = -1
    for alt in alternatives:
        low = alt.lower()
        for pref in lowered_prefs:
            if pref in low and len(pref) > best_len:
                best = alt
                best_len = len(pref)
    if best:
        return best
    return alternatives[0]


def prefer_phrases_from_config(config: dict) -> list[str]:
    phrases: list[str] = []
    for key in ("hotkeys", "press_keys", "window_actions", "switch_window", "volume"):
        section = config.get(key, {})
        if isinstance(section, dict):
            phrases.extend(str(k) for k in section if " " in str(k))
    for key in (
        "help_phrases",
        "repeat_phrases",
        "cancel_phrases",
        "show_desktop_phrases",
        "lock_phrases",
        "refresh_phrases",
        "new_tab_phrases",
        "close_tab_phrases",
    ):
        phrases.extend(str(p) for p in config.get(key, []) if " " in str(p))
    return phrases


def create_engine(
    name: str,
    stt_config: dict,
    recognizer: sr.Recognizer,
    full_config: dict | None = None,
) -> SttEngine:
    if name == "vosk":
        grammar = build_vosk_grammar(full_config or {})
        return VoskEngine(stt_config.get("vosk_model_path"), grammar=grammar)
    if name == "google":
        prefer = prefer_phrases_from_config(full_config or {})
        return GoogleEngine(
            recognizer,
            stt_config.get("language", "pt-BR"),
            prefer_phrases=prefer,
        )
    if name == "whisper":
        lang = stt_config.get("whisper_language") or stt_config.get("language", "pt")
        return WhisperEngine(
            model_size=str(stt_config.get("whisper_model", "base")),
            device=str(stt_config.get("whisper_device", "cpu")),
            compute_type=str(stt_config.get("whisper_compute_type", "int8")),
            language=str(lang),
        )
    raise ValueError(
        f"Engine STT desconhecido: '{name}'. Use 'vosk', 'google' ou 'whisper'."
    )
