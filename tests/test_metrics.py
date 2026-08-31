import unittest
from app.metrics.metrics import PipelineMetrics

class TestMetrics(unittest.TestCase):
    def test_metrics_calculation(self):
        # 4 seconds of 16kHz 16-bit audio = 4 * 16000 * 2 = 128,000 bytes
        audio_bytes = 128000
        text_bytes = 28
        total_packet_bytes = 180

        metrics = PipelineMetrics(
            audio_size_bytes=audio_bytes,
            text_payload_bytes=text_bytes,
            total_packet_bytes=total_packet_bytes,
            stt_latency_ms=420.0,
            network_latency_ms=15.0,
            tts_latency_ms=310.0,
            end_to_end_latency_ms=745.0,
            transcript="Meet me at checkpoint four.",
            language="en"
        )

        self.assertAlmostEqual(metrics.reduction_percentage, ((128000 - 28) / 128000) * 100.0, places=2)
        self.assertAlmostEqual(metrics.packet_reduction_percentage, ((128000 - 180) / 128000) * 100.0, places=2)
        self.assertGreater(metrics.reduction_percentage, 99.0)
        self.assertGreater(metrics.packet_reduction_percentage, 99.0)

if __name__ == "__main__":
    unittest.main()
