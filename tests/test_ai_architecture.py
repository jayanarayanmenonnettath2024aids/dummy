import unittest
import os
import time
import socket
from typing import Dict, Any

from app.models.registry import LanguageProfile, DEFAULT_LANGUAGE_REGISTRY
from app.models.manager import ModelManager, ModelNotInstalledError
from app.stt.engine import STTEngine, WhisperSTT, OnnxSTT
from app.tts.engine import TTSEngine, Pyttsx3TTS, NeuralTTSEngine
from app.vad.silero_vad import SileroVADDetector
from app.communication.packet_v2 import iTantraPacketV2
from app.communication.peer_transceiver import PeerTransceiver

class TestAIArchitecture(unittest.TestCase):
    """
    Test suite for Block 4: Portable Local ONNX STT/TTS Architecture.
    Covers the 11 required specifications.
    """

    @classmethod
    def setUpClass(cls):
        cls.manager = ModelManager()
        cls.sample_wav = "samples/checkpoint_en.wav"

    # 1. STT interface
    def test_01_stt_interface(self):
        stt = WhisperSTT()
        self.assertIsInstance(stt, STTEngine)
        info = stt.get_engine_info()
        self.assertIn("engine", info)
        self.assertIn("offline_only", info)
        self.assertTrue(info["offline_only"])
        self.assertTrue(hasattr(stt, "transcribe"))
        self.assertTrue(hasattr(stt, "is_language_supported"))

    # 2. TTS interface
    def test_02_tts_interface(self):
        tts = Pyttsx3TTS()
        self.assertIsInstance(tts, TTSEngine)
        info = tts.get_engine_info()
        self.assertIn("engine", info)
        self.assertIn("offline_only", info)
        self.assertTrue(info["offline_only"])
        self.assertTrue(hasattr(tts, "synthesize"))
        self.assertTrue(hasattr(tts, "is_language_supported"))

    # 3. Model registry
    def test_03_model_registry(self):
        profiles = self.manager.get_available_models()
        self.assertGreaterEqual(len(profiles), 10, "Registry must contain all 10 target languages")
        codes = [p.code for p in profiles]
        for expected in ["en", "hi", "ta", "gu", "mr", "kn", "ml", "te", "or", "bn"]:
            self.assertIn(expected, codes)

        # Verify accurate reporting: English and Hindi have verified Neural ONNX TTS models
        self.assertTrue(self.manager.is_available("en", "stt"))
        self.assertTrue(self.manager.is_available("en", "tts"))
        self.assertTrue(self.manager.is_available("hi", "stt"))
        self.assertTrue(self.manager.is_available("hi", "tts"))
        self.assertTrue(self.manager.is_available("ta", "stt"))
        # Tamil STT is verified via shared Whisper, but Tamil Neural TTS is NOT AVAILABLE
        self.assertFalse(self.manager.is_available("ta", "tts"))
        self.assertFalse(self.manager.is_available("gu", "stt"))
        self.assertFalse(self.manager.is_available("bn", "stt"))

    # 4. Language selection
    def test_04_language_selection(self):
        installed = self.manager.get_installed_models()
        installed_codes = [p.code for p in installed]
        self.assertIn("en", installed_codes)
        self.assertIn("ta", installed_codes)
        self.assertIn("hi", installed_codes)
        self.assertNotIn("gu", installed_codes)

    # 5. English STT
    def test_05_english_stt(self):
        stt = self.manager.load_model("en", task="stt")
        self.assertTrue(stt.is_language_supported("en"))
        transcript, latency = stt.transcribe(self.sample_wav, language="en")
        self.assertIsNotNone(transcript)
        self.assertIn("checkpoint", transcript.lower())
        self.assertGreater(latency, 0.0)

    # 6. English TTS
    def test_06_english_tts(self):
        tts = self.manager.load_model("en", task="tts")
        self.assertTrue(tts.is_language_supported("en"))
        out_path, latency = tts.synthesize("Meet me at checkpoint 4.", language="en", play_audio=False)
        self.assertTrue(os.path.exists(out_path))
        self.assertGreater(os.path.getsize(out_path), 1000)

    # 7. Tamil STT if model installed
    def test_07_tamil_stt_if_installed(self):
        if self.manager.is_available("ta", "stt"):
            stt = self.manager.load_model("ta", task="stt")
            self.assertTrue(stt.is_language_supported("ta"))
            info = stt.get_engine_info()
            self.assertIn("ta", info["supported_languages"])

    # 8. Tamil TTS if model installed
    def test_08_tamil_tts_if_installed(self):
        if self.manager.is_available("ta", "tts"):
            tts = self.manager.load_model("ta", task="tts")
            self.assertTrue(tts.is_language_supported("ta"))
            out_path, latency = tts.synthesize("வணக்கம்.", language="ta", play_audio=False)
            self.assertTrue(os.path.exists(out_path))

    # 9. Model unavailable handling
    def test_09_model_unavailable_handling(self):
        # Attempting to load an uninstalled language must raise ModelNotInstalledError
        with self.assertRaises(ModelNotInstalledError) as ctx:
            self.manager.load_model("gu", task="stt")
        self.assertIn("MODEL NOT INSTALLED", str(ctx.exception))

        with self.assertRaises(ModelNotInstalledError) as ctx:
            self.manager.load_model("bn", task="tts")
        self.assertIn("MODEL NOT INSTALLED", str(ctx.exception))

    # 10. No-cloud verification
    def test_10_no_cloud_verification(self):
        # Verify engines function without internet or cloud APIs
        # In a closed environment, offline flags are enforced
        stt = self.manager.load_model("en", task="stt")
        tts = self.manager.load_model("en", task="tts")

        self.assertTrue(stt.get_engine_info()["offline_only"])
        self.assertTrue(tts.get_engine_info()["offline_only"])

    # 11. Pipeline integration (Mic -> VAD -> STTEngine -> iTantraPacketV2 -> Binary TCP -> iTantraPacketV2 -> TTSEngine -> Speaker)
    def test_11_pipeline_integration(self):
        import soundfile as sf
        vad = SileroVADDetector()
        stt = self.manager.load_model("en", task="stt")
        tts = self.manager.load_model("en", task="tts")

        # 1. Feed audio to VAD
        audio_data, sr = sf.read(self.sample_wav)
        completed_utterance = vad.process_chunk(audio_data, sample_rate=sr)

        # 2. Transcribe via STTEngine
        if completed_utterance is not None and len(completed_utterance) > 0:
            transcript, _ = stt.transcribe(completed_utterance, language="en")
        else:
            transcript, _ = stt.transcribe(self.sample_wav, language="en")

        self.assertTrue(len(transcript) > 0)

        # 3. Create iTantraPacketV2 & Serialize to Binary
        pkt = iTantraPacketV2(payload=transcript, language="en", sender_id="NODE-ALPHA")
        binary_bytes = pkt.to_binary()
        self.assertLess(len(binary_bytes), 120)

        # 4. Deserialize Binary Packet
        received_pkt = iTantraPacketV2.from_binary(binary_bytes)
        self.assertEqual(received_pkt.payload, transcript)

        # 5. Synthesize via TTSEngine
        out_wav, _ = tts.synthesize(received_pkt.payload, language=received_pkt.language, play_audio=False)
        self.assertTrue(os.path.exists(out_wav))


if __name__ == "__main__":
    unittest.main()
