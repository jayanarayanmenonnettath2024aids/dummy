import unittest
import secrets
import struct

from app.communication.packet_v2 import iTantraPacketV2, HMAC_RAW_BYTES, MAX_PACKET_BYTES
from app.communication.stream_decoder import StreamFrameDecoder
from app.security.authenticator import (
    PacketAuthenticator,
    AuthenticationFailedError,
    ReplayAttackError,
    UntrustedPeerError,
    MalformedSecurityTagError
)
from app.security.trust_store import TrustStore

class TestBlock8Protocol(unittest.TestCase):
    """
    Dedicated Block 8 Test Suite for Production Binary Protocol Optimization,
    Raw 32-Byte HMAC-SHA256 Wire Framing, Stream Chunking, and Bounds Validation.
    """

    def setUp(self):
        self.node_a_key = secrets.token_bytes(32)
        self.node_b_key = secrets.token_bytes(32)

        self.trust_store = TrustStore(trust_file=":memory:")
        self.trust_store.pair_device("NODE-ALPHA", self.node_a_key)
        self.trust_store.pair_device("NODE-BRAVO", self.node_b_key)

        self.auth = PacketAuthenticator(trust_store=self.trust_store)

    # 1. Valid HMAC (create -> sign -> serialize -> deserialize -> verify = PASS)
    def test_01_valid_raw_hmac_pipeline(self):
        pkt = iTantraPacketV2(payload="Status normal.", sender_id="NODE-ALPHA", sequence_number=1)
        raw_tag = self.auth.sign_packet(pkt, self.node_a_key, raw_binary=True)
        self.assertEqual(len(raw_tag), 32)
        self.assertIsInstance(raw_tag, bytes)

        wire_bytes = pkt.to_binary()
        unpacked = iTantraPacketV2.from_binary(wire_bytes)
        self.assertEqual(unpacked.payload, "Status normal.")
        self.assertTrue(self.auth.verify_and_authenticate(unpacked))

    # 2. Payload tampering
    def test_02_payload_tampering(self):
        pkt = iTantraPacketV2(payload="Proceed north.", sender_id="NODE-ALPHA", sequence_number=2)
        self.auth.sign_packet(pkt, self.node_a_key, raw_binary=True)
        wire_bytes = bytearray(pkt.to_binary())
        # Tamper payload text in wire bytes
        wire_bytes[-4:] = b"east"
        unpacked = iTantraPacketV2.from_binary(bytes(wire_bytes))
        with self.assertRaises(AuthenticationFailedError):
            self.auth.verify_and_authenticate(unpacked)

    # 3. Priority tampering (NORMAL -> DISTRESS)
    def test_03_priority_tampering(self):
        pkt = iTantraPacketV2(
            payload="Routine report.",
            sender_id="NODE-ALPHA",
            sequence_number=3,
            priority=iTantraPacketV2.PRIORITY_NORMAL,
            message_type=iTantraPacketV2.MESSAGE_TYPE_NORMAL
        )
        self.auth.sign_packet(pkt, self.node_a_key, raw_binary=True)
        # Modify priority byte (offset 4) in binary frame
        wire_bytes = bytearray(pkt.to_binary())
        wire_bytes[4] = iTantraPacketV2.PRIORITY_DISTRESS
        unpacked = iTantraPacketV2.from_binary(bytes(wire_bytes))
        with self.assertRaises(AuthenticationFailedError):
            self.auth.verify_and_authenticate(unpacked)

    # 4. HMAC byte length == 32 raw bytes on wire
    def test_04_hmac_exact_32_raw_bytes(self):
        pkt = iTantraPacketV2(payload="Check tag size.", sender_id="NODE-ALPHA", sequence_number=4)
        self.auth.sign_packet(pkt, self.node_a_key, raw_binary=True)
        raw_wire = pkt.to_binary()
        # Offset 23 is AuthTagLen (uint16)
        auth_len = struct.unpack("!H", raw_wire[23:25])[0]
        self.assertEqual(auth_len, 32)
        # Offset 25 to 57 is the raw 32-byte HMAC tag
        tag_slice = raw_wire[25:57]
        self.assertEqual(len(tag_slice), 32)
        self.assertEqual(tag_slice, pkt.auth_tag)

    # 5. Replay protection
    def test_05_replay_protection(self):
        pkt = iTantraPacketV2(payload="Replay test.", sender_id="NODE-ALPHA", sequence_number=5)
        self.auth.sign_packet(pkt, self.node_a_key, raw_binary=True)
        unpacked = iTantraPacketV2.from_binary(pkt.to_binary())
        self.assertTrue(self.auth.verify_and_authenticate(unpacked))
        # Resending same sequence number must fail
        with self.assertRaises(ReplayAttackError):
            self.auth.verify_and_authenticate(unpacked)

    # 6. Wrong key rejection
    def test_06_wrong_key_rejection(self):
        pkt = iTantraPacketV2(payload="Signed by Bravo, claims Alpha.", sender_id="NODE-ALPHA", sequence_number=6)
        self.auth.sign_packet(pkt, self.node_b_key, raw_binary=True)  # Signed with Node B's key
        unpacked = iTantraPacketV2.from_binary(pkt.to_binary())
        with self.assertRaises(AuthenticationFailedError):
            self.auth.verify_and_authenticate(unpacked)

    # 7. Truncated HMAC
    def test_07_truncated_hmac(self):
        pkt = iTantraPacketV2(payload="Truncated HMAC.", sender_id="NODE-ALPHA", sequence_number=7)
        self.auth.sign_packet(pkt, self.node_a_key, raw_binary=True)
        pkt.auth_tag = pkt.auth_tag[:16]  # Truncate to 16 bytes
        with self.assertRaises(MalformedSecurityTagError):
            self.auth.verify_and_authenticate(pkt)

    # 8. Corrupted HMAC (1 byte modified)
    def test_08_corrupted_hmac(self):
        pkt = iTantraPacketV2(payload="Corrupted HMAC.", sender_id="NODE-ALPHA", sequence_number=8)
        self.auth.sign_packet(pkt, self.node_a_key, raw_binary=True)
        tag_bytes = bytearray(pkt.auth_tag)
        tag_bytes[0] ^= 0xFF  # Flip bits of first byte
        pkt.auth_tag = bytes(tag_bytes)
        with self.assertRaises(AuthenticationFailedError):
            self.auth.verify_and_authenticate(pkt)

    # 9. Stream framing: Single Packet A
    def test_09_stream_framing_single_packet(self):
        decoder = StreamFrameDecoder()
        pkt = iTantraPacketV2(payload="Single frame.", sender_id="NODE-ALPHA", sequence_number=9)
        raw = pkt.to_binary()
        framed = struct.pack("!I", len(raw)) + raw
        packets = decoder.feed_bytes(framed)
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0].payload, "Single frame.")
        self.assertEqual(decoder.buffer_size, 0)

    # 10. Stream framing: Coalesced Packet A + Packet B in single chunk
    def test_10_stream_framing_coalesced_packets(self):
        decoder = StreamFrameDecoder()
        pkt_a = iTantraPacketV2(payload="Frame A", sender_id="NODE-ALPHA", sequence_number=10)
        pkt_b = iTantraPacketV2(payload="Frame B", sender_id="NODE-ALPHA", sequence_number=11)
        raw_a = pkt_a.to_binary()
        raw_b = pkt_b.to_binary()
        framed_a = struct.pack("!I", len(raw_a)) + raw_a
        framed_b = struct.pack("!I", len(raw_b)) + raw_b
        
        # Feed combined chunk
        packets = decoder.feed_bytes(framed_a + framed_b)
        self.assertEqual(len(packets), 2)
        self.assertEqual(packets[0].payload, "Frame A")
        self.assertEqual(packets[1].payload, "Frame B")
        self.assertEqual(decoder.buffer_size, 0)

    # 11. Stream framing: Fragmented Packet A (First half + Second half)
    def test_11_stream_framing_fragmented_packet(self):
        decoder = StreamFrameDecoder()
        pkt = iTantraPacketV2(payload="Fragmented tactical voice.", sender_id="NODE-ALPHA", sequence_number=12)
        raw = pkt.to_binary()
        framed = struct.pack("!I", len(raw)) + raw
        split_idx = len(framed) // 2

        # Feed first half
        packets_part1 = decoder.feed_bytes(framed[:split_idx])
        self.assertEqual(len(packets_part1), 0)
        self.assertGreater(decoder.buffer_size, 0)

        # Feed second half
        packets_part2 = decoder.feed_bytes(framed[split_idx:])
        self.assertEqual(len(packets_part2), 1)
        self.assertEqual(packets_part2[0].payload, "Fragmented tactical voice.")
        self.assertEqual(decoder.buffer_size, 0)

    # 12. Stream framing: Packet A + Partial Packet B
    def test_12_stream_framing_packet_plus_partial(self):
        decoder = StreamFrameDecoder()
        pkt_a = iTantraPacketV2(payload="Frame A complete", sender_id="NODE-ALPHA", sequence_number=13)
        pkt_b = iTantraPacketV2(payload="Frame B trailing", sender_id="NODE-ALPHA", sequence_number=14)
        raw_a = pkt_a.to_binary()
        raw_b = pkt_b.to_binary()
        framed_a = struct.pack("!I", len(raw_a)) + raw_a
        framed_b = struct.pack("!I", len(raw_b)) + raw_b

        # Feed Frame A + 10 bytes of Frame B
        packets = decoder.feed_bytes(framed_a + framed_b[:10])
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0].payload, "Frame A complete")
        self.assertEqual(decoder.buffer_size, 10)

        # Feed remainder of Frame B
        packets_b = decoder.feed_bytes(framed_b[10:])
        self.assertEqual(len(packets_b), 1)
        self.assertEqual(packets_b[0].payload, "Frame B trailing")
        self.assertEqual(decoder.buffer_size, 0)

    # 13. Stream framing: Oversized frame length rejection
    def test_13_stream_framing_oversized_rejection(self):
        decoder = StreamFrameDecoder(max_frame_bytes=MAX_PACKET_BYTES)
        # Prefix claiming 1 MB frame
        bad_frame = struct.pack("!I", 1024 * 1024) + b"\x00" * 20
        with self.assertRaises(ValueError):
            decoder.feed_bytes(bad_frame)

if __name__ == "__main__":
    unittest.main()
