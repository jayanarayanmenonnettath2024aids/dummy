import unittest
import os
import time
from typing import List

from app.stt.engine import WhisperSTTEngine
from app.tts.engine import BaseTTSEngine
from app.communication.interface import iTantraPacket
from app.communication.packet_v2 import iTantraPacketV2
from app.communication.peer_transceiver import PeerTransceiver

class MockTTSEngine(BaseTTSEngine):
    def __init__(self):
        self.synthesized_texts: List[str] = []

    def synthesize(self, text: str, language: str = "en", output_path=None, play_audio=False):
        self.synthesized_texts.append(text)
        return "mock_e2e.wav", 0.01


class TestBinaryEndToEnd(unittest.TestCase):
    """
    Integration test verifying the end-to-end pipeline:
    Speech Input -> STT -> Binary Packet (iTantraPacketV2) -> TCP Transport -> Binary Decode -> TTS Synthesis.
    """

    @classmethod
    def setUpClass(cls):
        cls.stt_engine = WhisperSTTEngine(model_name="openai/whisper-tiny")
        cls.sample_wav = "samples/checkpoint_en.wav"

    def test_e2e_speech_to_binary_packet_to_tts(self):
        mock_tts_node_b = MockTTSEngine()
        received_packets_b = []

        def on_msg_recv_b(packet, metrics):
            received_packets_b.append(packet)

        # Node B (Receiver on port 65492)
        node_b = PeerTransceiver(
            listen_host="127.0.0.1",
            listen_port=65492,
            peer_host="127.0.0.1",
            peer_port=65491,
            node_name="NODE-BRAVO-BIN",
            tts_engine=mock_tts_node_b,
            on_message_received=on_msg_recv_b,
            transport_format="binary"
        )

        # Node A (Transmitter on port 65491)
        node_a = PeerTransceiver(
            listen_host="127.0.0.1",
            listen_port=65491,
            peer_host="127.0.0.1",
            peer_port=65492,
            node_name="NODE-ALPHA-BIN",
            transport_format="binary"
        )

        try:
            node_b.start()
            node_a.start()
            time.sleep(0.2)

            # 1. Step 1: STT Speech-to-Text Transcription
            audio_bytes_size = os.path.getsize(self.sample_wav)
            t1_start = time.time()
            transcript, stt_latency = self.stt_engine.transcribe(self.sample_wav, language="en")
            t2_finish = time.time()

            self.assertIsNotNone(transcript)
            self.assertIn("checkpoint", transcript.lower())
            print(f"\n[+] E2E STT Transcribed: '{transcript}' (in {stt_latency*1000:.1f}ms)")

            # 2. Step 2: Transmit via Binary Packet over TCP
            success, sent_pkt, metrics = node_a.transmit(
                transcript=transcript,
                language="en",
                audio_size_bytes=audio_bytes_size,
                t1_start=t1_start,
                t2_stt=t2_finish
            )

            self.assertTrue(success, "Binary packet transmission failed")
            self.assertIsNotNone(metrics)
            print(f"[+] E2E Binary Frame Sent: {metrics.total_packet_bytes} bytes (Payload: {metrics.text_payload_bytes} bytes)")
            
            # Binary total packet bytes should be compact (~70-80 bytes), not ~270 bytes JSON
            self.assertLess(metrics.total_packet_bytes, 120, "Packet size is too large for compact binary protocol")

            # 3. Step 3: Wait for Node B to receive and decode
            start_wait = time.time()
            while time.time() - start_wait < 5.0 and len(received_packets_b) == 0:
                time.sleep(0.1)

            self.assertEqual(len(received_packets_b), 1, "Node B did not receive binary packet")
            recv_pkt = received_packets_b[0]
            self.assertEqual(recv_pkt.payload, transcript)
            self.assertEqual(recv_pkt.sender_id, "NODE-ALPHA-BIN")
            self.assertEqual(recv_pkt.language, "en")

            # 4. Step 4: Verify Node B TTS was triggered with transcribed text
            self.assertEqual(len(mock_tts_node_b.synthesized_texts), 1)
            self.assertEqual(mock_tts_node_b.synthesized_texts[0], transcript)
            print(f"[+] E2E TTS Successfully Reconstructed: '{mock_tts_node_b.synthesized_texts[0]}'")

        finally:
            node_a.stop()
            node_b.stop()


if __name__ == "__main__":
    unittest.main()
