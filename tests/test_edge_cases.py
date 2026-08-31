import unittest
import socket
from app.communication.interface import iTantraPacket
from app.communication.tcp_transport import TCPTransport
from app.tts.engine import Pyttsx3TTSEngine

class TestEdgeCases(unittest.TestCase):
    def setUp(self):
        self.tts = Pyttsx3TTSEngine()

    def test_empty_input_tts(self):
        # Empty or whitespace string
        wav_path, latency = self.tts.synthesize("", language="en", play_audio=False)
        self.assertTrue(bool(wav_path))

    def test_long_input_payload(self):
        long_text = "Alert! " * 100
        packet = iTantraPacket(payload=long_text, language="en")
        raw = packet.to_bytes()
        restored = iTantraPacket.from_bytes(raw)
        self.assertEqual(restored.payload, long_text)

    def test_unicode_tamil_packet(self):
        tamil_text = "அவசரக் குழு பிரிவு நான்கிற்கு வரவும்"  # "Emergency team report to sector 4" in Tamil
        packet = iTantraPacket(payload=tamil_text, language="ta")
        raw = packet.to_bytes()
        restored = iTantraPacket.from_bytes(raw)
        self.assertEqual(restored.payload, tamil_text)
        self.assertEqual(restored.language, "ta")

    def test_receiver_unavailable_connection_failure(self):
        # Trying to connect to an unused port
        client = TCPTransport(host="127.0.0.1", port=65499, is_server=False, timeout=1.0)
        packet = iTantraPacket(payload="Hello")
        success, latency, bytes_sent = client.send(packet)
        self.assertFalse(success)
        self.assertEqual(bytes_sent, 0)

    def test_malformed_packet_handling(self):
        # Bad JSON payload handling
        malformed_bytes = b"NOT_A_VALID_JSON_PACKET"
        with self.assertRaises(Exception):
            iTantraPacket.from_bytes(malformed_bytes)

if __name__ == "__main__":
    unittest.main()
