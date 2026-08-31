import unittest
import os
from app.tts.engine import Pyttsx3TTSEngine

class TestTTSEngine(unittest.TestCase):
    def setUp(self):
        self.tts = Pyttsx3TTSEngine()

    def test_tts_initialization(self):
        self.assertIsNotNone(self.tts)

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
        text = "வணக்கம்"  # Tamil greeting
        wav_path, latency = self.tts.synthesize(text, language="ta", play_audio=False)
        self.assertTrue(os.path.exists(wav_path))
        try:
            os.remove(wav_path)
        except Exception:
            pass

if __name__ == "__main__":
    unittest.main()
