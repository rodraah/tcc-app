"""Testes do listener e engines STT (sem microfone)."""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import speech_recognition as sr

from voice.stt_engines import GoogleEngine, VoskEngine, WhisperEngine, create_engine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VOSK_MODEL = PROJECT_ROOT / "models" / "vosk-model-small-pt-0.3"


class TestCreateEngine(unittest.TestCase):
    def test_create_vosk_engine(self):
        if not VOSK_MODEL.exists():
            self.skipTest("Modelo Vosk não instalado")
        engine = create_engine("vosk", {"vosk_model_path": str(VOSK_MODEL)}, sr.Recognizer())
        self.assertIsInstance(engine, VoskEngine)

    def test_create_google_engine(self):
        engine = create_engine("google", {"language": "pt-BR"}, sr.Recognizer())
        self.assertIsInstance(engine, GoogleEngine)

    def test_create_whisper_engine_lazy(self):
        engine = create_engine(
            "whisper",
            {"whisper_model": "base", "whisper_device": "cpu"},
            sr.Recognizer(),
        )
        self.assertIsInstance(engine, WhisperEngine)
        self.assertIsNone(engine._model)

    def test_unknown_engine_raises(self):
        with self.assertRaises(ValueError):
            create_engine("azure", {}, sr.Recognizer())


class TestGoogleEngine(unittest.TestCase):
    def test_transcribe_calls_recognize_google(self):
        recognizer = MagicMock(spec=sr.Recognizer)
        recognizer.recognize_google.return_value = "assistente abrir notepad"
        engine = GoogleEngine(recognizer, "pt-BR")
        audio = MagicMock(spec=sr.AudioData)

        text = engine.transcribe(audio)

        self.assertEqual(text, "assistente abrir notepad")
        recognizer.recognize_google.assert_called_once_with(
            audio, language="pt-BR", show_all=True
        )


class TestWhisperEngine(unittest.TestCase):
    def test_transcribe_uses_faster_whisper(self):
        engine = WhisperEngine(model_size="base", device="cpu", language="pt")
        audio = MagicMock(spec=sr.AudioData)
        audio.get_raw_data.return_value = b"\x00\x00" * 1600

        seg = MagicMock()
        seg.text = " abrir navegador "
        fake_model = MagicMock()
        fake_model.transcribe.return_value = ([seg], MagicMock())

        with patch.object(engine, "_ensure_model", return_value=fake_model):
            text = engine.transcribe(audio)

        self.assertEqual(text, "abrir navegador")
        fake_model.transcribe.assert_called_once()
        kwargs = fake_model.transcribe.call_args.kwargs
        self.assertEqual(kwargs.get("language"), "pt")
        self.assertTrue(kwargs.get("vad_filter"))


class TestVoskEngine(unittest.TestCase):
    def test_transcribe_returns_string(self):
        if not VOSK_MODEL.exists():
            self.skipTest("Modelo Vosk não instalado")
        engine = VoskEngine(VOSK_MODEL)
        # Áudio silencioso mínimo (16kHz, 16-bit, ~0.5s)
        silent = b"\x00\x00" * 8000
        audio = sr.AudioData(silent, 16000, 2)
        text = engine.transcribe(audio)
        self.assertIsInstance(text, str)


class TestHybridListenerListen(unittest.TestCase):
    @patch("voice.listener.sr.Microphone")
    def test_listen_once_timeout_returns_none(self, mock_mic_cls):
        from voice.listener import HybridListener

        mock_mic = MagicMock()
        mock_mic_cls.return_value = mock_mic

        config = {
            "audio": {"ambient_noise_duration": 0.01, "listen_timeout": 1},
            "stt": {"engine": "google", "language": "pt-BR"},
        }

        with patch.object(HybridListener, "_calibrate"):
            listener = HybridListener(config, engine_name="google")

        listener.recognizer.listen = MagicMock(
            side_effect=sr.WaitTimeoutError("timeout")
        )
        result = listener.listen_once()
        self.assertIsNone(result)
        listener.close()

    @patch("voice.listener.sr.Microphone")
    def test_google_request_error_falls_back_to_whisper(self, mock_mic_cls):
        from voice.listener import HybridListener

        mock_mic_cls.return_value = MagicMock()
        config = {
            "audio": {"ambient_noise_duration": 0.01, "listen_timeout": 1},
            "stt": {"engine": "google", "language": "pt-BR"},
        }

        with patch.object(HybridListener, "_calibrate"):
            listener = HybridListener(config, engine_name="google")

        audio = MagicMock(spec=sr.AudioData)
        listener.recognizer.listen = MagicMock(return_value=audio)
        listener.engine.transcribe = MagicMock(
            side_effect=sr.RequestError("offline")
        )
        whisper = MagicMock()
        whisper.transcribe.return_value = "abrir navegador"
        with patch.object(listener, "_ensure_whisper_fallback", return_value=whisper):
            result = listener.listen_once()

        self.assertEqual(result, "abrir navegador")
        self.assertEqual(listener.engine_name, "whisper")
        listener.close()

    @patch("voice.listener.sr.Microphone")
    def test_google_falls_to_vosk_if_whisper_missing(self, mock_mic_cls):
        from voice.listener import HybridListener

        mock_mic_cls.return_value = MagicMock()
        config = {
            "audio": {"ambient_noise_duration": 0.01, "listen_timeout": 1},
            "stt": {"engine": "google", "language": "pt-BR"},
        }

        with patch.object(HybridListener, "_calibrate"):
            listener = HybridListener(config, engine_name="google")

        audio = MagicMock(spec=sr.AudioData)
        listener.recognizer.listen = MagicMock(return_value=audio)
        listener.engine.transcribe = MagicMock(
            side_effect=sr.RequestError("offline")
        )
        vosk = MagicMock()
        vosk.transcribe.return_value = "abrir notepad"
        with patch.object(
            listener,
            "_ensure_whisper_fallback",
            side_effect=FileNotFoundError("no model"),
        ):
            with patch.object(listener, "_ensure_vosk_fallback", return_value=vosk):
                result = listener.listen_once()

        self.assertEqual(result, "abrir notepad")
        self.assertEqual(listener.engine_name, "vosk")
        listener.close()


if __name__ == "__main__":
    unittest.main()
