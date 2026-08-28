from voice.actions.keyboard import type_text
from voice.models import Intent


def type_text_handler(intent: Intent) -> None:
    text = intent.params.get("text")
    if not text:
        raise ValueError("Parâmetro 'text' ausente.")
    type_text(text)
