import unittest
import os
import time
import numpy as np

from app.models.manager import ModelManager, ModelNotInstalledError
from app.models.registry import LanguageProfile
from app.tts.engine import NeuralONNXTTSEngine
from app.stt.engine import WhisperSTT
from app.vad.silero_vad import SileroVADDetector
from app.vad.stream_processor import VADStreamProcessor
from app.vad.config import VADConfig
from app.communication.packet_v2 import iTantraPacketV2
from app.communication.playback_controller import PriorityPlaybackController
from app.discovery.mdns_discovery import MdnsDeviceDiscovery

class TestQuantizationAndEdgeOptimization(unittest.TestCase):
    """
    Automated Test Suite for Block 6: Edge AI Optimization, Multilingual Expansion & Quantization.
    Covers all 15 required verification areas.
    """

    def setUp(self):
        self.manager = ModelManager()

    # 1. FP32 model loading
    def test_01_fp32_model_loading(self):
        tts = NeuralONNXTTSEngine(precision="fp32")
        self.assertEqual(tts.get_precision(), "fp32")
        self.assertTrue(tts.is_language_supported("en"))
        self.assertTrue(tts.is_language_supported("hi"))

    # 2. Optimized INT8 model loading
    def test_02_optimized_int8_model_loading(self):
        tts = NeuralONNXTTSEngine(precision="int8")
        self.assertEqual(tts.get_precision(), "int8")
        self.assertTrue(tts.is_language_supported("en"))
        self.assertTrue(tts.is_language_supported("hi"))
        self.assertTrue(tts.is_language_supported("te"))
        self.assertTrue(tts.is_language_supported("ml"))

    # 3. STT inference
    def test_03_stt_inference(self):
        stt = WhisperSTT()
        transcript, lat = stt.transcribe("samples/checkpoint_en.wav", language="en")
        self.assertIsNotNone(transcript)
        self.assertGreater(len(transcript), 0)

    # 4. Multilingual TTS inference (English, Hindi, Telugu, Malayalam)
    def test_04_multilingual_tts_inference(self):
        tts = NeuralONNXTTSEngine(precision="int8")
        
        # Test English
        out_en, lat_en = tts.synthesize("Meet at checkpoint.", language="en", play_audio=False)
        self.assertTrue(os.path.exists(out_en))
        self.assertGreater(os.path.getsize(out_en), 500)

        # Test Hindi
        out_hi, lat_hi = tts.synthesize("चेकपॉइंट पर रिपोर्ट करें।", language="hi", play_audio=False)
        self.assertTrue(os.path.exists(out_hi))
        self.assertGreater(os.path.getsize(out_hi), 500)

        # Test Telugu
        out_te, lat_te = tts.synthesize("చెక్‌పాయింట్ వద్ద రిపోర్ట్ చేయండి.", language="te", play_audio=False)
        self.assertTrue(os.path.exists(out_te))
        self.assertGreater(os.path.getsize(out_te), 500)

        # Test Malayalam
        out_ml, lat_ml = tts.synthesize("ചെക്ക്പോയിന്റിൽ റിപ്പോർട്ട് ചെയ്യുക.", language="ml", play_audio=False)
        self.assertTrue(os.path.exists(out_ml))
        self.assertGreater(os.path.getsize(out_ml), 500)

    # 5. Language selection
    def test_05_language_selection(self):
        mm = ModelManager()
        self.assertTrue(mm.is_available("en", "tts"))
        self.assertTrue(mm.is_available("hi", "tts"))
        self.assertTrue(mm.is_available("te", "tts"))
        self.assertTrue(mm.is_available("ml", "tts"))

    # 6. Missing model handling (Clean Exception, Zero SAPI5 Fallback)
    def test_06_missing_model_handling(self):
        mm = ModelManager()
        with self.assertRaises(ModelNotInstalledError):
            mm.load_model("gu", task="tts")
        with self.assertRaises(ModelNotInstalledError):
            mm.load_model("or", task="tts")
        with self.assertRaises(ModelNotInstalledError):
            mm.load_model("or", task="stt")

    # 7. Model metadata
    def test_07_model_metadata(self):
        mm = ModelManager()
        models = mm.get_unique_models()
        self.assertGreaterEqual(len(models), 4)
        total_footprint = mm.get_total_disk_footprint_mib()
        self.assertGreater(total_footprint, 100.0)

    # 8. Quantized model discovery
    def test_08_quantized_model_discovery(self):
        # Verify INT8 ONNX files exist physically on disk
        en_int8 = "app/tts/models/vits-piper-en_US-lessac-medium/en_US-lessac-medium.int8.onnx"
        hi_int8 = "app/tts/models/vits-piper-hi_IN-pratham-medium/hi_IN-pratham-medium.int8.onnx"
        te_int8 = "app/tts/models/vits-piper-te_IN-maya-medium/te_IN-maya-medium.int8.onnx"
        ml_int8 = "app/tts/models/vits-piper-ml_IN-meera-medium/ml_IN-meera-medium.int8.onnx"
        self.assertTrue(os.path.exists(en_int8))
        self.assertTrue(os.path.exists(hi_int8))
        self.assertTrue(os.path.exists(te_int8))
        self.assertTrue(os.path.exists(ml_int8))

    # 9. Model precision switching (Runtime Abstraction)
    def test_09_model_precision_switching(self):
        mm = ModelManager(precision="fp32")
        self.assertEqual(mm.get_precision(), "fp32")
        
        mm.set_precision("int8")
        self.assertEqual(mm.get_precision(), "int8")

        engine = mm.load_model("en", task="tts")
        self.assertEqual(engine.get_precision(), "int8")

    # 10. Existing packet pipeline
    def test_10_existing_packet_pipeline(self):
        pkt = iTantraPacketV2(
            payload="Quantized Pipeline Active",
            priority=iTantraPacketV2.PRIORITY_ALERT,
            message_type=iTantraPacketV2.MESSAGE_TYPE_ALERT
        )
        b = pkt.to_binary()
        unpacked = iTantraPacketV2.from_binary(b)
        self.assertEqual(unpacked.payload, "Quantized Pipeline Active")
        self.assertEqual(unpacked.priority, iTantraPacketV2.PRIORITY_ALERT)

    # 11. Existing VAD
    def test_11_existing_vad(self):
        vad = SileroVADDetector()
        self.assertIsNotNone(vad._session)
        vad.start()
        chunk = np.zeros(512, dtype=np.float32)
        vad.process_chunk(chunk)
        prob = vad._predict_chunk(chunk)
        self.assertLess(prob, 0.5)
        vad.stop()

    # 12. Existing priority system
    def test_12_existing_priority_system(self):
        ctrl = PriorityPlaybackController()
        status = ctrl.get_queue_status()
        self.assertEqual(status["queue_depth"], 0)
        ctrl.stop()

    # 13. Existing PTT mode
    def test_13_existing_ptt_mode(self):
        proc = VADStreamProcessor(config=VADConfig())
        proc.set_mode("ptt")
        self.assertEqual(proc.mode, "ptt")
        self.assertFalse(proc.is_running)

    # 14. Existing Voice Mode
    def test_14_existing_voice_mode(self):
        proc = VADStreamProcessor(config=VADConfig())
        proc.set_mode("voice")
        self.assertEqual(proc.mode, "voice")
        proc.stop_live_mic()

    # 15. mDNS discovery
    def test_15_mdns_discovery(self):
        disc = MdnsDeviceDiscovery(
            node_id="TEST-NODE-B6",
            device_name="Test Edge Node",
            tcp_port=65432
        )
        self.assertEqual(disc.device_name, "Test Edge Node")


if __name__ == "__main__":
    unittest.main()
