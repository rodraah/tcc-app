"""Voice Assistant — importable module (vendored folder)."""


def __getattr__(name: str):
    if name == "VoiceAssistant":
        from voice.assistant import VoiceAssistant

        return VoiceAssistant
    if name == "Intent":
        from voice.models import Intent

        return Intent
    if name == "Callbacks":
        from voice.models import Callbacks

        return Callbacks
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["VoiceAssistant", "Intent", "Callbacks"]
