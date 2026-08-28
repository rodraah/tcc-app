import subprocess
import time

from voice.models import Intent
from voice.actions.window import close_window_by_titles, is_save_dialog_open

DEFAULT_CLOSE = {
    "notepad": {"process": "notepad.exe", "titles": ["bloco de notas", "notepad"]},
    "calc": {"titles": ["calculadora", "calculator"]},
    "browser": {"titles": ["chrome", "edge", "firefox", "mozilla", "google"]},
}


def close_app_handler(intent: Intent, close_config: dict | None = None) -> bool:
    """Fecha app. Retorna True se diálogo 'Salvar alterações?' apareceu."""
    app = intent.params.get("app")
    if not app:
        raise ValueError("Parâmetro 'app' ausente.")

    config = {**DEFAULT_CLOSE, **(close_config or {})}
    target = config.get(app, {})
    titles = target.get("titles", [])
    process = target.get("process")

    closed = False
    if titles and close_window_by_titles(titles):
        closed = True
    elif process:
        subprocess.run(
            ["taskkill", "/IM", process, "/F"],
            check=False,
            capture_output=True,
        )
        closed = True
    else:
        raise RuntimeError(f"Não foi possível fechar '{app}'.")

    if closed:
        # ponytail: poll curto no lugar de sleep fixo 0.5s; diálogo costuma aparecer em <200ms
        for _ in range(6):
            time.sleep(0.05)
            if is_save_dialog_open():
                return True
        return False
    return False
