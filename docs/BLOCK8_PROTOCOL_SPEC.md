# iTANTRA — BLOCK 8 PRODUCTION BINARY PROTOCOL SPECIFICATION

## 1. Protocol Overview & Wire Layout

```
┌─────────────┬─────────────┬─────────────┬─────────────┬─────────────┬─────────────┬─────────────┬─────────────┬─────────────┐
│ Magic Header│ Protocol Ver│ Message Type│ Priority    │ Language ID │ Sequence Num│ Timestamp   │ Audio Bytes │ AuthTag Len │
│ (2 Bytes)   │ (1 Byte)    │ (1 Byte)    │ (1 Byte)    │ (2 Bytes)   │ (4 Bytes)   │ (8 Bytes)   │ (4 Bytes)   │ (2 Bytes)   │
│ "IT" (0x4954│ 0x02        │ 1=NORM,3=ALR│ 0=NORM,3=DIS│ 'en','hi'   │ Big-Endian  │ IEEE754 dbl │ uint32      │ 32 (0x0020) │
└─────────────┴─────────────┴─────────────┴─────────────┴─────────────┴─────────────┴─────────────┴─────────────┴─────────────┘
  ◄────────────────────────────────────── FIXED HEADER (25 BYTES) ────────────────────────────────────────────────────────►

┌───────────────────────────────────────────────┬────────────┬─────────────┬────────────┬─────────────┬────────────┬─────────────┐
│ Raw HMAC-SHA256 Authentication Tag            │ Sender Len │ Sender ID   │ Session Len│ Session ID  │ Payload Len│ Text Payload│
│ (32 RAW BINARY BYTES)                         │ (1 Byte)   │ (N Bytes)   │ (1 Byte)   │ (M Bytes)   │ (2 Bytes)  │ (P Bytes)   │
└───────────────────────────────────────────────┴────────────┴─────────────┴────────────┴─────────────┴────────────┴─────────────┘
  ◄──────────────────────────────────────────── VARIABLE BODY SECTION ────────────────────────────────────────────────────────►
```

---

## 2. Field Specifications

| Field Name | Offset | Wire Type | Length (Bytes) | Description |
|------------|--------|-----------|----------------|-------------|
| `Magic Header` | 0 | ASCII Bytes | 2 | Fixed ASCII `b"IT"` (`0x4954`) |
| `Protocol Version` | 2 | `uint8` | 1 | Protocol version (`0x02`) |
| `Message Type` | 3 | `uint8` | 1 | `1`=NORMAL, `2`=VOICE_NOTE, `3`=ALERT, `4`=DISTRESS, `5`=ACK, `6`=HEARTBEAT |
| `Priority` | 4 | `uint8` | 1 | `0`=NORMAL, `1`=ELEVATED, `2`=ALERT, `3`=DISTRESS |
| `Language Code` | 5 | ASCII Bytes | 2 | 2-char ISO 639-1 (`en`, `hi`, `te`, `ml`, `ta`, etc.) |
| `Sequence Number` | 7 | `uint32` | 4 | Monotonic sequence number (Big-Endian) |
| `Timestamp` | 11 | `float64` | 8 | IEEE 754 double precision UNIX timestamp (Big-Endian) |
| `Audio Bytes` | 19 | `uint32` | 4 | Raw PCM voice byte count (Big-Endian) |
| `AuthTag Length` | 23 | `uint16` | 2 | Length of HMAC authentication tag (`32` for raw binary HMAC) |
| `AuthTag Bytes` | 25 | Raw Bytes | 32 | **Raw 32-byte binary HMAC-SHA256 digest** |
| `Sender ID Length`| 57 | `uint8` | 1 | Byte length of Node ID ($N \le 64$) |
| `Sender ID` | 58 | UTF-8 String | $N$ | Node UUID/ID string |
| `Session ID Length`| $58+N$ | `uint8` | 1 | Byte length of Session ID ($M \le 64$) |
| `Session ID` | $59+N$ | UTF-8 String | $M$ | Session identifier |
| `Payload Length` | $59+N+M$ | `uint16` | 2 | Byte length of UTF-8 transcribed text ($P \le 65535$) |
| `Text Payload` | $61+N+M$ | UTF-8 String | $P$ | Transcribed message payload |

---

## 3. Canonical HMAC Calculation

The HMAC-SHA256 signature is calculated over the canonical byte stream comprising:
```
HMAC_SHA256(
    Key,
    [Magic (2B)] + [Version (1B)] + [MsgType (1B)] + [Priority (1B)] +
    [Lang (2B)]  + [SeqNum (4B)]  + [Timestamp (8B)]+ [AudioBytes (4B)] +
    [SenderLen (1B)] + [SenderID] +
    [SessionLen (1B)]+ [SessionID]+
    [PayloadLen (2B)]+ [PayloadBytes]
)
```
Output: **32 raw binary bytes** inserted directly into the `AuthTag Bytes` variable section.
