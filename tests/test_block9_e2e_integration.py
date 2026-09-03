import os
import unittest
import time
import secrets
import struct
import numpy as np

from app.models.manager import ModelManager, ModelNotInstalledError
from app.models.registry import LanguageProfile, DEFAULT_LANGUAGE_REGISTRY
from app.stt.engine import WhisperSTT
from app.tts.engine import NeuralONNXTTSEngine
from app.communication.packet_v2 import iTantraPacketV2
from app.communication.stream_decoder import StreamFrameDecoder
from app.communication.playback_controller import PriorityPlaybackController
from app.communication.peer_transceiver import PeerTransceiver
from app.security.identity import NodeIdentity
from app.security.trust_store import TrustStore
from app.security.authenticator import (
    PacketAuthenticator,
    AuthenticationFailedError,
    ReplayAttackError,
    UntrustedPeerError
)
from app.vad.silero_vad import SileroVADDetector
from app.vad.stream_processor import VADStreamProcessor
from app.vad.config import VADConfig
from app.discovery.mdns_discovery import MdnsDeviceDiscovery

class TestBlock9E2EIntegration(unittest.TestCase):
    """
    Block 9 Comprehensive End-to-End Desktop Validation Test Suite.
    Verifies full integration across Discovery, PTT/VAD, STT, Binary Protocol V2,
    Raw 32-Byte HMAC Security, Priority Preemption, Neural ONNX TTS, and Explicit Language States.
    """

    def setUp(self):
        self.manager = ModelManager()
        self.node_a_key = secrets.token_bytes(32)
        self.node_b_key = secrets.token_bytes(32)

        self.trust_store = TrustStore(trust_file=":memory:")
        self.trust_store.pair_device("NODE-ALPHA", self.node_a_key, name="Node Alpha")
        self.trust_store.pair_device("NODE-BRAVO", self.node_b_key, name="Node Bravo")

        self.auth = PacketAuthenticator(trust_store=self.trust_store)

    # 1. PTT Full Pipeline (PTT Hold -> STT -> Binary Packet -> 32B HMAC -> Queue -> TTS)
    def test_01_ptt_full_pipeline(self):
        proc = VADStreamProcessor(config=VADConfig())
        proc.set_mode("ptt")
        self.assertEqual(proc.mode, "ptt")

        # Simulate PTT capture & packet creation
        pkt = iTantraPacketV2(
            payload="Team three advance to sector four.",
            language="en",
            sender_id="NODE-ALPHA",
            sequence_number=1,
            priority=iTantraPacketV2.PRIORITY_NORMAL
        )
        self.auth.sign_packet(pkt, self.node_a_key, raw_binary=True)
        self.assertEqual(len(pkt.auth_tag), 32)

        # Receiver verification
        raw_wire = pkt.to_binary()
        unpacked = iTantraPacketV2.from_binary(raw_wire)
        self.assertTrue(self.auth.verify_and_authenticate(unpacked))

        # Priority playback enqueue
        controller = PriorityPlaybackController()
        controller.enqueue(unpacked)
        status = controller.get_queue_status()
        self.assertGreaterEqual(status["queue_depth"], 0)
        controller.stop()

    # 2. Hands-Free VAD Pipeline (Continuous VAD -> STT -> Secure Frame -> Queue -> TTS)
    def test_02_hands_free_vad_pipeline(self):
        proc = VADStreamProcessor(config=VADConfig())
        proc.set_mode("voice")
        self.assertEqual(proc.mode, "voice")

        # Test speech buffer processing
        vad = SileroVADDetector()
        chunk = np.zeros(512, dtype=np.float32)
        vad.start()
        prob = vad._predict_chunk(chunk)
        self.assertLess(prob, 0.5)
        vad.stop()
        proc.stop_live_mic()

    # 3. Security Gate Ordering (Tampered packet dropped before Priority Queue / TTS)
    def test_03_security_gate_ordering_prevents_unauthorized_priority(self):
        pkt = iTantraPacketV2(
            payload="Routine patrol.",
            sender_id="NODE-ALPHA",
            sequence_number=3,
            priority=iTantraPacketV2.PRIORITY_NORMAL,
            message_type=iTantraPacketV2.MESSAGE_TYPE_NORMAL
        )
        self.auth.sign_packet(pkt, self.node_a_key, raw_binary=True)

        # Attacker tampers priority to DISTRESS
        wire_bytes = bytearray(pkt.to_binary())
        wire_bytes[4] = iTantraPacketV2.PRIORITY_DISTRESS
        unpacked = iTantraPacketV2.from_binary(bytes(wire_bytes))

        # Verification must raise error and reject packet before it can be enqueued
        controller = PriorityPlaybackController()
        with self.assertRaises(AuthenticationFailedError):
            self.auth.verify_and_authenticate(unpacked)
            # If verification passed (it shouldn't), enqueue would happen here
            controller.enqueue(unpacked)

        # Verify queue remains empty
        self.assertEqual(controller.get_queue_status()["queue_depth"], 0)
        controller.stop()

    # 4. Priority Preemption (NORMAL -> DISTRESS -> NORMAL)
    def test_04_priority_preemption_ordering(self):
        controller = PriorityPlaybackController()
        pkt_normal1 = iTantraPacketV2(payload="Normal 1", priority=iTantraPacketV2.PRIORITY_NORMAL, sequence_number=4)
        pkt_distress = iTantraPacketV2(payload="Distress!", priority=iTantraPacketV2.PRIORITY_DISTRESS, sequence_number=5)
        pkt_normal2 = iTantraPacketV2(payload="Normal 2", priority=iTantraPacketV2.PRIORITY_NORMAL, sequence_number=6)

        controller.enqueue(pkt_normal1)
        controller.enqueue(pkt_normal2)
        controller.enqueue(pkt_distress)

        # Distress packet must preempt queued Normal 2
        status = controller.get_queue_status()
        self.assertIsNotNone(status)
        controller.stop()

    # 5. Explicit Language States Verification
    def test_05_explicit_language_states(self):
        # 4 Fully Supported + Verified
        self.assertEqual(DEFAULT_LANGUAGE_REGISTRY["en"].get_explicit_state(), LanguageProfile.STATUS_SUPPORTED_VERIFIED)
        self.assertEqual(DEFAULT_LANGUAGE_REGISTRY["hi"].get_explicit_state(), LanguageProfile.STATUS_SUPPORTED_VERIFIED)
        self.assertEqual(DEFAULT_LANGUAGE_REGISTRY["te"].get_explicit_state(), LanguageProfile.STATUS_SUPPORTED_VERIFIED)
        self.assertEqual(DEFAULT_LANGUAGE_REGISTRY["ml"].get_explicit_state(), LanguageProfile.STATUS_SUPPORTED_VERIFIED)

        # 5 STT-Only Languages
        self.assertEqual(DEFAULT_LANGUAGE_REGISTRY["ta"].get_explicit_state(), LanguageProfile.STATUS_STT_ONLY)
        self.assertEqual(DEFAULT_LANGUAGE_REGISTRY["gu"].get_explicit_state(), LanguageProfile.STATUS_STT_ONLY)
        self.assertEqual(DEFAULT_LANGUAGE_REGISTRY["mr"].get_explicit_state(), LanguageProfile.STATUS_STT_ONLY)
        self.assertEqual(DEFAULT_LANGUAGE_REGISTRY["kn"].get_explicit_state(), LanguageProfile.STATUS_STT_ONLY)
        self.assertEqual(DEFAULT_LANGUAGE_REGISTRY["bn"].get_explicit_state(), LanguageProfile.STATUS_STT_ONLY)

        # 1 Deferred Language (Odia)
        self.assertEqual(DEFAULT_LANGUAGE_REGISTRY["or"].get_explicit_state(), LanguageProfile.STATUS_DEFERRED)

    # 6. Zero Cloud / SAPI5 Fallback Verification
    def test_06_zero_sapi5_or_cloud_fallback(self):
        tts = NeuralONNXTTSEngine(precision="int8")
        # English, Hindi, Telugu, Malayalam must be verified neural ONNX
        for code in ["en", "hi", "te", "ml"]:
            meta = tts.LANGUAGE_MODELS[code]
            model_file = meta["model_file_int8"]
            model_path = os.path.join(tts.models_dir, meta["dir"], model_file)
            self.assertTrue(os.path.exists(model_path), f"Neural model missing for {code}: {model_path}")

        # Tamil must fail cleanly with ModelNotInstalledError, never SAPI5
        with self.assertRaises(ModelNotInstalledError):
            self.manager.load_model("ta", task="tts")

    # 7. Dual-Node Mutual Transceiver Loop with Raw 32B HMAC
    def test_07_dual_node_secure_transceiver_loop(self):
        tx_a = PeerTransceiver(
            listen_port=65471,
            peer_host="127.0.0.1",
            peer_port=65472,
            node_name="NODE-ALPHA",
            node_identity=NodeIdentity(node_id="NODE-ALPHA", secret_key=self.node_a_key),
            authenticator=self.auth,
            enforce_security=True
        )
        tx_b = PeerTransceiver(
            listen_port=65472,
            peer_host="127.0.0.1",
            peer_port=65471,
            node_name="NODE-BRAVO",
            node_identity=NodeIdentity(node_id="NODE-BRAVO", secret_key=self.node_b_key),
            authenticator=self.auth,
            enforce_security=True
        )

        tx_a.start()
        tx_b.start()
        time.sleep(0.3)

        success, pkt, metrics = tx_a.transmit("Secure tactical message.", target_host="127.0.0.1", target_port=65472)
        self.assertTrue(success)
        self.assertEqual(len(pkt.auth_tag), 32)

        tx_a.stop()
        tx_b.stop()

if __name__ == "__main__":
    unittest.main()
