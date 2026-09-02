import time
import socket
import threading
from typing import Optional, Callable, Dict, Any, Tuple

from app.communication.interface import iTantraPacket
from app.communication.packet_v2 import iTantraPacketV2
from app.communication.tcp_transport import TCPTransport
from app.communication.playback_controller import PriorityPlaybackController
from app.tts.engine import BaseTTSEngine, LocalTTSEngine
from app.metrics.metrics import PipelineMetrics
from app.security.identity import NodeIdentity
from app.security.trust_store import TrustStore
from app.security.authenticator import (
    PacketAuthenticator,
    SecurityError,
    AuthenticationFailedError,
    ReplayAttackError,
    UntrustedPeerError
)

class PeerTransceiver:
    """
    Continuous Bidirectional Transceiver (Walkie-Talkie Node) with Alert Priority & Security Defense.
    Listens for incoming packets concurrently on a background thread,
    verifies cryptographic authenticity and replay window BEFORE priority queuing,
    and routes valid incoming messages through the PriorityPlaybackController.
    """
    def __init__(
        self,
        listen_host: str = "0.0.0.0",
        listen_port: int = 65432,
        peer_host: str = "127.0.0.1",
        peer_port: int = 65432,
        node_name: Optional[str] = None,
        tts_engine: Optional[BaseTTSEngine] = None,
        playback_controller: Optional[PriorityPlaybackController] = None,
        on_message_received: Optional[Callable[[iTantraPacket, PipelineMetrics], None]] = None,
        on_message_sent: Optional[Callable[[iTantraPacket, PipelineMetrics], None]] = None,
        transport_format: str = "binary",
        authenticator: Optional[PacketAuthenticator] = None,
        node_identity: Optional[NodeIdentity] = None,
        enforce_security: bool = False
    ):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.peer_host = peer_host
        self.peer_port = peer_port
        self.node_name = node_name or socket.gethostname()
        self.transport_format = transport_format
        
        self.tts = tts_engine or LocalTTSEngine()
        self.playback_controller = playback_controller
        self.on_message_received = on_message_received
        self.on_message_sent = on_message_sent
        
        # Security components
        self.node_identity = node_identity
        self.authenticator = authenticator
        self.enforce_security = enforce_security
        self.security_violations_count = 0
        
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

                # Ensure packet is iTantraPacketV2 or compatible
                if not isinstance(packet, iTantraPacketV2):
                    packet_v2 = iTantraPacketV2(
                        payload=packet.payload,
                        language=packet.language,
                        sender_id=packet.sender_id,
                        sequence_number=packet.sequence_number,
                        session_id=packet.session_id,
                        audio_size_bytes=packet.audio_size_bytes,
                        t1_capture_start=packet.t1_capture_start,
                        t2_stt_finish=packet.t2_stt_finish,
                        t3_tx_start=packet.t3_tx_start,
                        t4_rx_finish=packet.t4_rx_finish,
                        auth_tag=getattr(packet, "auth_tag", "")
                    )
                else:
                    packet_v2 = packet

                # SECURITY GATE: Verify authenticity & replay defense BEFORE priority queue or TTS
                if self.enforce_security and self.authenticator:
                    try:
                        self.authenticator.verify_and_authenticate(packet_v2)
                    except SecurityError as sec_err:
                        self.security_violations_count += 1
                        print(f"[SECURITY ALERT] Rejected malicious/unauthenticated packet from '{packet_v2.sender_id}': {sec_err}")
                        continue  # DROP PACKET SAFELY

                # If PriorityPlaybackController is attached, enqueue for priority playback
                if self.playback_controller:
                    self.playback_controller.enqueue(packet_v2)
                    tts_latency = 0.05
                else:
                    # Direct synthesis fallback
                    out_wav, tts_latency = self.tts.synthesize(
                        packet_v2.payload,
                        language=packet_v2.language,
                        play_audio=True
                    )
                
                # Compute telemetry
                stt_latency_ms = (packet_v2.t2_stt_finish - packet_v2.t1_capture_start) * 1000.0 if packet_v2.t1_capture_start else 0.0
                net_latency_ms = (packet_v2.t4_rx_finish - packet_v2.t3_tx_start) * 1000.0 if packet_v2.t3_tx_start else rx_latency * 1000.0
                if net_latency_ms < 0:
                    net_latency_ms = rx_latency * 1000.0
                tts_latency_ms = tts_latency * 1000.0
                total_e2e_ms = stt_latency_ms + net_latency_ms + tts_latency_ms

                metrics = PipelineMetrics(
                    audio_size_bytes=packet_v2.audio_size_bytes,
                    text_payload_bytes=packet_v2.get_text_payload_bytes(),
                    total_packet_bytes=bytes_recv,
                    stt_latency_ms=stt_latency_ms,
                    network_latency_ms=net_latency_ms,
                    tts_latency_ms=tts_latency_ms,
                    end_to_end_latency_ms=total_e2e_ms,
                    transcript=packet_v2.payload,
                    language=packet_v2.language,
                    audio_transmitted=False
                )

                if self.on_message_received:
                    self.on_message_received(packet_v2, metrics)

            except Exception as e:
                if self.is_running:
                    err_msg = str(e)
                    if "10038" not in err_msg and "closed" not in err_msg.lower():
                        print(f"[!] Transceiver receive notice: {e}")
                time.sleep(0.1)

    def transmit(
        self,
        transcript: str,
        language: str = "en",
        message_type: int = iTantraPacketV2.MESSAGE_TYPE_NORMAL,
        priority: int = iTantraPacketV2.PRIORITY_NORMAL,
        audio_size_bytes: int = 0,
        t1_start: float = 0.0,
        t2_stt: float = 0.0,
        target_host: Optional[str] = None,
        target_port: Optional[int] = None,
        signing_key: Optional[bytes] = None
    ) -> Tuple[bool, Optional[iTantraPacketV2], Optional[PipelineMetrics]]:
        """
        Send a transcript packet with designated message type, priority, and HMAC authentication tag.
        """
        host = target_host or self.peer_host
        port = target_port or self.peer_port

        self._sequence_number += 1
        packet = iTantraPacketV2(
            payload=transcript,
            language=language,
            sender_id=self.node_name,
            sequence_number=self._sequence_number,
            message_type=message_type,
            priority=priority,
            audio_size_bytes=audio_size_bytes,
            t1_capture_start=t1_start or time.time(),
            t2_stt_finish=t2_stt or time.time()
        )

        # Cryptographic signing if key/authenticator available
        key_to_use = signing_key or (self.node_identity.secret_key if self.node_identity else None)
        if key_to_use and self.authenticator:
            self.authenticator.sign_packet(packet, key_to_use)

        client = TCPTransport(host=host, port=port, is_server=False, timeout=10.0, transport_format=self.transport_format)
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
