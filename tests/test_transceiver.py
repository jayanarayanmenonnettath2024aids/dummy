import unittest
import time
from app.communication.peer_transceiver import PeerTransceiver
from app.communication.interface import iTantraPacket
from app.metrics.metrics import PipelineMetrics
from app.tts.engine import BaseTTSEngine

class MockTTSEngine(BaseTTSEngine):
    """Mock TTS for fast unit testing without audio playback."""
    def synthesize(self, text: str, language: str = "en", output_path=None, play_audio=False):
        return "mock_output.wav", 0.05

class TestPeerTransceiver(unittest.TestCase):
    def test_bidirectional_transceiver_loop(self):
        received_by_a = []
        received_by_b = []

        node_a = PeerTransceiver(
            listen_host="127.0.0.1",
            listen_port=65460,
            peer_host="127.0.0.1",
            peer_port=65461,
            node_name="NODE-A",
            tts_engine=MockTTSEngine(),
            on_message_received=lambda pkt, met: received_by_a.append(pkt)
        )

        node_b = PeerTransceiver(
            listen_host="127.0.0.1",
            listen_port=65461,
            peer_host="127.0.0.1",
            peer_port=65460,
            node_name="NODE-B",
            tts_engine=MockTTSEngine(),
            on_message_received=lambda pkt, met: received_by_b.append(pkt)
        )

        try:
            node_a.start()
            node_b.start()
            time.sleep(0.3)  # Wait for sockets to bind

            # 1. Node A transmits to Node B
            success_a, pkt_a, met_a = node_a.transmit(
                transcript="Checkpoint Alpha reached.",
                language="en",
                audio_size_bytes=100000
            )
            self.assertTrue(success_a)

            # Wait for Node B to receive
            time.sleep(0.5)
            self.assertEqual(len(received_by_b), 1)
            self.assertEqual(received_by_b[0].payload, "Checkpoint Alpha reached.")
            self.assertEqual(received_by_b[0].sender_id, "NODE-A")

            # 2. Node B replies to Node A
            success_b, pkt_b, met_b = node_b.transmit(
                transcript="Copy that Alpha, proceed to Bravo.",
                language="en",
                audio_size_bytes=120000
            )
            self.assertTrue(success_b)

            # Wait for Node A to receive
            time.sleep(0.5)
            self.assertEqual(len(received_by_a), 1)
            self.assertEqual(received_by_a[0].payload, "Copy that Alpha, proceed to Bravo.")
            self.assertEqual(received_by_a[0].sender_id, "NODE-B")

        finally:
            node_a.stop()
            node_b.stop()

if __name__ == "__main__":
    unittest.main()
