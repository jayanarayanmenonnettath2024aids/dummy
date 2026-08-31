import time
import socket
import threading
from typing import Optional, Callable, Dict, Any, Tuple

from app.communication.interface import iTantraPacket
from app.communication.tcp_transport import TCPTransport
from app.tts.engine import BaseTTSEngine, LocalTTSEngine
from app.metrics.metrics import PipelineMetrics

class PeerTransceiver:
    """
    Continuous Bidirectional Transceiver (Walkie-Talkie Node).
    Listens for incoming packets concurrently on a background thread
    while allowing the user to transmit speech replies at any time.
    """
    def __init__(
        self,
        listen_host: str = "0.0.0.0",
        listen_port: int = 65432,
        peer_host: str = "127.0.0.1",
        peer_port: int = 65432,
        node_name: Optional[str] = None,
        tts_engine: Optional[BaseTTSEngine] = None,
        on_message_received: Optional[Callable[[iTantraPacket, PipelineMetrics], None]] = None,
        on_message_sent: Optional[Callable[[iTantraPacket, PipelineMetrics], None]] = None
    ):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.peer_host = peer_host
        self.peer_port = peer_port
        self.node_name = node_name or socket.gethostname()
        
        self.tts = tts_engine or LocalTTSEngine()
        self.on_message_received = on_message_received
        self.on_message_sent = on_message_sent
        
        self.is_running = False
        self._server_transport: Optional[TCPTransport] = None
        self._listener_thread: Optional[threading.Thread] = None
        self._sequence_number = 0

    def start(self):
        """Start the background listening server."""
        if self.is_running:
            return
        
        self.is_running = True
        self._server_transport = TCPTransport(
            host=self.listen_host,
            port=self.listen_port,
            is_server=True,
            timeout=1.0  # short timeout to allow checking is_running flag
        )
        
        self._listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listener_thread.start()
        print(f"[*] PeerTransceiver node [{self.node_name}] listening on port {self.listen_port}")

    def _listen_loop(self):
        """Continuous background loop waiting for incoming packets."""
        while self.is_running:
            try:
                packet, rx_latency, bytes_recv = self._server_transport.receive(timeout=1.0)
                if not packet:
                    continue

                # We received a valid message
                t5_start = time.perf_counter()
                
                # Reconstruct speech locally using offline TTS
                out_wav, tts_latency = self.tts.synthesize(
                    packet.payload,
                    language=packet.language,
                    play_audio=True
                )
                
                # Compute telemetry
                stt_latency_ms = (packet.t2_stt_finish - packet.t1_capture_start) * 1000.0 if packet.t1_capture_start else 0.0
                net_latency_ms = (packet.t4_rx_finish - packet.t3_tx_start) * 1000.0 if packet.t3_tx_start else rx_latency * 1000.0
                if net_latency_ms < 0:
                    net_latency_ms = rx_latency * 1000.0
                tts_latency_ms = tts_latency * 1000.0
                total_e2e_ms = stt_latency_ms + net_latency_ms + tts_latency_ms

                metrics = PipelineMetrics(
                    audio_size_bytes=packet.audio_size_bytes,
                    text_payload_bytes=packet.get_text_payload_bytes(),
                    total_packet_bytes=bytes_recv,
                    stt_latency_ms=stt_latency_ms,
                    network_latency_ms=net_latency_ms,
                    tts_latency_ms=tts_latency_ms,
                    end_to_end_latency_ms=total_e2e_ms,
                    transcript=packet.payload,
                    language=packet.language,
                    audio_transmitted=False
                )

                if self.on_message_received:
                    self.on_message_received(packet, metrics)

            except Exception as e:
                if self.is_running:
                    # Ignore normal socket closure during shutdown
                    err_msg = str(e)
                    if "10038" not in err_msg and "closed" not in err_msg.lower():
                        print(f"[!] Transceiver receive notice: {e}")
                time.sleep(0.1)

    def transmit(
        self,
        transcript: str,
        language: str = "en",
        audio_size_bytes: int = 0,
        t1_start: float = 0.0,
        t2_stt: float = 0.0,
        target_host: Optional[str] = None,
        target_port: Optional[int] = None
    ) -> Tuple[bool, Optional[iTantraPacket], Optional[PipelineMetrics]]:
        """
        Send a transcript packet to the designated peer node.
        """
        host = target_host or self.peer_host
        port = target_port or self.peer_port

        self._sequence_number += 1
        packet = iTantraPacket(
            payload=transcript,
            language=language,
            sender_id=self.node_name,
            sequence_number=self._sequence_number,
            audio_size_bytes=audio_size_bytes,
            t1_capture_start=t1_start or time.time(),
            t2_stt_finish=t2_stt or time.time()
        )

        client = TCPTransport(host=host, port=port, is_server=False, timeout=10.0)
        success, net_latency, bytes_sent = client.send(packet)

        stt_latency_ms = (packet.t2_stt_finish - packet.t1_capture_start) * 1000.0 if packet.t1_capture_start else 0.0
        net_latency_ms = net_latency * 1000.0

        metrics = PipelineMetrics(
            audio_size_bytes=audio_size_bytes,
            text_payload_bytes=packet.get_text_payload_bytes(),
            total_packet_bytes=bytes_sent,
            stt_latency_ms=stt_latency_ms,
            network_latency_ms=net_latency_ms,
            tts_latency_ms=0.0,
            end_to_end_latency_ms=stt_latency_ms + net_latency_ms,
            transcript=transcript,
            language=language,
            audio_transmitted=False
        )

        if success and self.on_message_sent:
            self.on_message_sent(packet, metrics)

        return success, packet, metrics

    def set_peer(self, peer_host: str, peer_port: int):
        """Update peer target endpoint."""
        self.peer_host = peer_host
        self.peer_port = peer_port

    def stop(self):
        """Cleanly terminate listening server."""
        self.is_running = False
        if self._server_transport:
            self._server_transport.close()
            self._server_transport = None
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=2.0)
        print(f"[*] PeerTransceiver node [{self.node_name}] stopped.")
