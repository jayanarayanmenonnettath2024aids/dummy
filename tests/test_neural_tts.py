import unittest
import os
import soundfile as sf
from app.tts.engine import NeuralONNXTTSEngine, TTSEngine
from app.models.manager import ModelManager, ModelNotInstalledError
from app.stt.engine import WhisperSTT
from app.communication.packet_v2 import iTantraPacketV2

class TestNeuralONNXTTS(unittest.TestCase):
    """
    Test suite for Portable Neural ONNX TTS Architecture (Pre-Block 5 TTS Correction).
    Verifies pure local ONNX inference, zero SAPI5 fallback, Android compatibility,
    and end-to-end STT -> PacketV2 -> Neural TTS pipeline.
    """

    def setUp(self):
        self.tts = NeuralONNXTTSEngine()
        self.manager = ModelManager()

    # 1. Engine Initialization
    def test_01_neural_tts_initialization(self):
        self.assertIsInstance(self.tts, TTSEngine)
        info = self.tts.get_engine_info()
        self.assertEqual(info["engine"], "NeuralONNXTTSEngine")
        self.assertTrue(info["offline_only"])
        self.assertTrue(info["android_compatible"])
        self.assertIn("en", info["supported_languages"])
        self.assertIn("hi", info["supported_languages"])

    # 2. Model Loading
    def test_02_model_loading(self):
        en_tts = self.tts._get_or_load_tts("en")
        self.assertIsNotNone(en_tts)
        hi_tts = self.tts._get_or_load_tts("hi")
        self.assertIsNotNone(hi_tts)

    # 3. Local Inference (English)
    def test_03_english_local_inference(self):
        text = "Meet me at checkpoint 4."
        out_wav, lat = self.tts.synthesize(text, language="en", play_audio=False)
        self.assertTrue(os.path.exists(out_wav))
        self.assertGreater(os.path.getsize(out_wav), 1000)
        self.assertLess(lat, 2.0, "Inference latency must be sub-2-second on CPU")
        
        # Verify valid WAV format
        data, samplerate = sf.read(out_wav)
        self.assertGreater(len(data), 0)
        self.assertEqual(samplerate, 22050)

    # 4. Local Inference (Hindi)
    def test_04_hindi_local_inference(self):
        text = "नमस्ते, चेकपॉइंट चार पर मिलें।"
        out_wav, lat = self.tts.synthesize(text, language="hi", play_audio=False)
        self.assertTrue(os.path.exists(out_wav))
        self.assertGreater(os.path.getsize(out_wav), 1000)
        self.assertLess(lat, 2.0)
        
        data, samplerate = sf.read(out_wav)
        self.assertGreater(len(data), 0)
        self.assertEqual(samplerate, 22050)

    # 5. Language Selection
    def test_05_language_selection(self):
        self.assertTrue(self.tts.is_language_supported("en"))
        self.assertTrue(self.tts.is_language_supported("hi"))
        self.assertFalse(self.tts.is_language_supported("ta"))
        self.assertFalse(self.tts.is_language_supported("gu"))

    # 6. Invalid Language Handling
    def test_06_invalid_language_handling(self):
        with self.assertRaises(ValueError):
            self.tts.synthesize("Hello", language="invalid_lang", play_audio=False)

    # 7. Missing Model Handling (Zero SAPI5 fallback)
    def test_07_missing_model_handling_no_sapi5(self):
        # Gujarati currently has no neural ONNX model installed
        with self.assertRaises(ValueError):
            self.tts.synthesize("નમસ્તે", language="gu", play_audio=False)

        # ModelManager must also raise ModelNotInstalledError
        with self.assertRaises(ModelNotInstalledError):
            self.manager.load_model("gu", task="tts")

    # 8. No Network Dependency
    def test_08_no_network_dependency(self):
        info = self.tts.get_engine_info()
        self.assertTrue(info["offline_only"])
        # Both models exist strictly on local disk
        en_meta = self.tts.LANGUAGE_MODELS["en"]
        en_path = os.path.join(self.tts.models_dir, en_meta["dir"], en_meta["model_file"])
        self.assertTrue(os.path.exists(en_path))

    # 9. Model Metadata
    def test_09_model_metadata(self):
        profiles = self.manager.get_available_models()
        en_prof = [p for p in profiles if p.code == "en"][0]
        self.assertEqual(en_prof.tts_engine_type, "neural_onnx")
        self.assertEqual(en_prof.tts_disk_size_mib, 60.27)
        self.assertTrue(en_prof.tts_available)

        gu_prof = [p for p in profiles if p.code == "gu"][0]
        self.assertFalse(gu_prof.tts_available)
        self.assertEqual(gu_prof.tts_engine_type, "none")

    # 10. Runtime Memory Measurement
    def test_10_runtime_memory_measurement(self):
        unique_models = self.manager.get_unique_models()
        self.assertGreaterEqual(len(unique_models), 4)
        names = [m["name"] for m in unique_models]
        self.assertIn("vits-piper-en_US-lessac-medium.onnx", names)
        self.assertIn("vits-piper-hi_IN-pratham-medium.onnx", names)

    # 11. Full End-to-End Pipeline (STT -> Binary Packet -> Neural TTS)
    def test_11_pipeline_integration(self):
        stt = WhisperSTT()
        transcript, stt_lat = stt.transcribe("samples/checkpoint_en.wav", language="en")
        self.assertTrue(len(transcript) > 0)

        packet = iTantraPacketV2(
            payload=transcript,
            language="en",
            sender_id="NODE-ALPHA",
            session_id="SESS-001",
            sequence_number=1
        )
        binary_data = packet.to_binary()
        self.assertGreater(len(binary_data), 0)

        reconstructed = iTantraPacketV2.from_binary(binary_data)
        self.assertEqual(reconstructed.payload, transcript)

        out_wav, tts_lat = self.tts.synthesize(reconstructed.payload, language=reconstructed.language, play_audio=False)
        self.assertTrue(os.path.exists(out_wav))
        self.assertGreater(os.path.getsize(out_wav), 1000)


if __name__ == "__main__":
    unittest.main()
