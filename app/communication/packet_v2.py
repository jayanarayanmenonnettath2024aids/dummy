import json
import struct
import time
import uuid
from typing import Optional, Dict, Any, Tuple

MAGIC_HEADER = b"IT"
PROTOCOL_VERSION_V2 = 2

class iTantraPacketV2:
    """
    Compact deterministic binary packet protocol for low-bandwidth tactical voice links.
    
    Binary Frame Layout (Big-Endian `!`):
    -----------------------------------------------------------------------------------
    Offset | Type      | Field Name          | Description
    -----------------------------------------------------------------------------------
    0..1   | 2 bytes   | Magic Header        | ASCII 'IT' (0x49, 0x54)
    2      | uint8     | Version             | Protocol version (0x02 for V2)
    3      | uint8     | Message Type        | 1=VOICE, 2=ACK, 3=HEARTBEAT, 4=EMERGENCY
    4      | uint8     | Priority            | 0=NORMAL, 1=HIGH, 2=EMERGENCY
    5..6   | 2 bytes   | Language Code       | 2-byte ISO code (e.g. 'en', 'ta')
    7..10  | uint32    | Sequence Number     | Monotonic sequence ID
    11..18 | float64   | Timestamp           | Epoch timestamp in seconds (Double)
    19..22 | uint32    | Audio Size Bytes    | Original PCM audio size
    23..24 | uint16    | Auth Tag Length     | Length of reserved security tag (K)
    25..   | K bytes   | Auth Tag Bytes      | Security cryptographic tag
           | uint8     | Sender ID Length    | Length of sender string (N)
           | N bytes   | Sender ID Bytes     | UTF-8 sender node name
           | uint8     | Session ID Length   | Length of session string (M)
           | M bytes   | Session ID Bytes    | UTF-8 session UUID prefix
           | uint16    | Payload Length      | Length of text message (P)
           | P bytes   | Payload Bytes       | UTF-8 transcribed text payload
    -----------------------------------------------------------------------------------
    """
    MESSAGE_TYPE_NORMAL = 1
    MESSAGE_TYPE_VOICE_NOTE = 2
    MESSAGE_TYPE_ALERT = 3
    MESSAGE_TYPE_DISTRESS = 4
    MESSAGE_TYPE_VOICE = 1        # Backward compatibility alias
    MESSAGE_TYPE_ACK = 5
    MESSAGE_TYPE_HEARTBEAT = 6
    MESSAGE_TYPE_EMERGENCY = 4    # Backward compatibility alias

    PRIORITY_NORMAL = 0
    PRIORITY_ELEVATED = 1
    PRIORITY_ALERT = 2
    PRIORITY_DISTRESS = 3
    PRIORITY_HIGH = 1             # Backward compatibility alias
    PRIORITY_EMERGENCY = 3        # Backward compatibility alias

    MESSAGE_TYPE_NAMES = {
        1: "NORMAL",
        2: "VOICE_NOTE",
        3: "ALERT",
        4: "DISTRESS",
        5: "ACK",
        6: "HEARTBEAT"
    }

    PRIORITY_NAMES = {
        0: "NORMAL",
        1: "ELEVATED",
        2: "ALERT",
        3: "DISTRESS"
    }

    def get_message_type_name(self) -> str:
        return self.MESSAGE_TYPE_NAMES.get(self.message_type, "NORMAL")

    def get_priority_name(self) -> str:
        return self.PRIORITY_NAMES.get(self.priority, "NORMAL")

    def __init__(
        self,
        payload: str,
        language: str = "en",
        sender_id: str = "NODE-A",
        sequence_number: int = 1,
        session_id: Optional[str] = None,
        message_type: int = MESSAGE_TYPE_VOICE,
        priority: int = PRIORITY_NORMAL,
        audio_size_bytes: int = 0,
        timestamp: Optional[float] = None,
        auth_tag: str = "",
        # Telemetry timestamp compatibility hooks
        t1_capture_start: float = 0.0,
        t2_stt_finish: float = 0.0,
        t3_tx_start: float = 0.0,
        t4_rx_finish: float = 0.0,
        version: str = "2.0"
    ):
        self.version = version
        self.message_type = message_type
        self.priority = priority
        self.sender_id = sender_id
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.sequence_number = sequence_number
        self.language = language[:2].lower() if language else "en"
        self.payload = payload
        self.audio_size_bytes = audio_size_bytes
        self.timestamp = timestamp or time.time()
        self.auth_tag = auth_tag

        # Telemetry timestamps
        self.t1_capture_start = t1_capture_start or self.timestamp
        self.t2_stt_finish = t2_stt_finish or self.timestamp
        self.t3_tx_start = t3_tx_start
        self.t4_rx_finish = t4_rx_finish

    def to_binary(self) -> bytes:
        """Serialize packet into compact, deterministic big-endian binary bytes."""
        sender_bytes = self.sender_id.encode("utf-8")
        session_bytes = self.session_id.encode("utf-8")
        payload_bytes = self.payload.encode("utf-8")
        auth_bytes = self.auth_tag.encode("utf-8") if self.auth_tag else b""
        lang_bytes = self.language.ljust(2, "\x00").encode("ascii")[:2]

        if len(sender_bytes) > 255:
            sender_bytes = sender_bytes[:255]
        if len(session_bytes) > 255:
            session_bytes = session_bytes[:255]
        if len(payload_bytes) > 65535:
            payload_bytes = payload_bytes[:65535]
        if len(auth_bytes) > 65535:
            auth_bytes = auth_bytes[:65535]

        # Fixed Header (25 bytes)
        # Format: 2s (Magic), B (Version), B (Type), B (Priority), 2s (Lang), I (Seq), d (Time), I (AudioBytes), H (AuthLen)
        fixed_header = struct.pack(
            "!2sBBB2sIdIH",
            MAGIC_HEADER,
            PROTOCOL_VERSION_V2,
            self.message_type,
            self.priority,
            lang_bytes,
            self.sequence_number,
            float(self.timestamp),
            self.audio_size_bytes,
            len(auth_bytes)
        )

        # Variable Length Section
        variable_body = bytearray()
        if auth_bytes:
            variable_body.extend(auth_bytes)

        variable_body.append(len(sender_bytes))
        variable_body.extend(sender_bytes)

        variable_body.append(len(session_bytes))
        variable_body.extend(session_bytes)

        variable_body.extend(struct.pack("!H", len(payload_bytes)))
        variable_body.extend(payload_bytes)

        return fixed_header + bytes(variable_body)

    @classmethod
    def from_binary(cls, raw_bytes: bytes) -> "iTantraPacketV2":
        """Deserialize compact binary bytes into iTantraPacketV2."""
        if len(raw_bytes) < 25:
            raise ValueError(f"Packet too short: {len(raw_bytes)} bytes (min 25 bytes required)")

        # Parse fixed header
        magic, version, msg_type, priority, lang_raw, seq, ts, audio_bytes, auth_len = struct.unpack(
            "!2sBBB2sIdIH", raw_bytes[:25]
        )

        if magic != MAGIC_HEADER:
            raise ValueError(f"Invalid packet magic header: {magic!r} (expected {MAGIC_HEADER!r})")

        if version != PROTOCOL_VERSION_V2:
            raise ValueError(f"Unsupported binary protocol version: {version} (expected {PROTOCOL_VERSION_V2})")

        lang = lang_raw.decode("ascii", errors="ignore").rstrip("\x00") or "en"
        offset = 25

        # Auth Tag
        auth_tag = ""
        if auth_len > 0:
            if offset + auth_len > len(raw_bytes):
                raise ValueError("Truncated packet: insufficient bytes for auth tag")
            auth_tag = raw_bytes[offset : offset + auth_len].decode("utf-8", errors="replace")
            offset += auth_len

        # Sender ID
        if offset >= len(raw_bytes):
            raise ValueError("Truncated packet: missing sender ID length")
        sender_len = raw_bytes[offset]
        offset += 1
        if offset + sender_len > len(raw_bytes):
            raise ValueError("Truncated packet: insufficient bytes for sender ID")
        sender_id = raw_bytes[offset : offset + sender_len].decode("utf-8", errors="replace")
        offset += sender_len

        # Session ID
        if offset >= len(raw_bytes):
            raise ValueError("Truncated packet: missing session ID length")
        session_len = raw_bytes[offset]
        offset += 1
        if offset + session_len > len(raw_bytes):
            raise ValueError("Truncated packet: insufficient bytes for session ID")
        session_id = raw_bytes[offset : offset + session_len].decode("utf-8", errors="replace")
        offset += session_len

        # Payload Length & Bytes
        if offset + 2 > len(raw_bytes):
            raise ValueError("Truncated packet: missing payload length prefix")
        payload_len = struct.unpack("!H", raw_bytes[offset : offset + 2])[0]
        offset += 2

        if offset + payload_len > len(raw_bytes):
            raise ValueError(f"Truncated packet: expected {payload_len} payload bytes, got {len(raw_bytes) - offset}")

        payload = raw_bytes[offset : offset + payload_len].decode("utf-8", errors="replace")

        return cls(
            payload=payload,
            language=lang,
            sender_id=sender_id,
            sequence_number=seq,
            session_id=session_id,
            message_type=msg_type,
            priority=priority,
            audio_size_bytes=audio_bytes,
            timestamp=ts,
            auth_tag=auth_tag,
            version=f"{version}.0"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Dictionary format for JSON serialization and development logs."""
        return {
            "ver": self.version,
            "type": self.message_type,
            "pri": self.priority,
            "src": self.sender_id,
            "ses": self.session_id,
            "seq": self.sequence_number,
            "lang": self.language,
            "text": self.payload,
            "message_type_name": self.get_message_type_name(),
            "priority_name": self.get_priority_name(),
            "audio_bytes": self.audio_size_bytes,
            "ts": self.timestamp,
            "t1": self.t1_capture_start,
            "t2": self.t2_stt_finish,
            "t3": self.t3_tx_start,
            "t4": self.t4_rx_finish,
            "sec_tag": self.auth_tag
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "iTantraPacketV2":
        """Reconstruct from dictionary format."""
        return cls(
            payload=data.get("text", ""),
            language=data.get("lang", "en"),
            sender_id=data.get("src", "UNKNOWN"),
            sequence_number=int(data.get("seq", 0)),
            session_id=data.get("ses", ""),
            message_type=int(data.get("type", cls.MESSAGE_TYPE_VOICE)),
            priority=int(data.get("pri", cls.PRIORITY_NORMAL)),
            audio_size_bytes=int(data.get("audio_bytes", 0)),
            timestamp=float(data.get("ts", data.get("t1", time.time()))),
            t1_capture_start=float(data.get("t1", 0.0)),
            t2_stt_finish=float(data.get("t2", 0.0)),
            t3_tx_start=float(data.get("t3", 0.0)),
            t4_rx_finish=float(data.get("t4", 0.0)),
            version=str(data.get("ver", "2.0")),
            auth_tag=data.get("sec_tag", "")
        )

    def to_json(self) -> str:
        """Serialize packet to JSON string (for debugging / logging)."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "iTantraPacketV2":
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def to_bytes(self, format_type: str = "binary") -> bytes:
        """Serialize according to specified format ('binary' or 'json')."""
        if format_type.lower() == "binary":
            return self.to_binary()
        return self.to_json().encode("utf-8")

    @classmethod
    def from_bytes(cls, raw_bytes: bytes) -> "iTantraPacketV2":
        """Auto-detect format: deserializes binary if starting with 'IT', else JSON."""
        if raw_bytes.startswith(MAGIC_HEADER):
            return cls.from_binary(raw_bytes)
        try:
            json_str = raw_bytes.decode("utf-8")
            return cls.from_json(json_str)
        except Exception:
            # Fallback to binary parse attempt
            return cls.from_binary(raw_bytes)

    def get_text_payload_bytes(self) -> int:
        """Returns byte size of the raw UTF-8 text message."""
        return len(self.payload.encode("utf-8"))

    def get_total_packet_bytes(self, format_type: str = "binary") -> int:
        """Returns total network frame byte size."""
        return len(self.to_bytes(format_type))
