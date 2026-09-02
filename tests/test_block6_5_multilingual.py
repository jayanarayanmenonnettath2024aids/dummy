import unittest
import os
import numpy as np

from app.models.manager import ModelManager, ModelNotInstalledError
from app.models.registry import LanguageProfile, DEFAULT_LANGUAGE_REGISTRY
from app.tts.engine import NeuralONNXTTSEngine
from app.stt.engine import WhisperSTT
from app.vad.silero_vad import SileroVADDetector
from app.vad.stream_processor import VADStreamProcessor
from app.vad.config import VADConfig
from app.communication.packet_v2 import iTantraPacketV2
from app.communication.playback_controller import PriorityPlaybackController
from app.discovery.mdns_discovery import MdnsDeviceDiscovery

class TestBlock6_5Multilingual(unittest.TestCase):
    """
    Comprehensive Block 6.5 Automated Test Suite covering all 26 required areas:
    - Language codes & availability
    - STT/TTS model selection & precision switching
    - Honest missing-model error handling (zero SAPI5/pyttsx3/cloud fallback)
    - 10-language pipelines (EN, HI, TE, ML, TA, GU, MR, KN, BN, OR)
    - Full regression preservation for VAD, packet, priority, discovery, and dual mode.
    """

    def setUp(self):
        self.manager = ModelManager()

    # 1. All 10 language codes
    def test_01_all_10_language_codes(self):
        expected_codes = {"en", "hi", "gu", "mr", "kn", "ml", "ta", "te", "or", "bn"}
        registry_codes = set(DEFAULT_LANGUAGE_REGISTRY.keys())
        self.assertEqual(expected_codes, registry_codes)

    # 2. Language selection
    def test_02_language_selection(self):
        name_en = self.manager.get_language_name("en")
        name_hi = self.manager.get_language_name("hi")
        name_te = self.manager.get_language_name("te")
        name_ml = self.manager.get_language_name("ml")
        self.assertEqual(name_en, "English")
        self.assertEqual(name_hi, "Hindi")
        self.assertEqual(name_te, "Telugu")
        self.assertEqual(name_ml, "Malayalam")

    # 3. STT model selection
    def test_03_stt_model_selection(self):
        stt_en = self.manager.load_model("en", task="stt")
        self.assertIsInstance(stt_en, WhisperSTT)

    # 4. TTS model selection
    def test_04_tts_model_selection(self):
        tts_en = self.manager.load_model("en", task="tts")
        self.assertIsInstance(tts_en, NeuralONNXTTSEngine)

    # 5. Model availability detection
    def test_05_model_availability_detection(self):
        # 4 full languages
        self.assertTrue(self.manager.is_available("en", "all"))
        self.assertTrue(self.manager.is_available("hi", "all"))
        self.assertTrue(self.manager.is_available("te", "all"))
        self.assertTrue(self.manager.is_available("ml", "all"))
        # 5 STT-only languages
        self.assertTrue(self.manager.is_available("ta", "stt"))
        self.assertFalse(self.manager.is_available("ta", "tts"))
        self.assertFalse(self.manager.is_available("ta", "all"))

    # 6. Missing-model handling (Honest exception, zero SAPI5 fallback)
    def test_06_missing_model_handling(self):
        with self.assertRaises(ModelNotInstalledError):
            self.manager.load_model("ta", task="tts")
        with self.assertRaises(ModelNotInstalledError):
            self.manager.load_model("gu", task="tts")

    # 7. Precision selection
    def test_07_precision_selection(self):
        self.manager.set_precision("int8")
        self.assertEqual(self.manager.get_precision(), "int8")
        self.manager.set_precision("fp32")
        self.assertEqual(self.manager.get_precision(), "fp32")

    # 8. FP32 selection
    def test_08_fp32_selection(self):
        tts = NeuralONNXTTSEngine(precision="fp32")
        self.assertEqual(tts.get_precision(), "fp32")

    # 9. INT8 selection
    def test_09_int8_selection(self):
        tts = NeuralONNXTTSEngine(precision="int8")
        self.assertEqual(tts.get_precision(), "int8")

    # 10. Odia unsupported handling
    def test_10_odia_unsupported_handling(self):
        self.assertFalse(self.manager.is_available("or", "stt"))
        self.assertFalse(self.manager.is_available("or", "tts"))
        self.assertFalse(self.manager.is_available("or", "all"))
        with self.assertRaises(ModelNotInstalledError):
            self.manager.load_model("or", task="stt")
        with self.assertRaises(ModelNotInstalledError):
            self.manager.load_model("or", task="tts")

    # 11. Tamil pipeline
    def test_11_tamil_pipeline(self):
        profile = DEFAULT_LANGUAGE_REGISTRY["ta"]
        self.assertTrue(profile.stt_installed)
        self.assertFalse(profile.tts_installed)
        with self.assertRaises(ModelNotInstalledError):
            self.manager.load_model("ta", task="tts")

    # 12. Gujarati pipeline
    def test_12_gujarati_pipeline(self):
        profile = DEFAULT_LANGUAGE_REGISTRY["gu"]
        self.assertTrue(profile.stt_installed)
        self.assertFalse(profile.tts_installed)
        with self.assertRaises(ModelNotInstalledError):
            self.manager.load_model("gu", task="tts")

    # 13. Marathi pipeline
    def test_13_marathi_pipeline(self):
        profile = DEFAULT_LANGUAGE_REGISTRY["mr"]
        self.assertTrue(profile.stt_installed)
        self.assertFalse(profile.tts_installed)
        with self.assertRaises(ModelNotInstalledError):
            self.manager.load_model("mr", task="tts")

    # 14. Kannada pipeline
    def test_14_kannada_pipeline(self):
        profile = DEFAULT_LANGUAGE_REGISTRY["kn"]
        self.assertTrue(profile.stt_installed)
        self.assertFalse(profile.tts_installed)
        with self.assertRaises(ModelNotInstalledError):
            self.manager.load_model("kn", task="tts")

    # 15. Malayalam pipeline
    def test_15_malayalam_pipeline(self):
        self.assertTrue(self.manager.is_available("ml", "all"))
        tts = self.manager.load_model("ml", task="tts")
        out, lat = tts.synthesize("റിപ്പോർട്ട് ചെയ്യുക.", language="ml", play_audio=False)
        self.assertTrue(os.path.exists(out))

    # 16. Telugu pipeline
    def test_16_telugu_pipeline(self):
        self.assertTrue(self.manager.is_available("te", "all"))
        tts = self.manager.load_model("te", task="tts")
        out, lat = tts.synthesize("రిపోర్ట్ చేయండి.", language="te", play_audio=False)
        self.assertTrue(os.path.exists(out))

    # 17. Bengali pipeline
    def test_17_bengali_pipeline(self):
        profile = DEFAULT_LANGUAGE_REGISTRY["bn"]
        self.assertTrue(profile.stt_installed)
        self.assertFalse(profile.tts_installed)
        with self.assertRaises(ModelNotInstalledError):
            self.manager.load_model("bn", task="tts")

    # 18. English pipeline
    def test_18_english_pipeline(self):
        self.assertTrue(self.manager.is_available("en", "all"))
        tts = self.manager.load_model("en", task="tts")
        out, lat = tts.synthesize("Tactical status normal.", language="en", play_audio=False)
        self.assertTrue(os.path.exists(out))

    # 19. Hindi pipeline
    def test_19_hindi_pipeline(self):
        self.assertTrue(self.manager.is_available("hi", "all"))
        tts = self.manager.load_model("hi", task="tts")
        out, lat = tts.synthesize("स्थिति सामान्य है।", language="hi", play_audio=False)
        self.assertTrue(os.path.exists(out))

    # 20. Existing VAD
    def test_20_existing_vad(self):
        vad = SileroVADDetector()
        self.assertIsNotNone(vad._session)
        vad.start()
        chunk = np.zeros(512, dtype=np.float32)
        vad.process_chunk(chunk)
        prob = vad._predict_chunk(chunk)
        self.assertLess(prob, 0.5)
        vad.stop()

    # 21. Existing packet protocol
    def test_21_existing_packet_protocol(self):
        pkt = iTantraPacketV2(
            payload="Block 6.5 Multilingual Freeze",
            priority=iTantraPacketV2.PRIORITY_DISTRESS,
            message_type=iTantraPacketV2.MESSAGE_TYPE_DISTRESS,
            language="hi"
        )
        b = pkt.to_binary()
        restored = iTantraPacketV2.from_binary(b)
        self.assertEqual(restored.payload, "Block 6.5 Multilingual Freeze")
        self.assertEqual(restored.priority, iTantraPacketV2.PRIORITY_DISTRESS)

    # 22. Existing mDNS discovery
    def test_22_existing_mdns_discovery(self):
        disc = MdnsDeviceDiscovery(
            node_id="NODE-B6-5",
            device_name="Multilingual Field Unit",
            tcp_port=65432
        )
        self.assertEqual(disc.device_name, "Multilingual Field Unit")

    # 23. Existing priority system
    def test_23_existing_priority_system(self):
        ctrl = PriorityPlaybackController()
        status = ctrl.get_queue_status()
        self.assertEqual(status["queue_depth"], 0)
        ctrl.stop()

    # 24. Existing PTT mode
    def test_24_existing_ptt_mode(self):
        proc = VADStreamProcessor(config=VADConfig())
        proc.set_mode("ptt")
        self.assertEqual(proc.mode, "ptt")

    # 25. Existing Voice Mode
    def test_25_existing_voice_mode(self):
        proc = VADStreamProcessor(config=VADConfig())
        proc.set_mode("voice")
        self.assertEqual(proc.mode, "voice")
        proc.stop_live_mic()

    # 26. Existing security-independent communication behavior
    def test_26_security_independent_communication(self):
        pkt = iTantraPacketV2(payload="Payload Integrity")
        raw = pkt.to_binary()
        self.assertTrue(raw.startswith(b"IT\x02"))
        unpacked = iTantraPacketV2.from_binary(raw)
        self.assertEqual(unpacked.payload, "Payload Integrity")

if __name__ == "__main__":
    unittest.main()
