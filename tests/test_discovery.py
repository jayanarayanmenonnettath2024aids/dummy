import unittest
import time
import socket
from typing import List
from unittest.mock import MagicMock

from app.discovery.models import DiscoveredDevice
from app.discovery.interface import DeviceDiscovery
from app.discovery.mdns_discovery import MdnsDeviceDiscovery, SERVICE_TYPE
from app.communication.peer_transceiver import PeerTransceiver
from app.tts.engine import BaseTTSEngine

class MockTTSEngine(BaseTTSEngine):
    def synthesize(self, text: str, language: str = "en", output_path=None, play_audio=False):
        return "mock.wav", 0.01


class TestDeviceDiscovery(unittest.TestCase):
    """
    Test suite for Block 1: Automatic Local Device Discovery
    Covers the 10 required test specifications.
    """

    # 1. Device model creation
    def test_01_device_model_creation(self):
        device = DiscoveredDevice(
            node_id="NODE-ALPHA",
            device_name="Tactical Unit Alpha",
            device_type="desktop",
            host="alpha.local.",
            ip="192.168.1.50",
            port=65432,
            languages=["en", "ta"],
            capabilities=["stt", "tts", "ptt"],
            protocol_version="1.0",
            online=True
        )
        self.assertEqual(device.node_id, "NODE-ALPHA")
        self.assertEqual(device.device_name, "Tactical Unit Alpha")
        self.assertEqual(device.ip, "192.168.1.50")
        self.assertEqual(device.port, 65432)
        self.assertTrue(device.online)
        self.assertIn("ta", device.languages)

        d_dict = device.to_dict()
        self.assertEqual(d_dict["node_id"], "NODE-ALPHA")
        self.assertEqual(d_dict["online"], True)

        restored = DiscoveredDevice.from_dict(d_dict)
        self.assertEqual(restored.node_id, device.node_id)
        self.assertEqual(restored.ip, device.ip)
        self.assertEqual(restored.port, device.port)

    # 2. Discovery service initialization
    def test_02_discovery_service_initialization(self):
        discovery = MdnsDeviceDiscovery(
            node_id="NODE-TEST-INIT",
            device_name="Test Node",
            tcp_port=65430,
            local_ip="127.0.0.1",
            device_type="desktop",
            languages=["en"],
            capabilities=["stt", "tts"]
        )
        self.assertEqual(discovery.node_id, "NODE-TEST-INIT")
        self.assertEqual(discovery.tcp_port, 65430)
        self.assertFalse(discovery._is_running)

    # 3. Advertisement metadata
    def test_03_advertisement_metadata(self):
        discovery = MdnsDeviceDiscovery(
            node_id="NODE-META",
            device_name="Metadata Node",
            tcp_port=65431,
            local_ip="192.168.1.99",
            device_type="tactical-field",
            languages=["en", "ta"],
            capabilities=["stt", "tts", "ptt"],
            protocol_version="1.0"
        )
        info = discovery._create_service_info()
        self.assertEqual(info.type, SERVICE_TYPE)
        self.assertEqual(info.port, 65431)
        self.assertIn(b"node_id", info.properties)
        self.assertEqual(info.properties[b"node_id"], b"NODE-META")
        self.assertEqual(info.properties[b"device_name"], b"Metadata Node")
        self.assertEqual(info.properties[b"device_type"], b"tactical-field")
        self.assertEqual(info.properties[b"languages"], b"en,ta")
        self.assertEqual(info.properties[b"capabilities"], b"stt,tts,ptt")
        self.assertEqual(info.properties[b"version"], b"1.0")

    # 4. Discovery callbacks
    def test_04_discovery_callbacks(self):
        discovery = MdnsDeviceDiscovery(node_id="NODE-CB", device_name="Callback Node")
        added_mock = MagicMock()
        removed_mock = MagicMock()
        updated_mock = MagicMock()

        discovery.on_device_added(added_mock)
        discovery.on_device_removed(removed_mock)
        discovery.on_device_updated(updated_mock)

        test_device = DiscoveredDevice(node_id="NODE-PEER-1", device_name="Peer 1")
        discovery._notify_added(test_device)
        added_mock.assert_called_once_with(test_device)

        discovery._notify_updated(test_device)
        updated_mock.assert_called_once_with(test_device)

        discovery._notify_removed(test_device)
        removed_mock.assert_called_once_with(test_device)

    # 5. Device appearing
    def test_05_device_appearing(self):
        discovery = MdnsDeviceDiscovery(node_id="NODE-LOCAL", device_name="Local Node")
        added_devices = []
        discovery.on_device_added(lambda d: added_devices.append(d))

        mock_zc = MagicMock()
        mock_info = MagicMock()
        mock_info.properties = {
            b"node_id": b"NODE-REMOTE-A",
            b"device_name": b"Remote Node A",
            b"device_type": b"desktop",
            b"languages": b"en,ta",
            b"capabilities": b"stt,tts,ptt",
            b"version": b"1.0"
        }
        mock_info.addresses = [socket.inet_aton("192.168.1.120")]
        mock_info.port = 65435
        mock_info.server = "remote-a.local."
        mock_zc.get_service_info.return_value = mock_info

        # Simulate service resolved event
        discovery._handle_service_resolved(mock_zc, SERVICE_TYPE, f"NODE-REMOTE-A.{SERVICE_TYPE}")

        devices = discovery.get_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].node_id, "NODE-REMOTE-A")
        self.assertEqual(devices[0].ip, "192.168.1.120")
        self.assertEqual(devices[0].port, 65435)
        self.assertTrue(devices[0].online)
        self.assertEqual(len(added_devices), 1)

    # 6. Device disappearing
    def test_06_device_disappearing(self):
        discovery = MdnsDeviceDiscovery(node_id="NODE-LOCAL", device_name="Local Node", stale_timeout=0.5)
        removed_devices = []
        discovery.on_device_removed(lambda d: removed_devices.append(d))

        # Add device first
        device = DiscoveredDevice(node_id="NODE-REMOTE-B", device_name="Remote B", ip="192.168.1.130", port=65436)
        with discovery._lock:
            discovery._devices["NODE-REMOTE-B"] = device
            discovery._service_to_node[f"NODE-REMOTE-B.{SERVICE_TYPE}"] = "NODE-REMOTE-B"

        # Explicit service removal announcement
        discovery._handle_service_removed(f"NODE-REMOTE-B.{SERVICE_TYPE}")
        self.assertFalse(device.online)
        self.assertEqual(len(removed_devices), 1)
        self.assertEqual(removed_devices[0].node_id, "NODE-REMOTE-B")

    # 7. Device reappearing
    def test_07_device_reappearing(self):
        discovery = MdnsDeviceDiscovery(node_id="NODE-LOCAL", device_name="Local Node")
        updated_events = []
        discovery.on_device_updated(lambda d: updated_events.append(d))

        mock_zc = MagicMock()
        mock_info = MagicMock()
        mock_info.properties = {
            b"node_id": b"NODE-REAPPEAR",
            b"device_name": b"Reappear Node",
            b"device_type": b"desktop",
            b"languages": b"en",
            b"capabilities": b"stt,tts",
            b"version": b"1.0"
        }
        mock_info.addresses = [socket.inet_aton("192.168.1.140")]
        mock_info.port = 65437
        mock_info.server = "reappear.local."
        mock_zc.get_service_info.return_value = mock_info

        service_name = f"NODE-REAPPEAR.{SERVICE_TYPE}"

        # 1. Device appears
        discovery._handle_service_resolved(mock_zc, SERVICE_TYPE, service_name)
        dev = discovery.get_device("NODE-REAPPEAR")
        self.assertTrue(dev.online)

        # 2. Device disappears (goes offline)
        discovery._handle_service_removed(service_name)
        self.assertFalse(dev.online)

        # 3. Device reappears (comes back online)
        discovery._handle_service_resolved(mock_zc, SERVICE_TYPE, service_name)
        self.assertTrue(dev.online)
        self.assertGreater(len(updated_events), 0)

    # 8. Multiple devices
    def test_08_multiple_devices(self):
        discovery = MdnsDeviceDiscovery(node_id="NODE-LOCAL", device_name="Local Node")
        mock_zc = MagicMock()

        for i in range(1, 4):
            mock_info = MagicMock()
            mock_info.properties = {
                b"node_id": f"NODE-MULTI-{i}".encode("utf-8"),
                b"device_name": f"Unit {i}".encode("utf-8"),
                b"device_type": b"desktop",
                b"languages": b"en",
                b"capabilities": b"stt,tts",
                b"version": b"1.0"
            }
            mock_info.addresses = [socket.inet_aton(f"192.168.1.10{i}")]
            mock_info.port = 65430 + i
            mock_info.server = f"unit{i}.local."
            mock_zc.get_service_info.return_value = mock_info

            discovery._handle_service_resolved(mock_zc, SERVICE_TYPE, f"NODE-MULTI-{i}.{SERVICE_TYPE}")

        devices = discovery.get_devices()
        self.assertEqual(len(devices), 3)
        device_ids = [d.node_id for d in devices]
        self.assertIn("NODE-MULTI-1", device_ids)
        self.assertIn("NODE-MULTI-2", device_ids)
        self.assertIn("NODE-MULTI-3", device_ids)

    # 9. Invalid discovery data
    def test_09_invalid_discovery_data(self):
        discovery = MdnsDeviceDiscovery(node_id="NODE-LOCAL", device_name="Local Node")
        mock_zc = MagicMock()

        # Corrupted / empty info
        mock_zc.get_service_info.return_value = None
        discovery._handle_service_resolved(mock_zc, SERVICE_TYPE, f"INVALID.{SERVICE_TYPE}")
        self.assertEqual(len(discovery.get_devices()), 0)

        # Missing properties dictionary
        broken_info = MagicMock()
        broken_info.properties = {}
        broken_info.addresses = []
        broken_info.port = 65432
        broken_info.server = ""
        mock_zc.get_service_info.return_value = broken_info

        discovery._handle_service_resolved(mock_zc, SERVICE_TYPE, f"BROKEN-NODE.{SERVICE_TYPE}")
        devices = discovery.get_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].node_id, "BROKEN-NODE")
        self.assertEqual(devices[0].ip, "127.0.0.1")

    # 10. Selected device producing correct host/port for TCP transceiver
    def test_10_selected_device_produces_correct_tcp_target(self):
        # Create discovery with a known remote peer
        discovery = MdnsDeviceDiscovery(node_id="NODE-A", device_name="Node A")
        discovered_peer = DiscoveredDevice(
            node_id="NODE-B",
            device_name="Node B",
            ip="127.0.0.1",
            port=65477,
            online=True
        )
        with discovery._lock:
            discovery._devices["NODE-B"] = discovered_peer

        # Initialize PeerTransceivers
        received_by_b = []
        transceiver_b = PeerTransceiver(
            listen_host="127.0.0.1",
            listen_port=65477,
            node_name="NODE-B",
            tts_engine=MockTTSEngine(),
            on_message_received=lambda pkt, met: received_by_b.append(pkt)
        )

        transceiver_a = PeerTransceiver(
            listen_host="127.0.0.1",
            listen_port=65476,
            peer_host="0.0.0.0",  # Unconfigured initial IP
            peer_port=0,
            node_name="NODE-A",
            tts_engine=MockTTSEngine()
        )

        try:
            transceiver_b.start()
            transceiver_a.start()
            time.sleep(0.2)

            # Auto-configure Transceiver A from the selected discovered device
            selected = discovery.get_device("NODE-B")
            self.assertIsNotNone(selected)
            transceiver_a.set_peer(peer_host=selected.ip, peer_port=selected.port)

            self.assertEqual(transceiver_a.peer_host, "127.0.0.1")
            self.assertEqual(transceiver_a.peer_port, 65477)

            # Transmit speech packet using the automatically selected endpoint
            success, pkt, met = transceiver_a.transmit(
                transcript="Discovery connection verified.",
                language="en",
                audio_size_bytes=80000
            )
            self.assertTrue(success)

            time.sleep(0.3)
            self.assertEqual(len(received_by_b), 1)
            self.assertEqual(received_by_b[0].payload, "Discovery connection verified.")
            self.assertEqual(received_by_b[0].sender_id, "NODE-A")

        finally:
            transceiver_a.stop()
            transceiver_b.stop()


if __name__ == "__main__":
    unittest.main()
