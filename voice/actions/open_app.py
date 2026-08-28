import subprocess

from voice.models import Intent


def open_app_handler(intent: Intent) -> None:
    app = intent.params.get("app")
    if not app:
        raise ValueError("Parâmetro 'app' ausente.")
    subprocess.Popen(app, shell=True)
