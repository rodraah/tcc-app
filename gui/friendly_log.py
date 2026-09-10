"""Humanize technical log lines for the Log page (short Portuguese)."""

from __future__ import annotations

import re

_MODULE_ALIASES = {
    "system": "sistema",
    "gesture": "gesto",
    "voice": "voz",
    "gesto": "gesto",
    "voz": "voz",
    "sistema": "sistema",
}

# (substring match, friendly message) — first match wins
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"não foi possível acessar a webcam|nao foi possivel acessar a webcam", re.I),
     "Câmera não encontrada. Verifique se está conectada e livre."),
    (re.compile(r"depend[eê]ncias de gestos indispon", re.I),
     "Reconhecimento de gestos indisponível (bibliotecas ausentes)."),
    (re.compile(r"m[oó]dulo de voz indispon", re.I),
     "Reconhecimento de voz indisponível (bibliotecas ausentes)."),
    (re.compile(r"falha ao iniciar voz|voz ainda desligando", re.I),
     "Não foi possível iniciar a voz. Aguarde e tente de novo."),
    (re.compile(r"microfone.*(inv[aá]lido|indispon|n[aã]o)", re.I),
     "Microfone não encontrado. Escolha outro em Configuração."),
    (re.compile(r"nenhum microfone", re.I),
     "Nenhum microfone disponível."),
    (re.compile(r"modelo (de gestos )?n[aã]o (foi )?encontrado|modelo nao encontrado", re.I),
     "Modelo de gestos não encontrado. Rode o download de modelos."),
    (re.compile(r"erro ao carregar modelo", re.I),
     "Falha ao carregar o modelo de gestos."),
    (re.compile(r"sem internet|google falhou", re.I),
     "Sem internet — usando reconhecimento offline."),
    (re.compile(r"whisper indispon", re.I),
     "Whisper indisponível — tentando Vosk."),
    (re.compile(r"usando vosk", re.I),
     "Usando Vosk (offline)."),
    (re.compile(r"n[aã]o entendi", re.I),
     "Não entendi a fala. Tente de novo."),
    (re.compile(r"erro stt|fallback offline falhou|fallback .+ falhou", re.I),
     "Falha no reconhecimento de fala."),
    (re.compile(r"erro na thread de gestos", re.I),
     "Erro no reconhecimento de gestos. Tente Parar e Iniciar."),
    (re.compile(r"erro de voz", re.I),
     "Erro no reconhecimento de voz."),
    (re.compile(r"reconhecimento de gestos iniciado", re.I),
     "Reconhecimento de gestos iniciado."),
    (re.compile(r"a[cç][aã]o disparada:\s*(.+)", re.I),
     r"Ação: \1"),
    (re.compile(r"voz:\s*'(.+)'\s*(?:->|→)\s*(.+)", re.I),
     r"Voz: '\1' -> \2"),
]


def normalize_module(module: str) -> str:
    """Map internal module tags to short Portuguese labels."""
    return _MODULE_ALIASES.get((module or "sistema").strip().lower(), module or "sistema")


_VOICE_STATUS = {
    "started": "Ouvindo",
    "stopped": "Parado",
    "shutdown": "Desligado",
    "interrupted": "Interrompido",
}


def humanize_voice_status(status: str, detail: str | None = None) -> str:
    """Map raw voice-module status codes to short Portuguese UI labels."""
    key = (status or "").strip().lower()
    if key == "engine_switched":
        return f"Motor: {detail}" if detail else "Motor alternado"
    return _VOICE_STATUS.get(key, status)


def humanize(message: str) -> str:
    """Return a short Portuguese log line; drop stack traces."""
    if not message:
        return message

    # Keep only the first line — stack traces drown the Log page.
    first = message.strip().splitlines()[0].strip()

    for pattern, friendly in _PATTERNS:
        match = pattern.search(first)
        if match:
            if "\\" in friendly:  # replacement with groups
                return pattern.sub(friendly, first)
            return friendly

    # Generic: strip trailing exception type noise like "ExcName: detail"
    # but keep a readable first sentence, capped for the UI.
    cleaned = re.sub(r"\s+", " ", first)
    if len(cleaned) > 160:
        cleaned = cleaned[:157] + "..."
    return cleaned
