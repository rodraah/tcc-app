"""
Modulo de visualizacao: desenho de landmarks e overlays de texto no frame.

Centraliza todo o uso do drawing_utils do MediaPipe Tasks e dos cv2.putText,
deixando gestos.py focado na logica de classificacao e no loop principal.

Este modulo e puramente de apresentacao: NAO contem logica de deteccao
nem de classificacao de gestos.
"""

import cv2

from mediapipe.tasks.python import vision

# ---------------------------------------------------------------------------
# 1. Aliases do MediaPipe Tasks para desenho
# ---------------------------------------------------------------------------
mp_drawing = vision.drawing_utils
mp_drawing_styles = vision.drawing_styles
mp_hands = vision.HandLandmarksConnections


# ---------------------------------------------------------------------------
# 2. Desenho de landmarks
# ---------------------------------------------------------------------------
def draw_landmarks_on_frame(frame_bgr, hand_landmarks_list):
    """Desenha os landmarks e conexoes de todas as maos sobre o frame BGR."""
    for hand_landmarks in hand_landmarks_list:
        mp_drawing.draw_landmarks(
            frame_bgr,
            hand_landmarks,
            mp_hands.HAND_CONNECTIONS,
            mp_drawing_styles.get_default_hand_landmarks_style(),
            mp_drawing_styles.get_default_hand_connections_style(),
        )
    return frame_bgr


# ---------------------------------------------------------------------------
# 3. Overlays de texto (cv2.putText)
# ---------------------------------------------------------------------------
def desenhar_texto_gesto(frame, texto, i):
    """Texto do gesto detectado por mao (amarelo), empilhado a cada 30px."""
    cv2.putText(frame, texto, (10, 40 + i * 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)


def desenhar_feedback_acao(frame, acao):
    """Feedback verde 'Acao disparada' no rodape do frame."""
    cv2.putText(frame, f"Acao disparada: {acao}",
                (10, frame.shape[0] - 45), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (0, 255, 0), 2)


def desenhar_fps(frame, fps):
    """FPS no rodape do frame (verde)."""
    cv2.putText(frame, f"FPS: {int(fps)}", (10, frame.shape[0] - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
