import struct
import json
import time
import uuid
from typing import Dict, Any, Optional, Tuple, Union

MAGIC_HEADER = b"IT"
PROTOCOL_VERSION_V2 = 2

# Production Size Bounds
MAX_PACKET_BYTES = 65536        # 64 KiB frame limit
MAX_PACKET_SIZE = MAX_PACKET_BYTES # Backward compatibility alias
MAX_TEXT_BYTES = 65535          # 64 KiB text (uint16 max)
MAX_NODE_ID_BYTES = 64          # 64 bytes
MAX_SESSION_ID_BYTES = 64       # 64 bytes
HMAC_RAW_BYTES = 32             # 32 raw binary bytes (256-bit digest)
MAX_AUTH_TAG_SIZE = 64          # Max allowable tag buffer (allows 32 raw bytes or 64 hex chars)

class iTantraPacketV2:
    """
    Production Compact, Endian-Defined Binary Transport Packet Protocol (V2.0).
    
    Wire Layout:
    - Fixed Header (25 bytes):
        Magic (2B, 'IT') | Version (1B, 2) | MsgType (1B) | Priority (1B) |
        Language (2B) | Seq (4B) | Timestamp (8B double) | AudioBytes (4B) | AuthTagLen (2B)
    - Variable Body:
        AuthTag (AuthTagLen bytes, 32 raw bytes for production HMAC-SHA256) |
        SenderLen (1B) | SenderID (SenderLen bytes) |
        SessionLen (1B) | SessionID (SessionLen bytes) |
        PayloadLen (2B) | Payload (PayloadLen bytes)
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
        auth_tag: Union[bytes, str] = b"",
        # Telemetry timestamp compatibility hooks
        t1_capture_start: float = 0.0,
        t2_stt_finish: float = 0.0,
        t3_tx_start: float = 0.0,
        t4_rx_finish: float = 0.0,
        version: str = "2.0"
    ):
        self.version = version
        self.message_type = int(message_type)
        self.priority = int(priority)
        self.sender_id = str(sender_id)
        self.session_id = str(session_id or str(uuid.uuid4())[:8])
        self.sequence_number = int(sequence_number)
        self.language = str(language)[:2].lower() if language else "en"
        self.payload = str(payload)
        self.audio_size_bytes = int(audio_size_bytes)
        self.timestamp = float(timestamp if timestamp is not None else time.time())
        self.auth_tag = auth_tag

        # Telemetry timestamps
        self.t1_capture_start = float(t1_capture_start or self.timestamp)
        self.t2_stt_finish = float(t2_stt_finish or self.timestamp)
        self.t3_tx_start = float(t3_tx_start)
        self.t4_rx_finish = float(t4_rx_finish)

    def _get_bytes_to_authenticate(self) -> bytes:
        """Returns deterministic canonical byte representation across all fields for HMAC signing."""
        sender_bytes = self.sender_id.encode("utf-8")
        session_bytes = self.session_id.encode("utf-8")
        payload_bytes = self.payload.encode("utf-8")
        lang_bytes = self.language.ljust(2, "\x00").encode("ascii", errors="ignore")[:2]

        header = struct.pack(
            "!2sBBB2sIdI",
            MAGIC_HEADER,
            PROTOCOL_VERSION_V2,
            self.message_type,
            self.priority,
            lang_bytes,
            self.sequence_number,
            float(self.timestamp),
            self.audio_size_bytes,
        )
        body = bytearray()
        body.append(len(sender_bytes))
        body.extend(sender_bytes)
        body.append(len(session_bytes))
        body.extend(session_bytes)
        body.extend(struct.pack("!H", len(payload_bytes)))
        body.extend(payload_bytes)
        return header + bytes(body)

    def _get_raw_auth_bytes(self) -> bytes:
        """Helper to get raw binary bytes from auth_tag (handling hex string or raw bytes)."""
        if not self.auth_tag:
            return b""
        if isinstance(self.auth_tag, (bytes, bytearray)):
            return bytes(self.auth_tag)
        if isinstance(self.auth_tag, str):
            if len(self.auth_tag) == 64:
                try:
                    return bytes.fromhex(self.auth_tag)
                except ValueError:
                    return self.auth_tag.encode("utf-8")
            return self.auth_tag.encode("utf-8")
        return b""

    def to_binary(self) -> bytes:
        """Serialize packet into compact, deterministic big-endian binary bytes."""
        sender_bytes = self.sender_id.encode("utf-8")
        session_bytes = self.session_id.encode("utf-8")
        payload_bytes = self.payload.encode("utf-8")
        auth_bytes = self._get_raw_auth_bytes()
        lang_bytes = self.language.ljust(2, "\x00").encode("ascii", errors="ignore")[:2]

        if len(sender_bytes) > MAX_NODE_ID_BYTES:
            sender_bytes = sender_bytes[:MAX_NODE_ID_BYTES]
        if len(session_bytes) > MAX_SESSION_ID_BYTES:
            session_bytes = session_bytes[:MAX_SESSION_ID_BYTES]
        if len(payload_bytes) > MAX_TEXT_BYTES:
            payload_bytes = payload_bytes[:MAX_TEXT_BYTES]
        if len(auth_bytes) > MAX_AUTH_TAG_SIZE:
            auth_bytes = auth_bytes[:MAX_AUTH_TAG_SIZE]

        # Fixed Header (25 bytes)
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

        full_packet = fixed_header + bytes(variable_body)
        if len(full_packet) > MAX_PACKET_BYTES:
            raise ValueError(f"Packet exceeds maximum allowable size: {len(full_packet)} > {MAX_PACKET_BYTES}")

        return full_packet

    @classmethod
    def from_binary(cls, raw_bytes: bytes) -> "iTantraPacketV2":
        """Deserialize and validate compact binary bytes into iTantraPacketV2 with hardened bounds."""
        if not raw_bytes or not isinstance(raw_bytes, (bytes, bytearray)):
            raise ValueError("Invalid raw packet bytes: input is empty or not bytes")

        if len(raw_bytes) > MAX_PACKET_BYTES:
            raise ValueError(f"Oversized packet rejected: {len(raw_bytes)} bytes exceeds limit {MAX_PACKET_BYTES}")

        if len(raw_bytes) < 25:
            raise ValueError(f"Packet too short / truncated: {len(raw_bytes)} bytes (min 25 bytes required)")

        # Parse fixed header
        magic, version, msg_type, priority, lang_raw, seq, ts, audio_bytes, auth_len = struct.unpack(
            "!2sBBB2sIdIH", raw_bytes[:25]
        )

        if magic != MAGIC_HEADER:
            raise ValueError(f"Invalid packet magic header: {magic!r} (expected {MAGIC_HEADER!r})")

        if version != PROTOCOL_VERSION_V2:
            raise ValueError(f"Unsupported binary protocol version: {version} (expected {PROTOCOL_VERSION_V2})")

        if msg_type not in cls.MESSAGE_TYPE_NAMES:
            raise ValueError(f"Invalid message type in binary packet: {msg_type}")

        if priority not in cls.PRIORITY_NAMES:
            raise ValueError(f"Invalid priority in binary packet: {priority}")

        if auth_len > MAX_AUTH_TAG_SIZE:
            raise ValueError(f"Invalid auth tag length: {auth_len} exceeds max {MAX_AUTH_TAG_SIZE}")

        lang = lang_raw.decode("ascii", errors="ignore").rstrip("\x00") or "en"
        offset = 25

        # Auth Tag
        auth_tag: Union[bytes, str] = b""
        if auth_len > 0:
            if offset + auth_len > len(raw_bytes):
                raise ValueError("Truncated packet: insufficient bytes for auth tag")
            tag_raw = raw_bytes[offset : offset + auth_len]
            if auth_len == 32:
                auth_tag = bytes(tag_raw)
            else:
                try:
                    auth_tag = tag_raw.decode("utf-8")
                except UnicodeDecodeError:
                    auth_tag = bytes(tag_raw)
            offset += auth_len

        # Sender ID
        if offset >= len(raw_bytes):
            raise ValueError("Truncated packet: missing sender ID length")
        sender_len = raw_bytes[offset]
        offset += 1
        if sender_len > MAX_NODE_ID_BYTES:
            raise ValueError(f"Sender ID length exceeds limit: {sender_len} > {MAX_NODE_ID_BYTES}")
        if offset + sender_len > len(raw_bytes):
            raise ValueError("Truncated packet: insufficient bytes for sender ID")
        try:
            sender_id = raw_bytes[offset : offset + sender_len].decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("Invalid UTF-8 in sender ID")
        offset += sender_len

        # Session ID
        if offset >= len(raw_bytes):
            raise ValueError("Truncated packet: missing session ID length")
        session_len = raw_bytes[offset]
        offset += 1
        if session_len > MAX_SESSION_ID_BYTES:
            raise ValueError(f"Session ID length exceeds limit: {session_len} > {MAX_SESSION_ID_BYTES}")
        if offset + session_len > len(raw_bytes):
            raise ValueError("Truncated packet: insufficient bytes for session ID")
        try:
            session_id = raw_bytes[offset : offset + session_len].decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("Invalid UTF-8 in session ID")
        offset += session_len

        # Payload Length & Bytes
        if offset + 2 > len(raw_bytes):
            raise ValueError("Truncated packet: missing payload length prefix")
        payload_len = struct.unpack("!H", raw_bytes[offset : offset + 2])[0]
        offset += 2

        if payload_len > MAX_TEXT_BYTES:
            raise ValueError(f"Oversized payload rejected: {payload_len} > {MAX_TEXT_BYTES}")

        if offset + payload_len > len(raw_bytes):
            raise ValueError(f"Truncated packet: expected {payload_len} payload bytes, got {len(raw_bytes) - offset}")

        try:
            payload = raw_bytes[offset : offset + payload_len].decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("Invalid UTF-8 in text payload")

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
        raw_tag = self._get_raw_auth_bytes()
        hex_tag = raw_tag.hex() if raw_tag else ""
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
            "sec_tag": hex_tag
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "iTantraPacketV2":
        """Reconstruct from dictionary format."""
        tag_val = data.get("sec_tag", "")
        if isinstance(tag_val, str) and len(tag_val) == 64:
            try:
                auth_tag = bytes.fromhex(tag_val)
            except ValueError:
                auth_tag = tag_val
        else:
            auth_tag = tag_val

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
            auth_tag=auth_tag
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
            return cls.from_binary(raw_bytes)

    def get_text_payload_bytes(self) -> int:
        """Returns byte size of the raw UTF-8 text message."""
        return len(self.payload.encode("utf-8"))

    def get_total_packet_bytes(self, format_type: str = "binary") -> int:
        """Returns total network frame byte size."""
        return len(self.to_bytes(format_type))
