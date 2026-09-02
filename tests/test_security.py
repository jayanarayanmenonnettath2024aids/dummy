import unittest
import time
import secrets
import struct
import socket

from app.communication.packet_v2 import iTantraPacketV2, MAX_PACKET_SIZE, MAGIC_HEADER, PROTOCOL_VERSION_V2
from app.communication.tcp_transport import TCPTransport
from app.communication.peer_transceiver import PeerTransceiver
from app.security.identity import NodeIdentity
from app.security.trust_store import TrustStore
from app.security.authenticator import (
    PacketAuthenticator,
    SecurityError,
    AuthenticationFailedError,
    ReplayAttackError,
    UntrustedPeerError,
    MalformedSecurityTagError
)
from app.discovery.mdns_discovery import MdnsDeviceDiscovery
from app.vad.stream_processor import VADStreamProcessor
from app.vad.config import VADConfig

class TestBlock7Security(unittest.TestCase):
    """
    Comprehensive Block 7 Test Suite covering all 30 security, authentication,
    replay protection, bounds defense, and connection resilience requirements.
    """

    def setUp(self):
        self.node_a_key = secrets.token_bytes(32)
        self.node_b_key = secrets.token_bytes(32)

        self.trust_store = TrustStore(trust_file=":memory:")
        self.trust_store.pair_device("NODE-A", self.node_a_key, name="Node Alpha")
        self.trust_store.pair_device("NODE-B", self.node_b_key, name="Node Bravo")

        self.auth = PacketAuthenticator(trust_store=self.trust_store)

    # 1. Valid authenticated packet
    def test_01_valid_authenticated_packet(self):
        pkt = iTantraPacketV2(payload="Status secure.", sender_id="NODE-A", sequence_number=1)
        self.auth.sign_packet(pkt, self.node_a_key)
        self.assertTrue(self.auth.verify_and_authenticate(pkt))

    # 2. Modified text
    def test_02_modified_text(self):
        pkt = iTantraPacketV2(payload="Original text.", sender_id="NODE-A", sequence_number=2)
        self.auth.sign_packet(pkt, self.node_a_key)
        pkt.payload = "Modified text."
        with self.assertRaises(AuthenticationFailedError):
            self.auth.verify_and_authenticate(pkt)

    # 3. Modified language
    def test_03_modified_language(self):
        pkt = iTantraPacketV2(payload="Hello", language="en", sender_id="NODE-A", sequence_number=3)
        self.auth.sign_packet(pkt, self.node_a_key)
        pkt.language = "hi"
        with self.assertRaises(AuthenticationFailedError):
            self.auth.verify_and_authenticate(pkt)

    # 4. Modified priority
    def test_04_modified_priority(self):
        pkt = iTantraPacketV2(payload="Routine msg", priority=iTantraPacketV2.PRIORITY_NORMAL, sender_id="NODE-A", sequence_number=4)
        self.auth.sign_packet(pkt, self.node_a_key)
        pkt.priority = iTantraPacketV2.PRIORITY_DISTRESS
        with self.assertRaises(AuthenticationFailedError):
            self.auth.verify_and_authenticate(pkt)

    # 5. Modified message type
    def test_05_modified_message_type(self):
        pkt = iTantraPacketV2(payload="Routine msg", message_type=iTantraPacketV2.MESSAGE_TYPE_NORMAL, sender_id="NODE-A", sequence_number=5)
        self.auth.sign_packet(pkt, self.node_a_key)
        pkt.message_type = iTantraPacketV2.MESSAGE_TYPE_ALERT
        with self.assertRaises(AuthenticationFailedError):
            self.auth.verify_and_authenticate(pkt)

    # 6. Modified sequence number
    def test_06_modified_sequence_number(self):
        pkt = iTantraPacketV2(payload="Msg", sender_id="NODE-A", sequence_number=6)
        self.auth.sign_packet(pkt, self.node_a_key)
        pkt.sequence_number = 999
        with self.assertRaises(AuthenticationFailedError):
            self.auth.verify_and_authenticate(pkt)

    # 7. Modified timestamp
    def test_07_modified_timestamp(self):
        pkt = iTantraPacketV2(payload="Msg", sender_id="NODE-A", sequence_number=7, timestamp=time.time())
        self.auth.sign_packet(pkt, self.node_a_key)
        pkt.timestamp = pkt.timestamp - 100.0
        with self.assertRaises(AuthenticationFailedError):
            self.auth.verify_and_authenticate(pkt)

    # 8. Invalid authentication tag
    def test_08_invalid_auth_tag(self):
        pkt = iTantraPacketV2(payload="Msg", sender_id="NODE-A", sequence_number=8, auth_tag="00" * 32)
        with self.assertRaises(AuthenticationFailedError):
            self.auth.verify_and_authenticate(pkt)

    # 9. Replay attack
    def test_09_replay_attack(self):
        pkt = iTantraPacketV2(payload="Msg", sender_id="NODE-A", sequence_number=9)
        self.auth.sign_packet(pkt, self.node_a_key)
        self.assertTrue(self.auth.verify_and_authenticate(pkt))
        with self.assertRaises(ReplayAttackError):
            self.auth.verify_and_authenticate(pkt)

    # 10. Duplicate packet
    def test_10_duplicate_packet(self):
        pkt = iTantraPacketV2(payload="Duplicate msg", sender_id="NODE-A", sequence_number=10)
        self.auth.sign_packet(pkt, self.node_a_key)
        self.assertTrue(self.auth.verify_and_authenticate(pkt))
        with self.assertRaises(ReplayAttackError):
            self.auth.verify_and_authenticate(pkt)

    # 11. Old packet (expired timestamp)
    def test_11_old_packet(self):
        old_time = time.time() - 45.0  # 45 seconds old > 30s limit
        pkt = iTantraPacketV2(payload="Old msg", sender_id="NODE-A", sequence_number=11, timestamp=old_time)
        self.auth.sign_packet(pkt, self.node_a_key)
        with self.assertRaises(ReplayAttackError):
            self.auth.verify_and_authenticate(pkt)

    # 12. Unknown device
    def test_12_unknown_device(self):
        pkt = iTantraPacketV2(payload="Msg", sender_id="NODE-UNKNOWN", sequence_number=12)
        self.auth.sign_packet(pkt, secrets.token_bytes(32))
        with self.assertRaises(UntrustedPeerError):
            self.auth.verify_and_authenticate(pkt)

    # 13. Untrusted device (unpaired status)
    def test_13_untrusted_device(self):
        self.trust_store.set_trust_status("NODE-ROGUE", TrustStore.STATUS_UNPAIRED)
        pkt = iTantraPacketV2(payload="Msg", sender_id="NODE-ROGUE", sequence_number=13)
        self.auth.sign_packet(pkt, secrets.token_bytes(32))
        with self.assertRaises(UntrustedPeerError):
            self.auth.verify_and_authenticate(pkt)

    # 14. Malformed packet (corrupt magic)
    def test_14_malformed_packet_magic(self):
        bad_bytes = b"XX\x02" + b"\x00" * 30
        with self.assertRaises(ValueError):
            iTantraPacketV2.from_binary(bad_bytes)

    # 15. Truncated packet
    def test_15_truncated_packet(self):
        truncated = b"IT\x02\x01\x00"  # only 5 bytes
        with self.assertRaises(ValueError):
            iTantraPacketV2.from_binary(truncated)

    # 16. Oversized packet
    def test_16_oversized_packet(self):
        oversized = b"IT\x02" + b"\x00" * (MAX_PACKET_SIZE + 10)
        with self.assertRaises(ValueError):
            iTantraPacketV2.from_binary(oversized)

    # 17. Invalid UTF-8
    def test_17_invalid_utf8(self):
        # Construct header + invalid UTF-8 bytes in payload
        header = struct.pack("!2sBBB2sIdIH", MAGIC_HEADER, PROTOCOL_VERSION_V2, 1, 0, b"en", 1, time.time(), 0, 0)
        body = bytearray()
        body.append(1)  # sender len
        body.extend(b"A")
        body.append(1)  # session len
        body.extend(b"S")
        body.extend(struct.pack("!H", 2))
        body.extend(b"\xFF\xFE")  # invalid utf-8
        with self.assertRaises(ValueError):
            iTantraPacketV2.from_binary(header + bytes(body))

    # 18. Invalid message type
    def test_18_invalid_message_type(self):
        header = struct.pack("!2sBBB2sIdIH", MAGIC_HEADER, PROTOCOL_VERSION_V2, 99, 0, b"en", 1, time.time(), 0, 0)
        with self.assertRaises(ValueError):
            iTantraPacketV2.from_binary(header + b"\x00" * 10)

    # 19. Invalid priority
    def test_19_invalid_priority(self):
        header = struct.pack("!2sBBB2sIdIH", MAGIC_HEADER, PROTOCOL_VERSION_V2, 1, 99, b"en", 1, time.time(), 0, 0)
        with self.assertRaises(ValueError):
            iTantraPacketV2.from_binary(header + b"\x00" * 10)

    # 20. Invalid language
    def test_20_invalid_language(self):
        pkt = iTantraPacketV2(payload="Test", language="english", sender_id="NODE-A", sequence_number=20)
        self.assertEqual(len(pkt.language), 2)

    # 21. Invalid payload length (claims 100 bytes, supplies 2)
    def test_21_invalid_payload_length(self):
        header = struct.pack("!2sBBB2sIdIH", MAGIC_HEADER, PROTOCOL_VERSION_V2, 1, 0, b"en", 1, time.time(), 0, 0)
        body = bytearray()
        body.append(1)
        body.extend(b"A")
        body.append(1)
        body.extend(b"S")
        body.extend(struct.pack("!H", 100))  # Claims 100 bytes
        body.extend(b"ab")                   # Only provides 2 bytes
        with self.assertRaises(ValueError):
            iTantraPacketV2.from_binary(header + bytes(body))

    # 22. Connection timeout
    def test_22_connection_timeout(self):
        client = TCPTransport(host="127.0.0.1", port=65498, is_server=False, timeout=0.1)
        pkt = iTantraPacketV2(payload="Timeout test")
        success, lat, sent = client.send(pkt)
        self.assertFalse(success)

    # 23. Peer disconnect (clean failure)
    def test_23_peer_disconnect(self):
        server = TCPTransport(host="127.0.0.1", port=65497, is_server=True, timeout=0.5)
        pkt, lat, rec = server.receive(timeout=0.1)
        self.assertIsNone(pkt)
        server.close()

    # 24. Peer restart (clean socket reopen)
    def test_24_peer_restart(self):
        tx = PeerTransceiver(listen_port=65496, node_name="NODE-RESTART")
        tx.start()
        self.assertTrue(tx.is_running)
        tx.stop()
        self.assertFalse(tx.is_running)
        # Restart
        tx.start()
        self.assertTrue(tx.is_running)
        tx.stop()

    # 25. Discovery + authentication integration
    def test_25_discovery_and_authentication(self):
        disc = MdnsDeviceDiscovery(node_id="NODE-DISC", device_name="Disc Node", tcp_port=65432)
        status = self.trust_store.get_device_status("NODE-DISC")
        self.assertEqual(status, TrustStore.STATUS_UNPAIRED)
        self.assertFalse(self.trust_store.is_trusted("NODE-DISC"))
        # Pair
        self.trust_store.pair_device("NODE-DISC", secrets.token_bytes(32))
        self.assertTrue(self.trust_store.is_trusted("NODE-DISC"))

    # 26. Alert packet security
    def test_26_alert_packet_security(self):
        pkt = iTantraPacketV2(
            payload="ALERT: Perimeter breached!",
            message_type=iTantraPacketV2.MESSAGE_TYPE_ALERT,
            priority=iTantraPacketV2.PRIORITY_ALERT,
            sender_id="NODE-A",
            sequence_number=26
        )
        self.auth.sign_packet(pkt, self.node_a_key)
        self.assertTrue(self.auth.verify_and_authenticate(pkt))

    # 27. Distress packet security
    def test_27_distress_packet_security(self):
        pkt = iTantraPacketV2(
            payload="DISTRESS: Officer under fire!",
            message_type=iTantraPacketV2.MESSAGE_TYPE_DISTRESS,
            priority=iTantraPacketV2.PRIORITY_DISTRESS,
            sender_id="NODE-A",
            sequence_number=27
        )
        self.auth.sign_packet(pkt, self.node_a_key)
        self.assertTrue(self.auth.verify_and_authenticate(pkt))

    # 28. PTT communication with security
    def test_28_ptt_communication_security(self):
        proc = VADStreamProcessor(config=VADConfig())
        proc.set_mode("ptt")
        self.assertEqual(proc.mode, "ptt")
        pkt = iTantraPacketV2(payload="PTT Tactical voice", sender_id="NODE-A", sequence_number=28)
        self.auth.sign_packet(pkt, self.node_a_key)
        self.assertTrue(self.auth.verify_and_authenticate(pkt))

    # 29. Voice/VAD communication with security
    def test_29_voice_vad_communication_security(self):
        proc = VADStreamProcessor(config=VADConfig())
        proc.set_mode("voice")
        self.assertEqual(proc.mode, "voice")
        proc.stop_live_mic()
        pkt = iTantraPacketV2(payload="Hands-free VAD voice", sender_id="NODE-A", sequence_number=29)
        self.auth.sign_packet(pkt, self.node_a_key)
        self.assertTrue(self.auth.verify_and_authenticate(pkt))

    # 30. Existing binary packet compatibility
    def test_30_existing_binary_packet_compatibility(self):
        raw_v2 = iTantraPacketV2(payload="Compatibility payload", sender_id="NODE-A", sequence_number=30).to_binary()
        unpacked = iTantraPacketV2.from_binary(raw_v2)
        self.assertEqual(unpacked.payload, "Compatibility payload")
        self.assertEqual(unpacked.sender_id, "NODE-A")

if __name__ == "__main__":
    unittest.main()
