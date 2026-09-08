"""Background thread wrappers for gesture and voice recognition.

Each thread communicates with the GUI via queues:
- Background threads put data into queues (never touch Tkinter widgets).
- The main thread polls queues via ``after()`` and updates widgets.

Thread-safety rules:
  1. NEVER update Tkinter widgets from a background thread.
  2. Use ``queue.Queue(maxsize=N)`` as the bridge.
  3. All queue puts use ``put_nowait()`` — never block the loop.
  4. Use daemon threads so they die on app exit.
"""

from __future__ import annotations

import queue
import threading
import time
import traceback


class GestureThread:
    """Background thread: webcam → MediaPipe → gesture classification → actions.

    Communicates with the GUI via queues:

    - ``frame_queue``     — BGR numpy frames for display (maxsize=1)
    - ``gesture_queue``   — ``(name, confidence, origin, action)`` tuples (maxsize=1)
    - ``log_queue``       — ``(message, module)`` tuples (maxsize=50)
    - ``action_queue``    — action name strings that fired (maxsize=5)
    """

    def __init__(self, camera_index: int = 0) -> None:
        self._camera_index = camera_index
        self._running = False
        self._thread: threading.Thread | None = None

        # Queues for GUI communication (main thread reads via after() polling)
        self.frame_queue: queue.Queue = queue.Queue(maxsize=1)
        self.gesture_queue: queue.Queue = queue.Queue(maxsize=1)
        self.log_queue: queue.Queue = queue.Queue(maxsize=50)
        self.action_queue: queue.Queue = queue.Queue(maxsize=5)
        self.error_queue: queue.Queue = queue.Queue(maxsize=1)  # Critical errors for UI dialogs

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the gesture loop in a daemon thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop,
            name="gesture-thread",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the loop to stop and wait for the thread to finish."""
        self._running = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5.0)

    @property
    def is_running(self) -> bool:
        """True while the background thread is alive."""
        return self._running and self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _put_log(self, message: str, module: str = "system") -> None:
        """Non-blocking log put — drops the message if the queue is full."""
        try:
            self.log_queue.put_nowait((message, module))
        except queue.Full:
            pass

    def _put_error(self, title: str, message: str) -> None:
        """Non-blocking error put for critical errors that need UI dialog."""
        try:
            self.error_queue.put_nowait((title, message))
        except queue.Full:
            pass

    # ------------------------------------------------------------------
    # Main loop (runs on background thread)
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        """Core gesture recognition loop.

        Loads MediaPipe GestureRecognizer, opens the webcam, and processes
        each frame: recognition → classification → action dispatch → queues.
        """
        recognizer = None
        cap = None

        try:
            # Late imports so the class can be instantiated even if mediapipe
            # or gesture deps are not installed (the loop will just not start).
            import cv2
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision

            from gesture.acoes import DisparadorAcoes, carregar_mapeamento
            from gesture.config import config
            from gesture.gestos import classificar_gesto_mao
            from gesture.visualizacao import (
                draw_landmarks_on_frame,
                desenhar_feedback_acao,
                desenhar_fps,
                desenhar_texto_gesto,
            )
        except ImportError as exc:
            self._put_log(f"Dependencias de gestos indisponiveis: {exc}")
            self._running = False
            return

        try:
            # --- Load MediaPipe GestureRecognizer ---
            try:
                base_options = mp_python.BaseOptions(
                    model_asset_path=config.MODEL_PATH,
                )
                options = vision.GestureRecognizerOptions(
                    base_options=base_options,
                    num_hands=config.NUM_HANDS,
                    running_mode=vision.RunningMode.VIDEO,
                    min_hand_detection_confidence=(
                        config.MIN_HAND_DETECTION_CONFIDENCE
                    ),
                    min_hand_presence_confidence=(
                        config.MIN_HAND_PRESENCE_CONFIDENCE
                    ),
                    min_tracking_confidence=config.MIN_TRACKING_CONFIDENCE,
                )
                recognizer = vision.GestureRecognizer.create_from_options(
                    options,
                )
            except FileNotFoundError:
                self._put_error(
                    "Modelo nao encontrado",
                    f"O modelo de gestos nao foi encontrado em:\n{config.MODEL_PATH}\n\n"
                    "Execute 'python scripts/download_models.py' para baixar os modelos necessarios.",
                )
                self._running = False
                return
            except Exception as exc:
                self._put_error(
                    "Erro ao carregar modelo",
                    f"Erro ao carregar o modelo de gestos:\n{exc}\n\n"
                    "Execute 'python scripts/download_models.py' para baixar os modelos necessarios.",
                )
                self._running = False
                return

            # --- Action dispatcher (holds hold-to-confirm state) ---
            disparador = DisparadorAcoes(carregar_mapeamento())

            # --- Open webcam ---
            cap = cv2.VideoCapture(self._camera_index)
            if not cap.isOpened():
                self._put_log("Nao foi possivel acessar a webcam.")
                recognizer.close()
                self._running = False
                return

            self._put_log("Reconhecimento de gestos iniciado.")

            prev_time = 0.0
            fim_feedback = 0.0
            feedback_acao: str | None = None

            while self._running:
                success, frame = cap.read()
                if not success:
                    continue

                # Mirror for natural interaction
                frame = cv2.flip(frame, 1)

                # MediaPipe expects RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB, data=rgb_frame,
                )

                timestamp_ms = int(time.time() * 1000)
                result = recognizer.recognize_for_video(mp_image, timestamp_ms)

                # Draw landmarks on the BGR frame
                frame = draw_landmarks_on_frame(frame, result.hand_landmarks)

                # --- Classify gestures per hand ---
                gesto_mapeado: str | None = None
                gesto_confianca: float = 0.0
                gesto_origem: str = ""

                for i, hand_landmarks in enumerate(result.hand_landmarks):
                    gesto_final, origem = classificar_gesto_mao(
                        result.gestures, i, hand_landmarks,
                    )

                    # Track the first mapped gesture (earliest hand wins)
                    if gesto_mapeado is None and gesto_final in disparador.mapa:
                        gesto_mapeado = gesto_final
                        gesto_origem = origem
                        if (
                            origem == "pronto"
                            and result.gestures
                            and len(result.gestures) > i
                        ):
                            gesto_confianca = result.gestures[i][0].score

                    texto = (
                        f"{gesto_final} ({origem}) -> "
                        f"{disparador.mapa.get(gesto_final)}"
                        if gesto_final
                        else "Nenhum gesto"
                    )
                    desenhar_texto_gesto(frame, texto, i)

                # --- Dispatch action ---
                acao_executada = disparador.alimentar(gesto_mapeado)
                if acao_executada:
                    fim_feedback = (
                        time.time() + config.DURACAO_FEEDBACK_SEGUNDOS
                    )
                    feedback_acao = acao_executada
                    try:
                        self.action_queue.put_nowait(acao_executada)
                    except queue.Full:
                        pass
                    self._put_log(
                        f"Ação disparada: {acao_executada}", "gesture",
                    )

                if fim_feedback > time.time() and feedback_acao:
                    desenhar_feedback_acao(frame, feedback_acao.upper())

                # FPS overlay
                curr_time = time.time()
                fps = 1 / (curr_time - prev_time) if prev_time else 0
                prev_time = curr_time
                desenhar_fps(frame, fps)

                # --- Put data into queues (non-blocking, drop old) ---
                try:
                    self.frame_queue.put_nowait(frame)
                except queue.Full:
                    pass

                # Mapped action that WILL fire if the gesture is held
                acao_mapeada = (
                    disparador.mapa.get(gesto_mapeado) if gesto_mapeado else ""
                )

                try:
                    self.gesture_queue.put_nowait(
                        (
                            gesto_mapeado or "",
                            gesto_confianca,
                            gesto_origem,
                            acao_mapeada or "",
                        ),
                    )
                except queue.Full:
                    pass

        except Exception as exc:
            tb = traceback.format_exc()
            self._put_log(f"Erro na thread de gestos: {exc}\n{tb}")
        finally:
            if cap is not None:
                cap.release()
            if recognizer is not None:
                recognizer.close()


class VoiceThread:
    """Background thread: mic → STT → intent → action.

    Wraps ``VoiceAssistant`` from the voice module.  If the voice module
    dependencies (pyaudio, etc.) are not installed, the thread becomes a
    no-op and reports the failure via ``log_queue`` and ``error_queue`` so
    the GUI can show a dialog.

    Communicates via:

    - ``status_queue``     — ``(status, detail)`` tuples (maxsize=1)
    - ``transcript_queue`` — raw recognized speech strings (maxsize=1)
    - ``log_queue``        — ``(message, module)`` tuples (maxsize=50)
    - ``error_queue``      — ``(title, message)`` critical errors (maxsize=1)
    """

    def __init__(
        self,
        engine: str | None = None,
        config_path: str | None = None,
        mic_device_id: int | None = None,
        pause_threshold: float | None = None,
    ) -> None:
        self._engine = engine
        self._config_path = config_path
        self._mic_device_id = mic_device_id
        self._pause_threshold = pause_threshold
        self._assistant = None
        self._started = False
        self._error_reported = False  # once-per-session guard for error dialogs

        self.status_queue: queue.Queue = queue.Queue(maxsize=1)
        self.transcript_queue: queue.Queue = queue.Queue(maxsize=1)
        self.log_queue: queue.Queue = queue.Queue(maxsize=50)
        self.error_queue: queue.Queue = queue.Queue(maxsize=1)  # Critical errors for UI dialogs

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------

    def _put_error(self, title: str, message: str) -> None:
        """Non-blocking error put for critical errors that need UI dialog."""
        try:
            self.error_queue.put_nowait((title, message))
        except queue.Full:
            pass

    def _put_log(self, message: str, module: str = "system") -> None:
        """Non-blocking log put — drops the message if the queue is full."""
        try:
            self.log_queue.put_nowait((message, module))
        except queue.Full:
            pass

    def start(self) -> None:
        """Start the voice assistant in a daemon thread.

        Importing the voice module is deferred so that missing optional
        dependencies (pyaudio, etc.) do not crash the application.  Failures
        are reported to both ``log_queue`` and ``error_queue`` so the GUI can
        show a dialog.
        """
        if self._started:
            return

        self._error_reported = False

        # Late import — voice deps may not be installed
        try:
            from voice.assistant import VoiceAssistant
            from voice.models import Callbacks
        except ImportError as exc:
            self._put_log(f"Modulo de voz indisponivel: {exc}", "system")
            self._put_error(
                "Voz indisponível",
                "O módulo de reconhecimento de voz não pôde ser carregado.\n\n"
                f"Detalhes: {exc}\n\n"
                "Verifique se as dependências de voz estão instaladas "
                "(pip install -r requirements.txt).",
            )
            return

        # --- Callbacks: bridge voice loop → GUI queues ---

        def _on_status(status: str, detail: str | None) -> None:
            try:
                self.status_queue.put_nowait((status, detail))
            except queue.Full:
                pass

        def _on_intent(intent, raw_text: str) -> None:
            try:
                self.log_queue.put_nowait(
                    (f"Voz: '{raw_text}' -> {intent.name}", "voice"),
                )
            except queue.Full:
                pass
            # Surface the raw recognized speech for the camera page display
            try:
                self.transcript_queue.put_nowait(raw_text)
            except queue.Full:
                pass

        def _on_error(exc: Exception, context: str) -> None:
            try:
                self.log_queue.put_nowait(
                    (f"Erro de voz ({context}): {exc}", "system"),
                )
            except queue.Full:
                pass
            # Surface critical STT failures (e.g. offline fallback without
            # models) to the UI — once per session to avoid dialog spam.
            if context in ("stt", "stt_fallback") and not self._error_reported:
                self._error_reported = True
                self._put_error(
                    "Voz indisponível",
                    "O reconhecimento de voz falhou ao processar o áudio.\n\n"
                    f"Detalhes: {exc}\n\n"
                    "Verifique a conexão com a internet (Google) ou baixe os "
                    "modelos offline (Whisper/Vosk) para reconhecimento sem "
                    "internet.",
                )

        callbacks = Callbacks(
            on_status=_on_status,
            on_intent=_on_intent,
            on_error=_on_error,
        )

        try:
            self._assistant = VoiceAssistant(
                engine=self._engine,
                config_path=self._config_path,
                callbacks=callbacks,
                push_to_talk=False,
                mic_device_id=self._mic_device_id,
                pause_threshold=self._pause_threshold,
            )
            self._assistant.start()
            self._started = True
        except RuntimeError as exc:
            # The previous assistant may still be shutting down in the
            # background (process-wide singleton guard still held).
            self._put_log(f"Falha ao iniciar voz: {exc}", "system")
            self._put_error(
                "Voz ainda desligando",
                "O reconhecimento de voz ainda está sendo desligado.\n\n"
                "Aguarde um instante e clique em Iniciar novamente.",
            )
        except Exception as exc:
            self._put_log(f"Falha ao iniciar voz: {exc}", "system")
            self._put_error(
                "Falha ao iniciar voz",
                f"Não foi possível iniciar o reconhecimento de voz:\n{exc}\n\n"
                "Verifique se o microfone está conectado e configurado no "
                "assistente de configuração.",
            )

    def stop(self) -> None:
        """Shut down the voice assistant.  Idempotent.

        Note: this blocks until the assistant loop exits (bounded by the
        assistant's internal join timeout).  Callers should invoke it from a
        background thread so the UI never freezes.
        """
        if self._assistant is not None and self._started:
            try:
                self._assistant.shutdown()
            except Exception:
                pass
            self._started = False

    @property
    def is_running(self) -> bool:
        """True while the voice assistant is active."""
        if self._assistant is None or not self._started:
            return False
        return getattr(self._assistant, "running", False)
