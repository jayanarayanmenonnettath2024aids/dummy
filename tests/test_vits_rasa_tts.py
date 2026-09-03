import os
import unittest
import numpy as np
import soundfile as sf

from app.tts.vits_rasa_engine import NeuralVitsRasaTTSEngine
from app.models.manager import ModelManager, ModelNotInstalledError
from app.models.registry import LanguageProfile, DEFAULT_LANGUAGE_REGISTRY
from app.stt.engine import WhisperSTT
from app.vad.silero_vad import SileroVADDetector
from app.communication.packet_v2 import iTantraPacketV2
from app.security.authenticator import PacketAuthenticator
from app.security.trust_store import TrustStore

class TestVitsRasaTTS(unittest.TestCase):
    """
    Block 9.5 Comprehensive AI4Bharat VITS-RASA Test Suite.
    Verifies modular engine loading, token parsing, multi-language neural synthesis,
    Unicode handling, ModelManager routing, zero cloud fallback, and full regression safety.
    """

    @classmethod
    def setUpClass(cls):
        cls.engine = NeuralVitsRasaTTSEngine(precision="fp32")
        cls.manager = ModelManager()

    # 1. Model Discovery
    def test_01_model_discovery(self):
        supported = self.engine.get_supported_languages()
        self.assertIn("ta", supported)
        self.assertIn("kn", supported)
        self.assertIn("mr", supported)
        self.assertIn("bn", supported)
        self.assertIn("te", supported)
        self.assertIn("ml", supported)
        self.assertFalse(self.engine.is_language_supported("gu"))
        self.assertFalse(self.engine.is_language_supported("or"))

    # 2. Model Configuration
    def test_02_model_configuration(self):
        model_path, tokens_path = self.engine.get_model_paths()
        self.assertTrue(os.path.exists(model_path), f"VITS-RASA model missing at {model_path}")
        self.assertTrue(os.path.exists(tokens_path), f"VITS-RASA tokens missing at {tokens_path}")

    # 3. Tokens Loading
    def test_03_tokens_loading(self):
        _, tokens_path = self.engine.get_model_paths()
        with open(tokens_path, "r", encoding="utf-8") as f:
            tokens = [line.strip() for line in f if line.strip()]
        self.assertGreater(len(tokens), 100)

    # 4. Tamil Synthesis
    def test_04_tamil_synthesis(self):
        out_path, lat = self.engine.synthesize("கட்டளை மையத்திற்கு தகவல் தெரிவிக்கவும்", language="ta")
        self.assertTrue(os.path.exists(out_path))
        self.assertGreater(lat, 0.0)
        data, sr = sf.read(out_path)
        self.assertEqual(sr, 24000)
        self.assertFalse(np.all(data == 0))
        self.assertFalse(np.isnan(data).any())

    # 5. Kannada Synthesis
    def test_05_kannada_synthesis(self):
        out_path, lat = self.engine.synthesize("ಆದೇಶ ಕೇಂದ್ರಕ್ಕೆ ಮಾಹಿತಿ ನೀಡಿರಿ", language="kn")
        self.assertTrue(os.path.exists(out_path))
        data, sr = sf.read(out_path)
        self.assertEqual(sr, 24000)
        self.assertFalse(np.all(data == 0))

    # 6. Marathi Synthesis
    def test_06_marathi_synthesis(self):
        out_path, lat = self.engine.synthesize("कमांड केंद्राला माहिती द्या", language="mr")
        self.assertTrue(os.path.exists(out_path))
        data, sr = sf.read(out_path)
        self.assertEqual(sr, 24000)
        self.assertFalse(np.all(data == 0))

    # 7. Bengali Synthesis
    def test_07_bengali_synthesis(self):
        out_path, lat = self.engine.synthesize("কমান্ড সেন্টারে তথ্য পাঠান", language="bn")
        self.assertTrue(os.path.exists(out_path))
        data, sr = sf.read(out_path)
        self.assertEqual(sr, 24000)
        self.assertFalse(np.all(data == 0))

    # 8. Unicode Input & Complex Ligatures
    def test_08_unicode_input(self):
        out_path, _ = self.engine.synthesize("தமிழ்நாடு / ಕರ್ನಾಟಕ / महाराष्ट्र / বাংলা", language="ta")
        self.assertTrue(os.path.exists(out_path))

    # 9. Empty Input Handling
    def test_09_empty_input_handling(self):
        out_path, lat = self.engine.synthesize("", language="ta")
        self.assertTrue(os.path.exists(out_path))
        data, sr = sf.read(out_path)
        self.assertEqual(sr, 24000)

    # 10. Invalid Language Handling
    def test_10_invalid_language_handling(self):
        with self.assertRaises(ValueError):
            self.engine.synthesize("Hello", language="xx")

    # 11. Missing Model Handling
    def test_11_missing_model_handling(self):
        bogus_engine = NeuralVitsRasaTTSEngine(models_dir="C:/nonexistent_dir_123")
        with self.assertRaises(FileNotFoundError):
            bogus_engine.load_model()

    # 12. Model Unloading & Memory Freeing
    def test_12_model_unloading(self):
        self.engine.unload_model()
        self.assertIsNone(self.engine.engine)

    # 13. Audio Validity (No NaN / Inf, non-zero amplitude)
    def test_13_audio_validity(self):
        out_path, _ = self.engine.synthesize("அவசர உதவி தேவை", language="ta")
        data, _ = sf.read(out_path)
        self.assertFalse(np.isnan(data).any())
        self.assertFalse(np.isinf(data).any())
        self.assertGreater(np.max(np.abs(data)), 0.05)

    # 14. Sample Rate Validation
    def test_14_sample_rate_validation(self):
        self.assertEqual(self.engine.sample_rate, 24000)

    # 15. Silent Output Detection
    def test_15_silent_output_detection(self):
        out_path, _ = self.engine.synthesize("சோதனை செய்தி", language="ta")
        data, _ = sf.read(out_path)
        max_amp = np.max(np.abs(data))
        self.assertGreater(max_amp, 0.01)

    # 16. ModelManager Integration
    def test_16_model_manager_integration(self):
        mgr = ModelManager()
        # Tamil should load VitsRasa engine
        tts_ta = mgr.load_model("ta", task="tts")
        self.assertIsInstance(tts_ta, NeuralVitsRasaTTSEngine)

        # English should load Piper ONNX engine
        from app.tts.engine import NeuralONNXTTSEngine
        tts_en = mgr.load_model("en", task="tts")
        self.assertIsInstance(tts_en, NeuralONNXTTSEngine)

        # Gujarati should raise ModelNotInstalledError (no SAPI5 fallback)
        with self.assertRaises(ModelNotInstalledError):
            mgr.load_model("gu", task="tts")

    # 17. Piper Regression Protection (en, hi, te, ml)
    def test_17_piper_regression_protection(self):
        from app.tts.engine import NeuralONNXTTSEngine
        piper = NeuralONNXTTSEngine(precision="int8")
        for code in ["en", "hi", "te", "ml"]:
            self.assertTrue(piper.is_language_supported(code))

    # 18. Existing STT Regression Protection
    def test_18_existing_stt_regression(self):
        stt = WhisperSTT(model_name="openai/whisper-tiny")
        self.assertEqual(stt.model_name, "openai/whisper-tiny")

    # 19. Existing VAD Regression Protection
    def test_19_existing_vad_regression(self):
        vad = SileroVADDetector()
        vad.start()
        prob = vad._predict_chunk(np.zeros(512, dtype=np.float32))
        self.assertLess(prob, 0.5)
        vad.stop()

    # 20. Existing Packet & Security Regression Protection
    def test_20_existing_packet_security_regression(self):
        pkt = iTantraPacketV2(payload="Test message", language="ta", sender_id="NODE-ALPHA")
        trust_store = TrustStore(trust_file=":memory:")
        key = b"\x01" * 32
        trust_store.pair_device("NODE-ALPHA", key)
        auth = PacketAuthenticator(trust_store=trust_store)
        auth.sign_packet(pkt, key, raw_binary=True)
        self.assertEqual(len(pkt.auth_tag), 32)
        self.assertTrue(auth.verify_and_authenticate(pkt))

if __name__ == "__main__":
    unittest.main()
