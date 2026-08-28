"""
Combina gestos prontos do MediaPipe (GestureRecognizer) com
gestos customizados detectados por regras geometricas sobre os landmarks.

Estrutura do modulo:
  - dedo_esticado() / detectar_gesto_customizado(): regras geometricas puras.
  - classificar_gesto_mao(): decisao pura "pronto vs customizado" por mao.
  - main(): carrega o modelo, abre a webcam e roda o loop de captura.
  - visualizacao.py: desenho de landmarks e overlays de texto (cv2.putText).

Importar este modulo NAO abre a webcam nem carrega o modelo — tudo isso
acontece apenas dentro de main().

Pre-requisitos:
    pip install mediapipe opencv-python

Baixe o modelo e coloque na pasta models/ deste projeto:
    https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task
"""

import cv2
import mediapipe as mp
import time
import math
import sys

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from gesture.acoes import DisparadorAcoes, carregar_mapeamento
from gesture.config import config
from gesture.visualizacao import (
    desenhar_feedback_acao,
    desenhar_fps,
    desenhar_texto_gesto,
    draw_landmarks_on_frame,
)

# ---------------------------------------------------------------------------
# 1. Regras geometricas para gestos CUSTOMIZADOS (funcoes puras)
# ---------------------------------------------------------------------------
def dedo_esticado(landmarks, ponta_idx, junta_idx, wrist_idx=0):
    """
    Heuristica simples: um dedo esta esticado se a ponta dele esta
    mais longe do pulso do que a junta intermediaria esta.
    """
    ponta = landmarks[ponta_idx]
    junta = landmarks[junta_idx]
    pulso = landmarks[wrist_idx]

    dist_ponta = math.hypot(ponta.x - pulso.x, ponta.y - pulso.y)
    dist_junta = math.hypot(junta.x - pulso.x, junta.y - pulso.y)
    return dist_ponta > dist_junta


def detectar_gesto_customizado(landmarks):
    """
    Recebe os 21 landmarks de UMA mao e devolve o nome do gesto
    customizado detectado, ou None se nenhum bater.

    Indices dos landmarks (MediaPipe Hands):
      4 = ponta do polegar   | 3 = junta do polegar
      8 = ponta do indicador | 6 = junta do indicador
      12 = ponta do medio    | 10 = junta do medio
      16 = ponta do anelar   | 14 = junta do anelar
      20 = ponta do mindinho | 18 = junta do mindinho
    """
    indicador = dedo_esticado(landmarks, 8, 6)
    medio = dedo_esticado(landmarks, 12, 10)
    anelar = dedo_esticado(landmarks, 16, 14)
    minimo = dedo_esticado(landmarks, 20, 18)

    # Exemplo de gesto customizado 1: "dois dedos" (indicador + medio, resto fechado)
    if indicador and medio and not anelar and not minimo:
        return "Dois_Dedos"

    # Exemplo de gesto customizado 2: "L" (polegar + indicador esticados, resto fechado)
    polegar = dedo_esticado(landmarks, 4, 3, wrist_idx=0)
    if polegar and indicador and not medio and not anelar and not minimo:
        return "Sinal_L"

    # Exemplo de gesto customizado 3: pinca (polegar e indicador bem proximos)
    ponta_polegar = landmarks[4]
    ponta_indicador = landmarks[8]
    dist_pinca = math.hypot(ponta_polegar.x - ponta_indicador.x,
                             ponta_polegar.y - ponta_indicador.y)
    if dist_pinca < config.LIMIAR_PINCA:
        return "Pinça"

    return None


