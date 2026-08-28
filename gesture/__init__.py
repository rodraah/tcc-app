"""Gesture recognition module: webcam -> MediaPipe -> gesture classification -> actions."""

from gesture.gestos import classificar_gesto_mao, detectar_gesto_customizado
from gesture.acoes import DisparadorAcoes, carregar_mapeamento, listar_acoes, executar_acao
from gesture.config import config

__all__ = [
    "classificar_gesto_mao",
    "detectar_gesto_customizado",
    "DisparadorAcoes",
    "carregar_mapeamento",
    "listar_acoes",
    "executar_acao",
    "config",
]
