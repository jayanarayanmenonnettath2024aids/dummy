import hmac
import hashlib
import time
from typing import Dict, Tuple, Optional, Any, Union
from app.security.trust_store import TrustStore

class SecurityError(Exception):
    """Raised when packet authentication or security verification fails."""
    pass

class AuthenticationFailedError(SecurityError):
    pass

class ReplayAttackError(SecurityError):
    pass

class UntrustedPeerError(SecurityError):
    pass

class MalformedSecurityTagError(SecurityError):
    pass

class ReplayWindow:
    """
    Sliding Replay Window for packet sequence number validation.
    Maintains the highest sequence number seen and a 64-bit bitmask of received packets.
    Prevents replay of duplicated, out-of-order, or retransmitted packets.
    """
    WINDOW_SIZE = 64

    def __init__(self):
        self.max_seq: int = 0
        self.window_mask: int = 0  # 64-bit mask

    def check_and_update(self, seq: int) -> bool:
        """
        Validates sequence number and updates window if valid.
        Returns True if sequence number is valid and fresh, False if replayed/old.
        """
        if seq <= 0:
            return False

        if seq > self.max_seq:
            # Advance window
            diff = seq - self.max_seq
            if diff >= self.WINDOW_SIZE:
                self.window_mask = 1  # Reset mask
            else:
                self.window_mask = (self.window_mask << diff) | 1
            self.max_seq = seq
            return True

        # Packet is within the window behind max_seq
        diff = self.max_seq - seq
        if diff >= self.WINDOW_SIZE:
            # Too old, outside replay window
            return False

        # Check if bit is already set (duplicate/replayed packet)
        if (self.window_mask >> diff) & 1:
            return False

        # Mark bit as received
        self.window_mask |= (1 << diff)
        return True


class PacketAuthenticator:
    """
    Production Authenticated Cryptography & Replay Defense Engine for iTantra packets.
    Uses standard HMAC-SHA256 (32 raw binary bytes wire tag) and enforces sliding replay windows.
    """
    MAX_PACKET_AGE_SECONDS = 30.0  # Freshness window
    MAX_FUTURE_SKEW_SECONDS = 5.0  # Clock skew allowance

    def __init__(self, trust_store: Optional[TrustStore] = None):
        self.trust_store = trust_store or TrustStore()
        # Map of (sender_id, session_id) -> ReplayWindow
        self._replay_windows: Dict[Tuple[str, str], ReplayWindow] = {}

    def compute_raw_tag(self, key: bytes, data_to_sign: bytes) -> bytes:
        """Compute standard HMAC-SHA256 raw 32-byte binary digest."""
        if not key or not data_to_sign:
            return b""
        return hmac.new(key, data_to_sign, hashlib.sha256).digest()

    def compute_tag(self, key: bytes, data_to_sign: bytes) -> str:
        """Compute standard HMAC-SHA256 hex digest (64 hex characters) for JSON / logs."""
        if not key or not data_to_sign:
            return ""
        return hmac.new(key, data_to_sign, hashlib.sha256).hexdigest()

    def sign_packet(self, packet_v2, secret_key: bytes, raw_binary: bool = True) -> Union[bytes, str]:
        """Signs an iTantraPacketV2 instance with HMAC-SHA256 (32 raw bytes by default)."""
        if not secret_key:
            return b"" if raw_binary else ""
        data_to_sign = packet_v2._get_bytes_to_authenticate()
        if raw_binary:
            tag = self.compute_raw_tag(secret_key, data_to_sign)
        else:
            tag = self.compute_tag(secret_key, data_to_sign)
        packet_v2.auth_tag = tag
        return tag

    def verify_and_authenticate(self, packet_v2, custom_key: Optional[bytes] = None) -> bool:
        """
        Verifies authenticity, integrity, timestamp freshness, and replay status of an incoming packet.
        Supports both 32-byte raw binary digests and 64-character hex strings seamlessly.
        Raises SecurityError on violation.
        """
        sender_id = packet_v2.sender_id
        session_id = packet_v2.session_id
        seq = packet_v2.sequence_number
        pkt_time = packet_v2.timestamp
        auth_tag = packet_v2.auth_tag

        # 1. Device Trust Check
        secret_key = custom_key or self.trust_store.get_peer_key(sender_id)
        if not secret_key:
            raise UntrustedPeerError(f"Peer '{sender_id}' is not trusted or has no pairing key in TrustStore.")

        # 2. Authentication Tag Presence & Normalization
        if not auth_tag:
            raise MalformedSecurityTagError(f"Missing HMAC authentication tag on packet from '{sender_id}'.")

        # Convert tag to raw 32 bytes for comparison
        if isinstance(auth_tag, str):
            if len(auth_tag) == 64:
                try:
                    auth_bytes = bytes.fromhex(auth_tag)
                except ValueError:
                    raise MalformedSecurityTagError("Invalid hexadecimal characters in authentication tag.")
            elif len(auth_tag) == 32:
                auth_bytes = auth_tag.encode("latin-1")
            else:
                raise MalformedSecurityTagError(f"Invalid authentication tag length: {len(auth_tag)} (expected 32 raw bytes or 64 hex chars).")
        elif isinstance(auth_tag, (bytes, bytearray)):
            if len(auth_tag) == 32:
                auth_bytes = bytes(auth_tag)
            elif len(auth_tag) == 64:
                try:
                    auth_bytes = bytes.fromhex(auth_tag.decode("ascii"))
                except Exception:
                    raise MalformedSecurityTagError("Invalid hexadecimal bytes in authentication tag.")
            else:
                raise MalformedSecurityTagError(f"Invalid authentication tag byte length: {len(auth_tag)} (expected 32 raw bytes).")
        else:
            raise MalformedSecurityTagError(f"Unsupported authentication tag type: {type(auth_tag)}")

        # 3. Cryptographic Integrity (HMAC-SHA256 32-byte raw digest)
        data_to_sign = packet_v2._get_bytes_to_authenticate()
        expected_raw_tag = self.compute_raw_tag(secret_key, data_to_sign)
        if not hmac.compare_digest(auth_bytes, expected_raw_tag):
            raise AuthenticationFailedError(
                f"HMAC integrity verification failed for packet seq #{seq} from '{sender_id}'. "
                f"Packet was tampered with in transit (payload/priority/timestamp/headers modified)."
            )

        # 4. Timestamp Freshness Window
        now = time.time()
        age = now - pkt_time
        if age > self.MAX_PACKET_AGE_SECONDS:
            raise ReplayAttackError(
                f"Packet timestamp expired (age: {age:.2f}s > {self.MAX_PACKET_AGE_SECONDS}s). Replay rejected."
            )
        if (pkt_time - now) > self.MAX_FUTURE_SKEW_SECONDS:
            raise SecurityError(
                f"Packet timestamp is too far in future (skew: {pkt_time - now:.2f}s). Rejected."
            )

        # 5. Sliding Replay Window Validation
        key = (sender_id, session_id)
        if key not in self._replay_windows:
            self._replay_windows[key] = ReplayWindow()
        
        window = self._replay_windows[key]
        if not window.check_and_update(seq):
            raise ReplayAttackError(
                f"Duplicate or replayed packet detected (seq #{seq} in session '{session_id}' from '{sender_id}')."
            )

        return True
