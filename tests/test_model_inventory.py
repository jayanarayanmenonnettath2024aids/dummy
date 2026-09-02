import unittest
import os
from app.models.registry import LanguageProfile, DEFAULT_LANGUAGE_REGISTRY, SHARED_WHISPER_DISK_MIB, SHARED_WHISPER_RAM_MIB
from app.models.manager import ModelManager, ModelNotInstalledError

class TestModelInventory(unittest.TestCase):
    """
    Unit test suite verifying accurate model inventory, language support,
    and non-duplicated memory accounting (Pre-Block 5).
    """

    def setUp(self):
        self.manager = ModelManager()

    # 1. Model metadata
    def test_01_model_metadata(self):
        profiles = self.manager.get_available_models()
        self.assertEqual(len(profiles), 10)
        for p in profiles:
            self.assertIsInstance(p.code, str)
            self.assertIsInstance(p.name, str)
            self.assertIsInstance(p.disk_size_mib, float)
            self.assertIsInstance(p.runtime_ram_mib, float)
            self.assertIsInstance(p.is_shared_stt_model, bool)

    # 2. Shared STT model representation
    def test_02_shared_stt_model_representation(self):
        en_profile = self.manager._registry["en"]
        ta_profile = self.manager._registry["ta"]
        hi_profile = self.manager._registry["hi"]

        self.assertTrue(en_profile.is_shared_stt_model)
        self.assertTrue(ta_profile.is_shared_stt_model)
        self.assertTrue(hi_profile.is_shared_stt_model)
        self.assertIn("whisper-tiny", en_profile.stt_model.lower())
        self.assertIn("whisper-tiny", ta_profile.stt_model.lower())
        self.assertIn("whisper-tiny", hi_profile.stt_model.lower())

    # 3. Language availability
    def test_03_language_availability(self):
        # EN, TA, HI are verified/tested
        self.assertTrue(self.manager.is_available("en", "stt"))
        self.assertTrue(self.manager.is_available("ta", "stt"))
        self.assertTrue(self.manager.is_available("hi", "stt"))

        # GU, BN are not yet verified for TTS
        self.assertFalse(self.manager.is_available("gu", "tts"))
        self.assertFalse(self.manager.is_available("bn", "tts"))

    # 4. Installed vs tested distinction
    def test_04_installed_vs_tested_distinction(self):
        gu_profile = self.manager._registry["gu"]
        # STT weights are present via shared multilingual Whisper-tiny, but not verified
        self.assertTrue(gu_profile.stt_installed)
        self.assertFalse(gu_profile.stt_tested)
        # TTS is not installed
        self.assertFalse(gu_profile.tts_installed)
        self.assertFalse(gu_profile.tts_tested)

    # 5. Disk-size reporting
    def test_05_disk_size_reporting(self):
        en_profile = self.manager._registry["en"]
        self.assertAlmostEqual(en_profile.disk_size_mib, 148.23, places=1)
        # Disk size must be strictly smaller than runtime RAM footprint
        self.assertLess(en_profile.disk_size_mib, en_profile.runtime_ram_mib)

    # 6. Runtime-memory reporting
    def test_06_runtime_memory_reporting(self):
        en_profile = self.manager._registry["en"]
        self.assertAlmostEqual(en_profile.runtime_ram_mib, 416.25, places=1)
        self.assertNotEqual(en_profile.disk_size_mib, en_profile.runtime_ram_mib, "Disk size and RAM must not be identical")

    # 7. TTS language inventory
    def test_07_tts_language_inventory(self):
        from app.tts.engine import NeuralONNXTTSEngine
        tts = NeuralONNXTTSEngine()
        info = tts.get_engine_info()
        self.assertEqual(info["engine"], "NeuralONNXTTSEngine")
        self.assertTrue(info["offline_only"])
        self.assertTrue(info["android_compatible"])
        self.assertTrue(tts.is_language_supported("en"))
        self.assertTrue(tts.is_language_supported("hi"))
        self.assertFalse(tts.is_language_supported("ta"))

    # 8. No duplicate model accounting
    def test_08_no_duplicate_model_accounting(self):
        total_disk = self.manager.get_total_disk_footprint_mib()
        # Total disk: 148.23 (Whisper) + 2.22 (VAD) + 4x VITS TTS (~60 MiB each) = ~391.0 MiB
        # It must NOT be 10 x 148.23 + 10 x 60 = 2082 MiB!
        self.assertLess(total_disk, 450.0, f"Expected non-duplicated disk footprint < 450 MiB, got {total_disk} MiB")
        self.assertGreater(total_disk, 200.0)

        unique_models = self.manager.get_unique_models()
        self.assertGreaterEqual(len(unique_models), 4)
        model_names = [m["name"] for m in unique_models]
        self.assertIn("openai/whisper-tiny", model_names)
        self.assertIn("silero_vad.onnx", model_names)
        self.assertIn("vits-piper-en_US-lessac-medium.onnx", model_names)
        self.assertIn("vits-piper-hi_IN-pratham-medium.onnx", model_names)


if __name__ == "__main__":
    unittest.main()