# ---------------------------------------------------------------------------
# 2. Decisao por mao: gesto PRONTO (MediaPipe) ou CUSTOMIZADO (regras)
# ---------------------------------------------------------------------------
def classificar_gesto_mao(gestures, i, hand_landmarks):
    """
    Decide, para UMA mao, se o gesto vem do MediaPipe (pronto) ou das
    regras customizadas. Funcao pura: nao toca em cv2, webcam ou dispatcher.

    Recebe as pecas do resultado do MediaPipe que precisa (lista de gestos,
    indice da mao e landmarks dela) e devolve (gesto, origem):
      - gesto: nome do gesto detectado, ou None se nenhum bater;
      - origem: "pronto", "customizado" ou "" (quando gesto e None).
    """
    gesto_final = None
    origem = ""

    if gestures and len(gestures) > i:
        categoria = gestures[i][0].category_name
        confianca = gestures[i][0].score

        if categoria != "None" and confianca >= config.CONFIANCA_MINIMA_GESTO_PRONTO:
            gesto_final = categoria
            origem = "pronto"

    # Se o MediaPipe nao reconheceu nada confiavel, tenta as regras customizadas
    if gesto_final is None:
        gesto_custom = detectar_gesto_customizado(hand_landmarks)
        if gesto_custom:
            gesto_final = gesto_custom
            origem = "customizado"

    return gesto_final, origem


# ---------------------------------------------------------------------------
# 3. Loop principal
# ---------------------------------------------------------------------------
def main():
    # 3.1 Configuracao do reconhecedor
    try:
        base_options = python.BaseOptions(model_asset_path=config.MODEL_PATH)
        options = vision.GestureRecognizerOptions(
            base_options=base_options,
            num_hands=config.NUM_HANDS,
            running_mode=vision.RunningMode.VIDEO,
            min_hand_detection_confidence=config.MIN_HAND_DETECTION_CONFIDENCE,
            min_hand_presence_confidence=config.MIN_HAND_PRESENCE_CONFIDENCE,
            min_tracking_confidence=config.MIN_TRACKING_CONFIDENCE,
        )
        recognizer = vision.GestureRecognizer.create_from_options(options)
    except FileNotFoundError:
        print(
            f"Modelo nao encontrado: {config.MODEL_PATH}. "
            "Execute 'python scripts/download_models.py' para baixar os modelos necessarios."
        )
        sys.exit(1)
    except Exception as e:
        print(
            f"Erro ao carregar o modelo {config.MODEL_PATH}: {e}. "
            "Execute 'python scripts/download_models.py' para baixar os modelos necessarios."
        )
        sys.exit(1)

    # 3.2 Disparo de acoes a partir do mapeamento gesto -> acao
    disparador = DisparadorAcoes(carregar_mapeamento())

    # 3.3 Captura da webcam
    cap = cv2.VideoCapture(config.CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError("Nao foi possivel acessar a webcam.")

    prev_time = 0

    fim_feedback = 0  # contador de frames para feedback visual de acao disparada
    feedback_acao = None  # acao que disparou o feedback visual

    while True:
        success, frame = cap.read()
        if not success:
            break

        frame = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        timestamp_ms = int(time.time() * 1000)
        result = recognizer.recognize_for_video(mp_image, timestamp_ms)

        frame = draw_landmarks_on_frame(frame, result.hand_landmarks)

        # Gesto mapeado do frame: o primeiro gesto mapeado entre as maos vence
        gesto_mapeado = None

        # Para cada mao detectada, decide se usa o gesto PRONTO ou o CUSTOMIZADO
        for i, hand_landmarks in enumerate(result.hand_landmarks):
            gesto_final, origem = classificar_gesto_mao(
                result.gestures, i, hand_landmarks
            )

            if gesto_mapeado is None and gesto_final in disparador.mapa:
                gesto_mapeado = gesto_final

            texto = f"{gesto_final} ({origem}) -> {disparador.mapa.get(gesto_final)}" if gesto_final else "Nenhum gesto"
            desenhar_texto_gesto(frame, texto, i)

        # Alimenta o disparador 1x por frame com o gesto mapeado (ou None)
        acao_executada = disparador.alimentar(gesto_mapeado)
        if acao_executada:
            fim_feedback = time.time() + config.DURACAO_FEEDBACK_SEGUNDOS  # reinicia o contador de feedback
            feedback_acao = acao_executada  # guarda a acao que disparou o feedback

        if fim_feedback > time.time() and feedback_acao:
            desenhar_feedback_acao(frame, feedback_acao.upper())

        curr_time = time.time()
        fps = 1 / (curr_time - prev_time) if prev_time else 0
        prev_time = curr_time
        desenhar_fps(frame, fps)

        cv2.imshow("Gestos prontos + customizados - 'q' para sair", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    recognizer.close()


if __name__ == "__main__":
    main()
