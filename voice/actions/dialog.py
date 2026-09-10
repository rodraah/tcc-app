from voice.models import Intent
from voice.actions.files import (
    create_folder,
    list_location,
    open_last_saved,
    read_last_saved,
    summarize_listing,
)
from voice.actions.notepad import (
    force_close_notepad,
    read_notepad_content,
    save_content_to_file,
    save_notepad_to_location,
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


def save_notepad_handler(intent: Intent, save_config: dict | None = None) -> str:
    """Salva o Bloco de Notas aberto em um local conhecido (opcionalmente nomeado)."""
    location = intent.params.get("location")
    if not location:
        raise ValueError("Parâmetro 'location' ausente.")
    name = intent.params.get("name")
    path = save_notepad_to_location(
        save_config or {}, str(location), name=str(name) if name else None
    )
    return str(path)


def open_last_file_handler(intent: Intent) -> str:
    path = open_last_saved()
    return str(path)


def read_last_file_handler(intent: Intent) -> str:
    path, text = read_last_saved()
    if not text.strip():
        return f"{path.name} está vazio."
    return text


def create_folder_handler(intent: Intent, save_config: dict | None = None) -> str:
    name = intent.params.get("name")
    location = intent.params.get("location")
    if not name or not location:
        raise ValueError("Parâmetros 'name' e 'location' são obrigatórios.")
    path = create_folder(str(name), str(location), save_config or {})
    return str(path)


def list_folder_handler(intent: Intent, save_config: dict | None = None) -> str:
    location = intent.params.get("location")
    if not location:
        raise ValueError("Parâmetro 'location' ausente.")
    directory, names = list_location(str(location), save_config or {})
    return summarize_listing(directory, names)
