import unittest
import os
from app.tts.engine import NeuralONNXTTSEngine

class TestTTSEngine(unittest.TestCase):
    def setUp(self):
        self.tts = NeuralONNXTTSEngine()

    def test_tts_initialization(self):
        self.assertIsNotNone(self.tts)
        self.assertTrue(self.tts.is_language_supported("en"))
        self.assertTrue(self.tts.is_language_supported("hi"))

    def test_tts_synthesis(self):
        text = "Test synthesis for iTantra speech loop."
        wav_path, latency = self.tts.synthesize(text, language="en", play_audio=False)
        self.assertTrue(os.path.exists(wav_path))
        self.assertGreater(os.path.getsize(wav_path), 0)
        self.assertGreater(latency, 0.0)
        # Cleanup
        try:
            os.remove(wav_path)
        except Exception:
            pass

    def test_tts_unicode_tamil(self):
        text = "வணக்கம்"  # Tamil greeting - uninstalled in offline Neural ONNX
        with self.assertRaises(ValueError):
            self.tts.synthesize(text, language="ta", play_audio=False)

if __name__ == "__main__":
    unittest.main()
