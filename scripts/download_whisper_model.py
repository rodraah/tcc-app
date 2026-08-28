"""Baixa/cacheia o modelo faster-whisper (HuggingFace)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Cache do modelo faster-whisper")
    parser.add_argument(
        "--model",
        default="base",
        help="Tamanho: tiny, base, small, medium, ... (padrão: base)",
    )
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--compute-type", default="int8")
    args = parser.parse_args()

    print(f"Baixando/carregando faster-whisper '{args.model}' ({args.device})...")
    from faster_whisper import WhisperModel

    WhisperModel(args.model, device=args.device, compute_type=args.compute_type)
    print("OK — modelo em cache (HuggingFace). Use: python main.py --engine whisper")


if __name__ == "__main__":
    main()
