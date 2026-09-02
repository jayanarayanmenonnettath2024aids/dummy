import unittest
import os
import time
import numpy as np
import soundfile as sf

from app.vad.config import VADConfig
from app.vad.silero_vad import SileroVADDetector
from app.vad.stream_processor import VADStreamProcessor
from app.stt.engine import WhisperSTTEngine
from app.communication.peer_transceiver import PeerTransceiver
from app.tts.engine import BaseTTSEngine

class MockTTSEngine(BaseTTSEngine):
    def synthesize(self, text: str, language: str = "en", output_path=None, play_audio=False):
        return "mock.wav", 0.01


class TestStreamingVAD(unittest.TestCase):
    """
    Test suite for Block 2: Streaming Voice Activity Detection
    Covers the 10 required specifications.
    """

    @classmethod
    def setUpClass(cls):
        cls.sample_path = "samples/checkpoint_en.wav"
        if os.path.exists(cls.sample_path):
            data, sr = sf.read(cls.sample_path)
            # Ensure 16kHz float32
            if data.ndim > 1:
                data = np.mean(data, axis=1)
            if sr != 16000:
                from scipy.signal import resample
                num_samples = int(len(data) * 16000 / sr)
                data = resample(data, num_samples).astype(np.float32)
            else:
                data = data.astype(np.float32)
            cls.real_audio = data
            cls.sample_rate = 16000
        else:
            cls.sample_rate = 16000
            cls.real_audio = np.zeros(32000, dtype=np.float32)

    def setUp(self):
        self.config = VADConfig(
            speech_start_threshold=0.5,
            silence_duration_ms=400.0,
            minimum_speech_ms=200.0,
            maximum_utterance_ms=5000.0,
            pre_speech_buffer_ms=200.0,
            post_speech_buffer_ms=100.0
        )
        self.detector = SileroVADDetector(config=self.config)

    # 1. Silence does not trigger STT
    def test_01_silence_does_not_trigger_stt(self):
        started_events = []
        ended_events = []
        self.detector.on_speech_started(lambda ts: started_events.append(ts))
        self.detector.on_speech_ended(lambda utt, dur: ended_events.append(utt))

        # Feed 2 seconds of pure ambient silence / low hiss
        silence_chunk = np.random.normal(0, 0.0001, 32000).astype(np.float32)
        res = self.detector.process_chunk(silence_chunk)

        self.assertIsNone(res)
        self.assertEqual(len(started_events), 0, "Silence triggered speech_started")
        self.assertEqual(len(ended_events), 0, "Silence triggered speech_ended")

    # 2. Speech triggers speech_started
    def test_02_speech_triggers_speech_started(self):
        started_events = []
        self.detector.on_speech_started(lambda ts: started_events.append(ts))

        # Feed real speech audio
        self.detector.process_chunk(self.real_audio[:16000])  # First 1 second of speech
        self.assertGreater(len(started_events), 0, "Speech failed to trigger speech_started")

    # 3. Silence after speech triggers speech_ended
    def test_03_silence_after_speech_triggers_speech_ended(self):
        ended_events = []
        self.detector.on_speech_ended(lambda utt, dur: ended_events.append(utt))

        # Feed speech chunk followed by sufficient silence (> silence_duration_ms)
        self.detector.process_chunk(self.real_audio[:24000])
        silence_tail = np.zeros(16000, dtype=np.float32)  # 1 second silence
        res = self.detector.process_chunk(silence_tail)

        self.assertGreater(len(ended_events), 0, "Silence after speech did not trigger speech_ended")
        self.assertIsNotNone(res)
        self.assertGreater(len(res), 0)

    # 4. Short noise does not create a message
    def test_04_short_noise_does_not_create_message(self):
        ended_events = []
        self.detector.on_speech_ended(lambda utt, dur: ended_events.append(utt))

        # Generate a brief 50ms spike (less than minimum_speech_ms = 200ms)
        brief_noise = np.sin(np.linspace(0, 100, 800)).astype(np.float32)  # 50ms at 16kHz
        silence = np.zeros(16000, dtype=np.float32)

        self.detector.process_chunk(brief_noise)
        res = self.detector.process_chunk(silence)

        self.assertIsNone(res, "Brief noise incorrectly generated an utterance")
        self.assertEqual(len(ended_events), 0)

    # 5. Long speech creates one utterance
    def test_05_long_speech_creates_one_utterance(self):
        ended_events = []
        self.detector.on_speech_ended(lambda utt, dur: ended_events.append(utt))

        # Feed continuous speech without pauses
        res1 = self.detector.process_chunk(self.real_audio)
        # End with silence
        res2 = self.detector.process_chunk(np.zeros(16000, dtype=np.float32))
        utterance = res1 if res1 is not None else res2

        self.assertEqual(len(ended_events), 1, f"Expected exactly 1 utterance, got {len(ended_events)}")
        self.assertIsNotNone(utterance)

    # 6. Pause around threshold behaves correctly
    def test_06_pause_around_threshold_behaves_correctly(self):
        # A short pause (< silence_duration_ms) should NOT terminate utterance
        ended_events = []
        self.detector.on_speech_ended(lambda utt, dur: ended_events.append(utt))

        # Speech part 1
        self.detector.process_chunk(self.real_audio[:12000])
        
        # Brief pause 150ms (< 400ms threshold)
        short_pause = np.zeros(2400, dtype=np.float32)
        res1 = self.detector.process_chunk(short_pause)
        self.assertIsNone(res1, "Short pause prematurely ended utterance")

        # Speech part 2 continues
        self.detector.process_chunk(self.real_audio[12000:24000])

        # Long pause 600ms (> 400ms threshold)
        long_pause = np.zeros(9600, dtype=np.float32)
        res2 = self.detector.process_chunk(long_pause)
        self.assertIsNotNone(res2, "Long pause failed to end utterance")
        self.assertEqual(len(ended_events), 1)

    # 7. Maximum utterance duration prevents runaway recording
    def test_07_maximum_utterance_duration_prevents_runaway(self):
        # Set short max utterance limit (1000 ms)
        short_max_cfg = VADConfig(
            speech_start_threshold=0.5,
            silence_duration_ms=2000.0,  # long silence
            minimum_speech_ms=100.0,
            maximum_utterance_ms=800.0   # force cut at 800ms
        )
        detector = SileroVADDetector(config=short_max_cfg)
        ended_events = []
        detector.on_speech_ended(lambda utt, dur: ended_events.append(utt))

        # Feed 2 seconds of continuous real speech
        res = detector.process_chunk(self.real_audio[:32000])

        self.assertIsNotNone(res, "Max utterance limit did not terminate recording")
        self.assertGreater(len(ended_events), 0)

    # 8. Pre-speech buffer works
    def test_08_pre_speech_buffer_works(self):
        self.detector.reset()
        # Feed 300ms of identifiable low audio before speech
        pre_audio = np.ones(4800, dtype=np.float32) * 0.01  # 300ms
        self.detector.process_chunk(pre_audio)

        # Trigger speech
        self.detector.process_chunk(self.real_audio[:16000])
        # Silence to end
        utterance = self.detector.process_chunk(np.zeros(16000, dtype=np.float32))

        self.assertIsNotNone(utterance)
        # Utterance should contain audio from before speech trigger
        self.assertGreater(len(utterance), len(self.real_audio[:16000]))

    # 9. Post-speech padding works
    def test_09_post_speech_padding_works(self):
        self.detector.reset()
        # Feed speech
        self.detector.process_chunk(self.real_audio[:16000])
        
        # Trailing silence
        silence_pad = np.zeros(8000, dtype=np.float32)
        utterance = self.detector.process_chunk(silence_pad)

        self.assertIsNotNone(utterance)
        # Utterance should include trailing buffer
        self.assertGreater(len(utterance), 16000)

    # 10. Existing PTT mode still works
    def test_10_existing_ptt_mode_still_works(self):
        received_by_b = []
        node_b = PeerTransceiver(
            listen_host="127.0.0.1",
            listen_port=65485,
            peer_host="127.0.0.1",
            peer_port=65484,
            node_name="NODE-B",
            tts_engine=MockTTSEngine(),
            on_message_received=lambda pkt, met: received_by_b.append(pkt)
        )

        node_a = PeerTransceiver(
            listen_host="127.0.0.1",
            listen_port=65484,
            peer_host="127.0.0.1",
            peer_port=65485,
            node_name="NODE-A",
            tts_engine=MockTTSEngine()
        )

        try:
            node_b.start()
            node_a.start()
            time.sleep(0.2)

            # Manual PTT transmit
            success, pkt, met = node_a.transmit(
                transcript="PTT mode manual transmission intact.",
                language="en",
                audio_size_bytes=95000
            )
            self.assertTrue(success)

            time.sleep(0.4)
            self.assertEqual(len(received_by_b), 1)
            self.assertEqual(received_by_b[0].payload, "PTT mode manual transmission intact.")
            self.assertEqual(received_by_b[0].sender_id, "NODE-A")

        finally:
            node_a.stop()
            node_b.stop()


if __name__ == "__main__":
    unittest.main()
