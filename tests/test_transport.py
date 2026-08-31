import unittest
import threading
import time
from app.communication.interface import iTantraPacket
from app.communication.tcp_transport import TCPTransport

class TestTCPTransport(unittest.TestCase):
    def test_packet_serialization(self):
        packet = iTantraPacket(
            payload="Meet me at checkpoint four.",
            language="en",
            sender_id="NODE-A",
            audio_size_bytes=128000
        )
        data_bytes = packet.to_bytes()
        self.assertIsInstance(data_bytes, bytes)
        
        restored = iTantraPacket.from_bytes(data_bytes)
        self.assertEqual(restored.payload, "Meet me at checkpoint four.")
        self.assertEqual(restored.sender_id, "NODE-A")
        self.assertEqual(restored.audio_size_bytes, 128000)

    def test_tcp_send_receive_loop(self):
        server = TCPTransport(host="127.0.0.1", port=65440, is_server=True, timeout=5.0)
        received_packets = []

        def server_worker():
            pkt, latency, num_bytes = server.receive()
            if pkt:
                received_packets.append(pkt)

        server_thread = threading.Thread(target=server_worker)
        server_thread.start()
        time.sleep(0.2)  # Give server time to bind

        client = TCPTransport(host="127.0.0.1", port=65440, is_server=False)
        test_packet = iTantraPacket(
            payload="Emergency team report to sector four.",
            language="en",
            sender_id="NODE-A"
        )
        success, lat, bytes_sent = client.send(test_packet)
        server_thread.join()
        server.close()

        self.assertTrue(success)
        self.assertGreater(bytes_sent, 0)
        self.assertEqual(len(received_packets), 1)
        self.assertEqual(received_packets[0].payload, "Emergency team report to sector four.")

if __name__ == "__main__":
    unittest.main()
