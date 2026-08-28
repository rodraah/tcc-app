import speech_recognition as sr
import threading
import time

from voice.logger import setup_logging
from voice.stt_engines import SttEngine, create_engine


def _valid_input_device_ids() -> set[int]:
    """Return the set of device indices that can be used as a microphone.

    Uses ``sounddevice`` (the same library the setup wizard uses to probe
    mics) so the persisted ``mic_device_id`` from ``app_state.json`` can be
    validated before handing it to ``sr.Microphone``.  Returns an empty set
    if sounddevice is unavailable or errors.
    """
    try:
        import sounddevice as sd

        valid = set()
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                valid.add(i)
        return valid
    except Exception:
        return set()


class HybridListener:
    """Captura via SpeechRecognition; Google (padrão) → Whisper → Vosk offline."""

    def __init__(
        self,
        config: dict,
        engine_name: str | None = None,
        mic_device_id: int | None = None,
        pause_threshold: float | None = None,
        on_error=None,
    ) -> None:
        self.logger = setup_logging()
        self.config = config
        self.audio_config = config.get("audio", {})
        self.stt_config = config.get("stt", {})

        self.engine_name = engine_name or self.stt_config.get("engine", "google")
        self._fallback_enabled = self.engine_name == "google"
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = self.audio_config.get(
            "dynamic_energy_threshold", True
        )
        if not self.recognizer.dynamic_energy_threshold:
            self.recognizer.energy_threshold = self.audio_config.get(
                "energy_threshold", 300
            )
        # The wizard's pause_threshold (app_state.json) overrides the YAML
        # default when provided.
        self.recognizer.pause_threshold = (
            pause_threshold
            if pause_threshold is not None
            else self.audio_config.get("pause_threshold", 0.7)
        )
        self.recognizer.non_speaking_duration = self.audio_config.get(
            "non_speaking_duration", 0.4
        )

        self.engine: SttEngine = create_engine(
            self.engine_name,
            self.stt_config,
            self.recognizer,
            full_config=config,
        )
        self._whisper_fallback: SttEngine | None = None
        self._vosk_fallback: SttEngine | None = None
        self._on_error = on_error

        # device_index=None keeps the system default (current behavior when
        # the user never picked a mic in the wizard).
        self._mic = self._open_microphone(mic_device_id)
        self._source = self._mic
        self._cycles = 0
        self._paused = False
        self.last_timings: dict[str, float] = {}

        self._calibrate(initial=True)
        mode = (
            f"{self.engine_name} (whisper→vosk fallback offline)"
            if self._fallback_enabled
            else self.engine_name
        )
        self.logger.info(f"STT engine ativo: {mode}")

    def _open_microphone(self, mic_device_id: int | None) -> sr.Microphone:
        """Open the microphone stream, falling back to the system default.

        A stale/invalid ``mic_device_id`` (e.g. the saved mic is no longer
        connected) must not crash voice startup.  The device index is first
        validated against the available input devices; if it is invalid, or
        if opening it fails, we fall back to the system default
        (``device_index=None``).  If no microphone can be opened at all, a
        clear PT-BR error is raised so the caller can surface a dialog.
        """
        sample_rate = self.audio_config.get("sample_rate", 16000)

        def _try_open(device_index: int | None) -> sr.Microphone | None:
            mic = sr.Microphone(
                device_index=device_index,
                sample_rate=sample_rate,
            )
            try:
                mic.__enter__()
            except Exception:
                return None
            if mic.stream is None:
                return None
            return mic

        # 1. Try the explicitly requested device (if any).
        if mic_device_id is not None:
            valid = _valid_input_device_ids()
            if valid and mic_device_id not in valid:
                self.logger.warning(
                    f"Microfone {mic_device_id} inválido/indisponível; "
                    "usando o microfone padrão do sistema."
                )
            else:
                mic = _try_open(mic_device_id)
                if mic is not None:
                    return mic
                self.logger.warning(
                    f"Não foi possível abrir o microfone {mic_device_id}; "
                    "usando o microfone padrão do sistema."
                )

        # 2. Fall back to the system default microphone.
        mic = _try_open(None)
        if mic is not None:
            return mic

        raise RuntimeError(
            "Nenhum microfone disponível. Conecte um microfone e configure-o "
            "no assistente de configuração."
        )

    def _calibrate(self, initial: bool = False) -> None:
        duration = self.audio_config.get("ambient_noise_duration", 1.5)
        if initial:
            self.logger.info(
                f"Calibrando ruído de fundo ({duration}s)... fique em silêncio."
            )
        self.recognizer.adjust_for_ambient_noise(self._source, duration=duration)
        self.logger.info(f"Limiar de energia: {self.recognizer.energy_threshold:.0f}")

    def _ensure_whisper_fallback(self) -> SttEngine:
        if self._whisper_fallback is None:
            self.logger.info("Carregando Whisper (fallback offline)...")
            self._whisper_fallback = create_engine(
                "whisper", self.stt_config, self.recognizer, full_config=self.config
            )
        return self._whisper_fallback

    def _ensure_vosk_fallback(self) -> SttEngine:
        if self._vosk_fallback is None:
            self.logger.info("Carregando Vosk (fallback offline)...")
            self._vosk_fallback = create_engine(
                "vosk", self.stt_config, self.recognizer, full_config=self.config
            )
        return self._vosk_fallback

    def _switch_to_offline(self) -> None:
        """Google falhou: Whisper primeiro; se modelo faltar, Vosk."""
        try:
            self.engine = self._ensure_whisper_fallback()
            self.engine_name = "whisper"
            self._fallback_enabled = False
            self.logger.warning("Sem internet / Google falhou. Usando Whisper.")
            return
        except Exception as exc:
            self.logger.warning(f"Whisper indisponível ({exc}); tentando Vosk.")
        self.engine = self._ensure_vosk_fallback()
        self.engine_name = "vosk"
        self._fallback_enabled = False
        self.logger.warning("Usando Vosk como fallback offline.")

    def listen_once(
        self,
        timeout: float | None = None,
        stop_event: threading.Event | None = None,
    ) -> str | None:
        if self._paused:
            return None

        listen_timeout = timeout or self.audio_config.get("listen_timeout", 5)
        phrase_limit = self.audio_config.get("phrase_time_limit", 8)
        self.last_timings = {}

        try:
            t0 = time.perf_counter()
            audio = self._listen(listen_timeout, phrase_limit, stop_event)
            if audio is None:
                return None
            self.last_timings["ms_listen"] = (time.perf_counter() - t0) * 1000
        except sr.WaitTimeoutError:
            return None

        try:
            t1 = time.perf_counter()
            text = self.engine.transcribe(audio)
            self.last_timings["ms_stt"] = (time.perf_counter() - t1) * 1000
        except sr.UnknownValueError:
            self.logger.info("Não entendi.")
            return None
        except sr.RequestError as exc:
            self.logger.warning(f"Erro STT ({self.engine_name}): {exc}")
            if not self._fallback_enabled:
                return None
            try:
                self._switch_to_offline()
            except Exception as switch_exc:
                self.logger.warning(f"Fallback offline falhou: {switch_exc}")
                self._notify_error(switch_exc, "stt_fallback")
                return None
            try:
                t1 = time.perf_counter()
                text = self.engine.transcribe(audio)
                self.last_timings["ms_stt"] = (time.perf_counter() - t1) * 1000
            except Exception as fallback_exc:
                self.logger.warning(f"Fallback {self.engine_name} falhou: {fallback_exc}")
                self._notify_error(fallback_exc, "stt_fallback")
                return None

        if text:
            self._cycles += 1
        return text or None

    def _listen(
        self,
        listen_timeout: float,
        phrase_limit: float,
        stop_event: threading.Event | None,
    ):
        """Run ``recognizer.listen()``, interrupting promptly on *stop_event*.

        Without a stop_event this is a single ``listen()`` call (original
        behavior).  With a stop_event, ``listen()`` runs in short windows so
        the event is observed between windows — a phrase already in progress
        is never cut short.
        """
        if stop_event is None:
            return self.recognizer.listen(
                self._source,
                timeout=listen_timeout,
                phrase_time_limit=phrase_limit,
            )

        window = 0.5
        deadline = time.monotonic() + listen_timeout
        while not stop_event.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise sr.WaitTimeoutError("listen timeout")
            try:
                return self.recognizer.listen(
                    self._source,
                    timeout=min(window, remaining),
                    phrase_time_limit=phrase_limit,
                )
            except sr.WaitTimeoutError:
                continue  # no speech in this window — check stop_event and retry
        return None

    def _notify_error(self, exc: Exception, context: str) -> None:
        """Forward a critical STT failure to the registered callback."""
        if self._on_error is None:
            return
        try:
            self._on_error(exc, context)
        except Exception:
            pass

    def recalibrate_if_needed(self, every: int | None = None) -> None:
        interval = every or self.audio_config.get("recalibrate_every", 30)
        if self._cycles > 0 and self._cycles % interval == 0:
            self.logger.info("Recalibração periódica de ruído...")
            self._calibrate(initial=False)

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        state = "pausada" if paused else "ativa"
        self.logger.info(f"Escuta {state}.")

    @property
    def paused(self) -> bool:
        return self._paused

    def close(self) -> None:
        self._mic.__exit__(None, None, None)
