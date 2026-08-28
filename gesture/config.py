"""
Configuracao central do projeto — fonte unica de verdade (single source of truth).

Todos os constantes ajustaveis do sistemas (modelos, confiancas, camera,
limiares de gestos, hold-to-confirm e mapeamento) ficam aqui, agrupados na
dataclass `Config`. Os demais modulos (gestos.py, acoes.py) importam a
instancia singleton `config` e usam seus campos tipados.

Uma futura GUI podera ler/alterar estes valores sem tocar na logica dos
modulos.

Este modulo e puramente config: NAO importa mediapipe, opencv nem win32gui.
"""

from dataclasses import dataclass, field
from pathlib import Path


_PROJECT_ROOT = Path(__file__).resolve().parent.parent  # TCC-App root


@dataclass
class Config:
    """Fonte unica de verdade para as constantes configuraveis do projeto."""

    # Modelo do MediaPipe (GestureRecognizer)
    MODEL_PATH: str = str(_PROJECT_ROOT / "models" / "gesture_recognizer.task")

    # Camera
    CAMERA_INDEX: int = 0
    NUM_HANDS: int = 2

    # Confiancas do reconhecedor MediaPipe
    MIN_HAND_DETECTION_CONFIDENCE: float = 0.5
    MIN_HAND_PRESENCE_CONFIDENCE: float = 0.5
    MIN_TRACKING_CONFIDENCE: float = 0.5

    # Confianca minima para aceitar um gesto "pronto" do MediaPipe.
    # Abaixo disso, o sistema cai para as regras customizadas.
    CONFIANCA_MINIMA_GESTO_PRONTO: float = 0.6

    # Limiar geometrico do gesto customizado "Pinca" (distancia polegar-indicador)
    LIMIAR_PINCA: float = 0.04

    # Hold-to-confirm (acoes.py): tempo de hold e tolerancia a gaps de deteccao
    DURACAO_HOLD_SEGUNDOS: float = 3.0
    TOLERANCIA_GAP_FRAMES: int = 3
    DURACAO_FEEDBACK_SEGUNDOS: float = 3.0 # tempo de feedback visual de acao disparada (em segundos)

    # Mapeamento gesto -> acao persistido em JSON
    CAMINHO_MAPEAMENTO: Path = _PROJECT_ROOT / "mapeamento.json"
    MAPA_PADRAO: dict[str, str] = field(
        default_factory=lambda: {
            "Closed_Fist": "minimizar",
            "Pinca": "lupa"
        }
    )


# Instancia singleton importada pelos modulos: `from gesture.config import config`
config = Config()
