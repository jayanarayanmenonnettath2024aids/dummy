import unittest
import time
import os
from zeroconf import Zeroconf
from app.discovery.mdns_discovery import MdnsDeviceDiscovery
from app.communication.peer_transceiver import PeerTransceiver
from app.stt.engine import WhisperSTTEngine
from app.tts.engine import LocalTTSEngine

class TestDiscoveryIntegration(unittest.TestCase):
    """
    End-to-end integration test verifying two iTantra nodes discovering each other
    over mDNS and transmitting voice packets without manual IP entry:
    Node A (Discovery) → STT → TCP → Node B (Discovery) → TTS
    """

    @classmethod
    def setUpClass(cls):
        # Load STT engine once
        cls.stt = WhisperSTTEngine()
        cls.tts = LocalTTSEngine()
        cls.sample_path = "samples/checkpoint_en.wav"

    def test_dual_node_autodiscovery_and_speech_transmission(self):
        # Shared Zeroconf instance on loopback to ensure deterministic instant mDNS resolution in test runner
        shared_zc = Zeroconf()

        port_a = 65481
        port_b = 65482

        # 1. Initialize Node A and Node B discovery with NO hardcoded peer IPs
        discovery_a = MdnsDeviceDiscovery(
            node_id="NODE-ALPHA-AUTO",
            device_name="Alpha Tactical Unit",
            tcp_port=port_a,
            local_ip="127.0.0.1",
            device_type="desktop",
            languages=["en", "ta"],
            capabilities=["stt", "tts", "ptt"],
            zeroconf_instance=shared_zc
        )

        discovery_b = MdnsDeviceDiscovery(
            node_id="NODE-BRAVO-AUTO",
            device_name="Bravo Field Unit",
            tcp_port=port_b,
            local_ip="127.0.0.1",
            device_type="desktop",
            languages=["en"],
            capabilities=["stt", "tts", "ptt"],
            zeroconf_instance=shared_zc
        )

        # 2. Initialize Transceivers with dummy initial target
        received_by_b = []
        transceiver_b = PeerTransceiver(
            listen_host="127.0.0.1",
            listen_port=port_b,
            peer_host="0.0.0.0",
            peer_port=0,
            node_name="NODE-BRAVO-AUTO",
            tts_engine=self.tts,
            on_message_received=lambda pkt, met: received_by_b.append(pkt)
        )

        transceiver_a = PeerTransceiver(
            listen_host="127.0.0.1",
            listen_port=port_a,
            peer_host="0.0.0.0",
            peer_port=0,
            node_name="NODE-ALPHA-AUTO",
            tts_engine=self.tts
        )

        try:
            # Start communication and discovery services
            transceiver_b.start()
            transceiver_a.start()

            discovery_a.start()
            discovery_b.start()

            # Wait for mDNS announcement and discovery resolution
            max_wait = 5.0
            start_t = time.time()
            dev_b_on_a = None
            dev_a_on_b = None

            while time.time() - start_t < max_wait:
                time.sleep(0.2)
                dev_b_on_a = discovery_a.get_device("NODE-BRAVO-AUTO")
                dev_a_on_b = discovery_b.get_device("NODE-ALPHA-AUTO")
                if dev_b_on_a and dev_a_on_b and dev_b_on_a.online and dev_a_on_b.online:
                    break

            # Verify Mutual Discovery
            self.assertIsNotNone(dev_b_on_a, "Node A failed to discover Node B over mDNS")
            self.assertIsNotNone(dev_a_on_b, "Node B failed to discover Node A over mDNS")
            self.assertEqual(dev_b_on_a.ip, "127.0.0.1")
            self.assertEqual(dev_b_on_a.port, port_b)
            self.assertEqual(dev_a_on_b.port, port_a)
            self.assertTrue(dev_b_on_a.online)
            self.assertTrue(dev_a_on_b.online)
            print(f"\n[+] Mutual Discovery Success: Node A found {dev_b_on_a.node_id} ({dev_b_on_a.ip}:{dev_b_on_a.port})")
            print(f"[+] Mutual Discovery Success: Node B found {dev_a_on_b.node_id} ({dev_a_on_b.ip}:{dev_a_on_b.port})")

            # 3. Connect Node A to Node B using discovered metadata (NO manual IP entered)
            transceiver_a.set_peer(peer_host=dev_b_on_a.ip, peer_port=dev_b_on_a.port)

            # 4. Perform End-to-End Flow: Node A Speech -> STT -> TCP -> Node B -> TTS
            self.assertTrue(os.path.exists(self.sample_path))
            audio_bytes_len = os.path.getsize(self.sample_path)
            t1_start = time.time()
            transcript, stt_latency = self.stt.transcribe(self.sample_path, language="en")
            t2_stt = time.time()

            self.assertGreater(len(transcript), 0)
            print(f"[+] Node A STT Transcript: '{transcript}'")

            # Transmit from Node A to discovered Node B
            success, packet, metrics = transceiver_a.transmit(
                transcript=transcript,
                language="en",
                audio_size_bytes=audio_bytes_len,
                t1_start=t1_start,
                t2_stt=t2_stt
            )
            self.assertTrue(success, "Transmission from Node A to discovered Node B failed")

            # Wait for Node B to receive and synthesize TTS
            start_wait = time.time()
            while time.time() - start_wait < 5.0 and len(received_by_b) == 0:
                time.sleep(0.1)

            self.assertEqual(len(received_by_b), 1, "Node B did not receive the transmitted packet")
            self.assertEqual(received_by_b[0].payload, transcript)
            self.assertEqual(received_by_b[0].sender_id, "NODE-ALPHA-AUTO")
            print(f"[+] Node B Received and Reconstructed: '{received_by_b[0].payload}' from {received_by_b[0].sender_id}")

        finally:
            discovery_a.stop()
            discovery_b.stop()
            transceiver_a.stop()
            transceiver_b.stop()
            shared_zc.close()


if __name__ == "__main__":
    unittest.main()
