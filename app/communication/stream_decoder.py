import struct
from typing import List, Optional, Tuple
from app.communication.packet_v2 import iTantraPacketV2, MAX_PACKET_BYTES

class StreamFrameDecoder:
    """
    Radio-Ready Length-Prefixed Stream Frame Decoder for TCP and Serial Mesh Channels.
    
    Framing Protocol:
        [4-byte Big-Endian Length Prefix (uint32)][Raw Binary Packet Bytes]
        
    Handles:
    - Partial TCP chunks (accumulates buffer until full frame arrives).
    - Concatenated frames (demuxes multiple packets delivered in a single recv()).
    - Incomplete or trailing fragments (retains tail for subsequent reads).
    - Rejection of oversized or impossible frame lengths before allocating buffers.
    """
    def __init__(self, max_frame_bytes: int = MAX_PACKET_BYTES):
        self.max_frame_bytes = max_frame_bytes
        self._buffer = bytearray()

    def feed_bytes(self, chunk: bytes) -> List[iTantraPacketV2]:
        """
        Feed incoming raw stream bytes and return all completely framed and deserialized packets.
        """
        if not chunk:
            return []

        self._buffer.extend(chunk)
        packets: List[iTantraPacketV2] = []

        while len(self._buffer) >= 4:
            # Peek 4-byte length prefix
            frame_len = struct.unpack("!I", self._buffer[:4])[0]

            if frame_len == 0 or frame_len > self.max_frame_bytes:
                # Malicious or corrupt length prefix -> discard invalid prefix
                self._buffer.clear()
                raise ValueError(f"Corrupt or oversized stream frame length: {frame_len} > {self.max_frame_bytes}")

            # Check if entire frame is available in buffer
            total_required = 4 + frame_len
            if len(self._buffer) < total_required:
                # Incomplete frame -> wait for more data from socket
                break

            # Extract full frame
            packet_raw = bytes(self._buffer[4:total_required])
            # Remove parsed frame from buffer
            del self._buffer[:total_required]

            # Deserialize packet
            packet = iTantraPacketV2.from_bytes(packet_raw)
            packets.append(packet)

        return packets

    def clear(self):
        """Clear internal stream buffer on connection reset or error."""
        self._buffer.clear()

    @property
    def buffer_size(self) -> int:
        """Current bytes in accumulator buffer."""
        return len(self._buffer)
