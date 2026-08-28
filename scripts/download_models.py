"""
Baixa os modelos .task do MediaPipe (GestureRecognizer e HandLandmarker)
para a pasta models/ do repositorio.

Uso:
    python scripts/download_models.py

Comportamento:
    - Idempotente: se o arquivo ja existir com tamanho valido, e pulado.
    - Se existir mas com tamanho suspeito (corrompido), e baixado de novo.
    - Download atomico: baixa para um arquivo temporario, valida e so entao
      move para o destino final.
    - Em caso de erro, imprime mensagem clara em PT-BR e sai com codigo != 0.

Dependencias: apenas a biblioteca padrao (urllib, os, sys, pathlib).
"""

import os
import sys
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuracao
# ---------------------------------------------------------------------------

# Raiz do repositorio = pasta pai de scripts/
REPO_ROOT = Path(__file__).resolve().parent.parent

# Pasta onde os modelos serao salvos
MODELS_DIR = REPO_ROOT / "models"

# Tamanho minimo aceitavel (em bytes) para um modelo .task valido.
# Arquivos menores que isso quase certamente sao uma pagina de erro HTML
# devolvida pelo servidor em vez do modelo real.
TAMANHO_MINIMO_BYTES = 1_048_576  # ~1 MB

# Modelos a baixar: nome do arquivo -> URL no MediaPipe Storage API.
MODELOS = {
    "gesture_recognizer.task": (
        "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/"
        "gesture_recognizer/float16/1/gesture_recognizer.task"
    ),
    "hand_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
        "hand_landmarker/float16/1/hand_landmarker.task"
    ),
}


# ---------------------------------------------------------------------------
# Funcoes auxiliares
# ---------------------------------------------------------------------------

def tamanho_valido(caminho: Path) -> bool:
    """True se o arquivo existe e tem tamanho >= TAMANHO_MINIMO_BYTES."""
    if not caminho.is_file():
        return False
    return caminho.stat().st_size >= TAMANHO_MINIMO_BYTES


def baixar_modelo(nome: str, url: str) -> str:
    """
    Garante que o modelo `nome` exista na pasta models/.

    Retorna "baixado" ou "pulado" conforme o que foi feito.
    """
    # Garante que a pasta models/ exista
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    destino = MODELS_DIR / nome

    # Ja existe e com tamanho valido -> pula (idempotencia).
    if tamanho_valido(destino):
        print(f"[OK] {nome} ja existe ({destino.stat().st_size} bytes) — pulando.")
        return "pulado"

    # Existe mas com tamanho suspeito -> trata como corrompido e re-baixa.
    if destino.is_file():
        print(
            f"[AVISO] {nome} existe mas tem tamanho suspeito "
            f"({destino.stat().st_size} bytes < {TAMANHO_MINIMO_BYTES}). "
            "Re-baixando..."
        )

    # Download atomico: baixa para um arquivo temporario na mesma pasta,
    # valida e so entao move para o nome final.
    temporario = MODELS_DIR / f"{nome}.part"
    try:
        print(f"[...] Baixando {nome} ...")
        urllib.request.urlretrieve(url, temporario)
    except Exception as exc:  # noqa: BLE001 - queremos reportar qualquer falha
        raise RuntimeError(
            f"Falha ao baixar '{nome}' de:\n  {url}\nMotivo: {exc}"
        ) from exc

    # Valida o tamanho do arquivo baixado.
    tamanho = temporario.stat().st_size
    if tamanho < TAMANHO_MINIMO_BYTES:
        temporario.unlink(missing_ok=True)
        raise RuntimeError(
            f"Arquivo baixado '{nome}' tem tamanho suspeito ({tamanho} bytes), "
            f"abaixo do minimo de {TAMANHO_MINIMO_BYTES} bytes. "
            "Provavelmente o servidor devolveu uma pagina de erro em vez do modelo.\n"
            f"  URL: {url}"
        )

    # Move para o destino final (substitui o arquivo corrompido, se houver).
    os.replace(temporario, destino)
    print(f"[OK] {nome} baixado ({tamanho} bytes).")
    return "baixado"


# ---------------------------------------------------------------------------
# Execucao principal
# ---------------------------------------------------------------------------

def main() -> int:
    baixados = []
    pulados = []

    for nome, url in MODELOS.items():
        try:
            resultado = baixar_modelo(nome, url)
        except RuntimeError as exc:
            print(f"\n[ERRO] {exc}", file=sys.stderr)
            print(
                "\nVerifique sua conexao com a internet e tente novamente.",
                file=sys.stderr,
            )
            return 1
        (baixados if resultado == "baixado" else pulados).append(nome)

    # Resumo final.
    print("\n--- Resumo ---")
    if baixados:
        print("Baixados: " + ", ".join(baixados))
    else:
        print("Baixados: nenhum")
    if pulados:
        print("Pulados (ja existiam): " + ", ".join(pulados))
    else:
        print("Pulados: nenhum")

    if baixados:
        print("\nModelos prontos na pasta models/. "
              "Agora voce pode executar gestos.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
