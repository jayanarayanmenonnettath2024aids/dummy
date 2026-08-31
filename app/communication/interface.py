import json
import time
import uuid
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any

class iTantraPacket:
    """
    Structured packet format for iTantra low-bitrate communication.
    Designed for extensibility: includes headers for security, replay protection,
    and timestamps for end-to-end telemetry.
    """
    def __init__(
        self,
        payload: str,
        language: str = "en",
        sender_id: str = "NODE-A",
        sequence_number: int = 1,
        session_id: Optional[str] = None,
        audio_size_bytes: int = 0,
        t1_capture_start: float = 0.0,
        t2_stt_finish: float = 0.0,
        t3_tx_start: float = 0.0,
        t4_rx_finish: float = 0.0,
        version: str = "1.0",
        auth_tag: str = "FUTURE_SECURITY_TAG_PLACEHOLDER"
    ):
        self.version = version
        self.sender_id = sender_id
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.sequence_number = sequence_number
        self.language = language
        self.payload = payload
        self.audio_size_bytes = audio_size_bytes
        self.t1_capture_start = t1_capture_start
        self.t2_stt_finish = t2_stt_finish
        self.t3_tx_start = t3_tx_start
        self.t4_rx_finish = t4_rx_finish
        self.auth_tag = auth_tag  # Phase 12 Security Placeholder

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ver": self.version,
            "src": self.sender_id,
            "ses": self.session_id,
            "seq": self.sequence_number,
            "lang": self.language,
            "text": self.payload,
            "audio_bytes": self.audio_size_bytes,
            "t1": self.t1_capture_start,
            "t2": self.t2_stt_finish,
            "t3": self.t3_tx_start,
            "t4": self.t4_rx_finish,
            "sec_tag": self.auth_tag
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "iTantraPacket":
        return cls(
            payload=data.get("text", ""),
            language=data.get("lang", "en"),
            sender_id=data.get("src", "UNKNOWN"),
            sequence_number=data.get("seq", 0),
            session_id=data.get("ses", ""),
            audio_size_bytes=data.get("audio_bytes", 0),
            t1_capture_start=data.get("t1", 0.0),
            t2_stt_finish=data.get("t2", 0.0),
            t3_tx_start=data.get("t3", 0.0),
            t4_rx_finish=data.get("t4", 0.0),
            version=data.get("ver", "1.0"),
            auth_tag=data.get("sec_tag", "")
        )

    def to_bytes(self) -> bytes:
        """Serialize packet to UTF-8 JSON bytes."""
        json_str = json.dumps(self.to_dict(), ensure_ascii=False)
        return json_str.encode('utf-8')

    @classmethod
    def from_bytes(cls, raw_bytes: bytes) -> "iTantraPacket":
        """Deserialize UTF-8 JSON bytes to packet."""
        json_str = raw_bytes.decode('utf-8')
        data = json.loads(json_str)
        return cls.from_dict(data)

    def get_text_payload_bytes(self) -> int:
        """Returns byte size of the raw text message."""
        return len(self.payload.encode('utf-8'))

    def get_total_packet_bytes(self) -> int:
        """Returns total network frame byte size including metadata headers."""
        return len(self.to_bytes())


class CommunicationInterface(ABC):
    """
    Abstract communication transport interface.
    Allows transparent swapping between TCP, Wi-Fi, Bluetooth, Serial, LoRa, or Radio.
    """
    @abstractmethod
    def send(self, packet: iTantraPacket) -> Tuple[bool, float, int]:
        """
        Send a packet over the link.
        Returns: Tuple of (success: bool, latency_seconds: float, bytes_sent: int)
        """
        pass

    @abstractmethod
    def receive(self, timeout: Optional[float] = None) -> Tuple[Optional[iTantraPacket], float, int]:
        """
        Receive a packet from the link.
        Returns: Tuple of (packet: Optional[iTantraPacket], latency_seconds: float, bytes_received: int)
        """
        pass

    @abstractmethod
    def close(self):
        """Clean up connection/sockets."""
        pass
