# iTANTRA — BLOCK 8 FRAMING & STREAM SECURITY

## 1. Length-Prefixed Stream Framing

To handle streaming networks (TCP, Serial RF Modems, Wi-Fi mesh sockets) where packet fragmentation or multi-packet coalescence occurs, iTantra uses a 4-byte big-endian framing prefix:

```
[ 4-Byte Frame Length (uint32) ] [ Binary Packet Payload (N Bytes) ]
```

---

## 2. Stream Reassembly Logic (`StreamFrameDecoder`)

1. **Partial Reads**: If fewer than 4 bytes or fewer than `4 + frame_len` bytes are received in a `recv()` call, the decoder preserves the buffer until the remaining fragments arrive.
2. **Packet Coalescence**: If multiple frames are received in a single chunk (`Frame A` + `Frame B`), the decoder parses `Frame A`, slices the accumulator, and immediately yields `Frame B`.
3. **Buffer Guard & Overflow Defense**:
   - `frame_len > MAX_PACKET_BYTES (65536)`: Immediate discard without memory allocation.
   - Rejects corrupted or impossible stream frame lengths safely.

---

## 3. Strict Verification Sequence

```
Incoming Stream Chunk
   ↓
StreamFrameDecoder (Length & Bounds Validation)
   ↓
iTantraPacketV2.from_binary() (Header & Field Structure Verification)
   ↓
PacketAuthenticator.verify_and_authenticate() (Raw 32-Byte HMAC Verification)
   ↓
ReplayWindow.check_and_update() (Sliding Replay Bitmask & Freshness Validation)
   ↓
TrustStore.is_trusted() (Offline Peer Authorization Check)
   ↓
PriorityPlaybackController.enqueue() (Priority Queue Routing)
   ↓
NeuralONNXTTSEngine.synthesize() (Voice Playback)
```
An unauthenticated or malformed packet is safely dropped at the cryptographic gate and **never reaches the priority queue or TTS audio engine**.
