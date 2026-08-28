"""Baixa o modelo Vosk PT-BR para uso offline.

No Windows, o modelo full (1.6G) falha ao carregar (ConstArpaLm).
A versão pruned é o modelo grande compatível.
"""

import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

# ponytail: Windows não carrega o full 1.6G; pruned é o upgrade estável.
# Full: vosk-model-pt-fb-v0.1.1-20220516_2113 (só Linux/macOS confiável).
MODEL_NAME = "vosk-model-pt-fb-v0.1.1-pruned"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"
MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / MODEL_NAME


def main() -> None:
    MODEL_DIR.parent.mkdir(parents=True, exist_ok=True)

    if MODEL_DIR.exists():
        print(f"Modelo já existe em: {MODEL_DIR}")
        return

    zip_path = MODEL_DIR.parent / f"{MODEL_NAME}.zip"
    print(f"Baixando modelo de {MODEL_URL} ...")
    urlretrieve(MODEL_URL, zip_path)

    print("Extraindo...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(MODEL_DIR.parent)

    zip_path.unlink(missing_ok=True)
    print(f"Modelo instalado em: {MODEL_DIR}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        sys.exit(1)
