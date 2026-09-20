from voice.models import Intent
from voice.actions.files import (
    create_folder,
    find_named_file,
    get_recent_paths,
    list_location,
    open_last_saved,
    open_path,
    read_last_saved,
    read_text_file,
    resolve_delete_target,
    reveal_last_saved,
    search_in_location,
    send_to_recycle_bin,
    summarize_listing,
    summarize_recent,
    summarize_search,
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


def reveal_last_file_handler(intent: Intent) -> str:
    path = reveal_last_saved()
    return str(path)


def open_file_handler(intent: Intent, save_config: dict | None = None) -> str:
    name = intent.params.get("name")
    location = intent.params.get("location")
    if not name or not location:
        raise ValueError("Parâmetros 'name' e 'location' são obrigatórios.")
    path = find_named_file(str(name), str(location), save_config or {})
    open_path(path)
    return str(path)


def read_file_handler(intent: Intent, save_config: dict | None = None) -> str:
    name = intent.params.get("name")
    location = intent.params.get("location")
    if not name or not location:
        raise ValueError("Parâmetros 'name' e 'location' são obrigatórios.")
    path = find_named_file(str(name), str(location), save_config or {})
    text = read_text_file(path)
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
    kind = str(intent.params.get("kind") or "all")
    directory, names = list_location(
        str(location), save_config or {}, kind=kind
    )
    return summarize_listing(directory, names, kind=kind)


def search_files_handler(intent: Intent, save_config: dict | None = None) -> str:
    query = intent.params.get("query")
    location = intent.params.get("location")
    if not query or not location:
        raise ValueError("Parâmetros 'query' e 'location' são obrigatórios.")
    directory, names = search_in_location(
        str(query), str(location), save_config or {}
    )
    return summarize_search(directory, str(query), names)


def list_recent_files_handler(intent: Intent, save_config: dict | None = None) -> str:
    config = save_config or {}
    limit = int(config.get("recent_limit", 10))
    return summarize_recent(get_recent_paths(limit=limit))


def delete_file_handler(intent: Intent, save_config: dict | None = None) -> str:
    """Apaga (lixeira). Exige confirmed=True e path (ou name+location / último)."""
    if not intent.params.get("confirmed"):
        raise ValueError("Apagar exige confirmação.")
    path = resolve_delete_target(intent.params, save_config or {})
    send_to_recycle_bin(path)
    return str(path)
