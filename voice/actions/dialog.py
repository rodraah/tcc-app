from voice.models import Intent
from voice.actions.notepad import (
    force_close_notepad,
    read_notepad_content,
    save_content_to_file,
)
from voice.actions.window import click_dialog_choice, is_confirm_save_dialog_open


def dialog_choice_handler(intent: Intent, save_config: dict | None = None) -> str | None:
    """
    Processa salvar / nao salvar / cancelar.
    Retorna caminho do arquivo se salvou, None caso contrario.
    """
    choice = intent.params.get("choice")
    if not choice:
        raise ValueError("Parâmetro 'choice' ausente.")

    config = save_config or {}

    if choice == "save":
        content = read_notepad_content() or ""
        saved_path = save_content_to_file(content, config)
        force_close_notepad()
        return str(saved_path)

    if choice == "discard":
        force_close_notepad()
        return None

    if choice == "cancel":
        if is_confirm_save_dialog_open():
            click_dialog_choice("cancel")
        return None

    raise ValueError(f"Escolha de diálogo desconhecida: {choice}")
