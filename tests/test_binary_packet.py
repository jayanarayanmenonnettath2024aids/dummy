import unittest
import time
from app.communication.packet_v2 import iTantraPacketV2, MAGIC_HEADER, PROTOCOL_VERSION_V2

class TestBinaryPacketV2(unittest.TestCase):
    """
    Test suite for Block 3: Compact Binary Packet Protocol (iTantraPacketV2)
    Covers the 13 required test specifications.
    """

    def setUp(self):
        self.sample_en = "Meet me at checkpoint 4."
        self.sample_ta = "அவசரக் குழு பிரிவு நான்கிற்கு வரவும்."
        self.sample_unicode = "Alpha-1 🎯 Radar Contact: Bearing 045° | Elev +12° 📡"

    # 1. Binary serialization
    def test_01_binary_serialization(self):
        pkt = iTantraPacketV2(
            payload=self.sample_en,
            language="en",
            sender_id="NODE-ALPHA",
            session_id="ses12345",
            sequence_number=42,
            audio_size_bytes=64000
        )
        raw_bin = pkt.to_binary()

        self.assertIsInstance(raw_bin, bytes)
        self.assertTrue(raw_bin.startswith(MAGIC_HEADER))
        self.assertEqual(raw_bin[2], PROTOCOL_VERSION_V2)
        self.assertGreater(len(raw_bin), 25)

    # 2. Binary deserialization
    def test_02_binary_deserialization(self):
        pkt = iTantraPacketV2(
            payload=self.sample_en,
            language="en",
            sender_id="NODE-BRAVO",
            session_id="ses99999",
            sequence_number=101,
            audio_size_bytes=32000
        )
        raw_bin = pkt.to_binary()
        reconstructed = iTantraPacketV2.from_binary(raw_bin)

        self.assertEqual(reconstructed.payload, self.sample_en)
        self.assertEqual(reconstructed.sender_id, "NODE-BRAVO")
        self.assertEqual(reconstructed.session_id, "ses99999")
        self.assertEqual(reconstructed.sequence_number, 101)
        self.assertEqual(reconstructed.language, "en")
        self.assertEqual(reconstructed.audio_size_bytes, 32000)

    # 3. Round-trip equality
    def test_03_round_trip_equality(self):
        original = iTantraPacketV2(
            payload="All units stand by for extraction vector.",
            language="en",
            sender_id="COMMAND-HQ",
            session_id="alpha777",
            sequence_number=7,
            message_type=iTantraPacketV2.MESSAGE_TYPE_VOICE,
            priority=iTantraPacketV2.PRIORITY_HIGH,
            audio_size_bytes=48000,
            timestamp=1725300000.12345,
            auth_tag="AUTH_SIGNATURE_MOCK"
        )
        binary_bytes = original.to_binary()
        decoded = iTantraPacketV2.from_binary(binary_bytes)

        self.assertEqual(decoded.payload, original.payload)
        self.assertEqual(decoded.language, original.language)
        self.assertEqual(decoded.sender_id, original.sender_id)
        self.assertEqual(decoded.session_id, original.session_id)
        self.assertEqual(decoded.sequence_number, original.sequence_number)
        self.assertEqual(decoded.message_type, original.message_type)
        self.assertEqual(decoded.priority, original.priority)
        self.assertEqual(decoded.audio_size_bytes, original.audio_size_bytes)
        self.assertAlmostEqual(decoded.timestamp, original.timestamp, places=4)
        self.assertEqual(decoded.auth_tag, original.auth_tag)

    # 4. Unicode support
    def test_04_unicode_support(self):
        pkt = iTantraPacketV2(
            payload=self.sample_unicode,
            language="en",
            sender_id="RECON-🛰️"
        )
        binary_bytes = pkt.to_binary()
        decoded = iTantraPacketV2.from_binary(binary_bytes)

        self.assertEqual(decoded.payload, self.sample_unicode)
        self.assertEqual(decoded.sender_id, "RECON-🛰️")

    # 5. Tamil Unicode support
    def test_05_tamil_support(self):
        pkt = iTantraPacketV2(
            payload=self.sample_ta,
            language="ta",
            sender_id="முனை-1"
        )
        binary_bytes = pkt.to_binary()
        decoded = iTantraPacketV2.from_binary(binary_bytes)

        self.assertEqual(decoded.payload, self.sample_ta)
        self.assertEqual(decoded.language, "ta")
        self.assertEqual(decoded.sender_id, "முனை-1")

    # 6. English support
    def test_06_english_support(self):
        pkt = iTantraPacketV2(
            payload="Radio check 1 2 3, loud and clear.",
            language="en"
        )
        binary_bytes = pkt.to_binary()
        decoded = iTantraPacketV2.from_binary(binary_bytes)

        self.assertEqual(decoded.payload, "Radio check 1 2 3, loud and clear.")
        self.assertEqual(decoded.language, "en")

    # 7. Empty payload handling
    def test_07_empty_payload_handling(self):
        pkt = iTantraPacketV2(
            payload="",
            language="en",
            message_type=iTantraPacketV2.MESSAGE_TYPE_HEARTBEAT
        )
        binary_bytes = pkt.to_binary()
        decoded = iTantraPacketV2.from_binary(binary_bytes)

        self.assertEqual(decoded.payload, "")
        self.assertEqual(decoded.message_type, iTantraPacketV2.MESSAGE_TYPE_HEARTBEAT)

    # 8. Maximum payload handling (large buffers up to 64KB boundary)
    def test_08_maximum_payload_handling(self):
        large_payload = "A" * 60000  # 60 KB string
        pkt = iTantraPacketV2(
            payload=large_payload,
            language="en"
        )
        binary_bytes = pkt.to_binary()
        decoded = iTantraPacketV2.from_binary(binary_bytes)

        self.assertEqual(len(decoded.payload), 60000)
        self.assertEqual(decoded.payload, large_payload)

    # 9. Invalid version rejection
    def test_09_invalid_version_rejection(self):
        pkt = iTantraPacketV2(payload="test")
        raw_bytes = bytearray(pkt.to_binary())
        # Corrupt version byte (byte 2) to 99
        raw_bytes[2] = 99

        with self.assertRaises(ValueError) as ctx:
            iTantraPacketV2.from_binary(bytes(raw_bytes))
        self.assertIn("Unsupported binary protocol version", str(ctx.exception))

    # 10. Invalid length rejection
    def test_10_invalid_length_rejection(self):
        # Short packet below minimum header (20 bytes)
        with self.assertRaises(ValueError) as ctx:
            iTantraPacketV2.from_binary(b"IT\x02\x01\x00en\x00\x00\x00\x01\x00\x00")
        self.assertIn("Packet too short", str(ctx.exception))

    # 11. Truncated packet handling
    def test_11_truncated_packet_handling(self):
        pkt = iTantraPacketV2(payload="Payload that will be truncated.")
        raw_bytes = pkt.to_binary()
        # Truncate last 10 bytes of payload
        truncated = raw_bytes[:-10]

        with self.assertRaises(ValueError) as ctx:
            iTantraPacketV2.from_binary(truncated)
        self.assertIn("Truncated packet", str(ctx.exception))

    # 12. Sequence number integrity
    def test_12_sequence_number_integrity(self):
        seq_values = [0, 1, 255, 65535, 4294967295]
        for seq in seq_values:
            pkt = iTantraPacketV2(payload=f"Seq test {seq}", sequence_number=seq)
            decoded = iTantraPacketV2.from_binary(pkt.to_binary())
            self.assertEqual(decoded.sequence_number, seq)

    # 13. Multiple messages stream serialization
    def test_13_multiple_messages_stream(self):
        messages = [
            ("Alpha acknowledging orders.", "en", 1),
            ("Bravo relocating to point Bravo-2.", "en", 2),
            ("பாதுகாப்பு பகுதி உறுதிப்படுத்தப்பட்டது.", "ta", 3)
        ]

        stream_bytes = bytearray()
        for text, lang, seq in messages:
            p = iTantraPacketV2(payload=text, language=lang, sequence_number=seq)
            bin_data = p.to_binary()
            # Prefix with 4-byte length framing (as done in TCPTransport)
            import struct
            stream_bytes.extend(struct.pack("!I", len(bin_data)))
            stream_bytes.extend(bin_data)

        # Deserialize stream
        offset = 0
        deserialized = []
        import struct
        while offset < len(stream_bytes):
            frame_len = struct.unpack("!I", stream_bytes[offset : offset + 4])[0]
            offset += 4
            frame_data = stream_bytes[offset : offset + frame_len]
            offset += frame_len
            pkt = iTantraPacketV2.from_binary(bytes(frame_data))
            deserialized.append((pkt.payload, pkt.language, pkt.sequence_number))

        self.assertEqual(len(deserialized), 3)
        for i in range(3):
            self.assertEqual(deserialized[i], messages[i])


if __name__ == "__main__":
    unittest.main()
