import unittest
import os
from app.stt.engine import WhisperSTTEngine

class TestSTTEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stt = WhisperSTTEngine()
        cls.sample_path = "samples/checkpoint_en.wav"

    def test_stt_initialization(self):
        self.assertIsNotNone(self.stt)

    def test_stt_transcription(self):
        self.assertTrue(os.path.exists(self.sample_path))
        transcript, latency = self.stt.transcribe(self.sample_path, language="en")
        self.assertIsInstance(transcript, str)
        self.assertGreater(len(transcript), 0)
        self.assertGreater(latency, 0.0)
        print(f"\n[Test STT] Transcript: '{transcript}', Latency: {latency*1000:.1f}ms")

if __name__ == "__main__":
    unittest.main()
