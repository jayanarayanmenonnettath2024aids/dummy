# iTANTRA — FINAL DESKTOP ARCHITECTURE & PRE-ANDROID CONTRACT

## 1. Executive Summary & Architectural Freeze

This specification represents the **frozen software architecture** of the iTANTRA Tactical Offline Walkie-Talkie System. All subsystems, interfaces, binary wire layouts, cryptographic algorithms, state machines, and priority rules defined herein constitute the formal **Pre-Android Contract**. The subsequent Android implementation will directly conform to these interfaces.

---

## 2. Frozen AI Subsystem Interfaces

### A. Streaming Voice Activity Detection (VAD)
- **Model**: `silero_vad.onnx` (FP32 ONNX, 2.22 MiB).
- **Interface**: `SileroVADDetector` / `VADStreamProcessor`.
- **Sample Rate**: 16,000 Hz, single channel, float32 PCM.
- **Chunk Size**: 512 samples (32.0 ms per step).
- **State Machine**:
  - `SILENCE` $\rightarrow$ Speech Probability $>0.50$ (Min 96 ms) $\rightarrow$ `SPEECH_STARTED`.
  - `SPEECH` $\rightarrow$ Silence Duration $>480$ ms $\rightarrow$ `SPEECH_ENDED` $\rightarrow$ Transcribe Utterance.
  - Ring Buffer: 192 ms pre-speech buffer + 160 ms post-speech padding.
  - Maximum Utterance Limit: 15.0 seconds.

### B. Multilingual Speech-to-Text (STT)
- **Model**: `openai/whisper-tiny` (Shared multilingual FP32 ONNX/PyTorch, 148.23 MiB, 37.76M parameters).
- **Interface**: `WhisperSTT.transcribe(audio_pcm, sample_rate=16000, language="en") -> (transcript: str, latency: float)`.
- **Language Coverage**: 9 Verified PS Languages (`en`, `hi`, `te`, `ml`, `ta`, `gu`, `mr`, `kn`, `bn`).
- **Odia (`or`)**: Explicitly marked `DEFERRED` (unsupported in Whisper vocabulary).

### C. Modular Neural Text-to-Speech (TTS)
- **Runtime**: `sherpa-onnx` CPU inference with ONNX Runtime backend.
- **Precision**: INT8 dynamically quantized (`~17.6 MiB` per language voice).
- **Production Models**:
  - English (`en`): `vits-piper-en_US-lessac-medium.int8.onnx`
  - Hindi (`hi`): `vits-piper-hi_IN-pratham-medium.int8.onnx`
  - Telugu (`te`): `vits-piper-te_IN-maya-medium.int8.onnx`
  - Malayalam (`ml`): `vits-piper-ml_IN-meera-medium.int8.onnx`
- **Zero Fallback Policy**: Windows SAPI5, `pyttsx3`, and cloud endpoints are strictly prohibited. Unsupported TTS languages report `STT ONLY`.

---

## 3. Frozen Binary Packet Protocol (V2.0)

### Wire Layout (Length-Prefixed Framing)
```
[ 4-Byte Frame Length (uint32) ]
[ 25-Byte Fixed Header ]
  - Magic: 2B ASCII "IT" (0x4954)
  - Version: 1B uint8 (0x02)
  - MsgType: 1B uint8 (1=NORM, 2=VOICE_NOTE, 3=ALERT, 4=DISTRESS, 5=ACK, 6=HEARTBEAT)
  - Priority: 1B uint8 (0=NORM, 1=ELEVATED, 2=ALERT, 3=DISTRESS)
  - Language: 2B ASCII (e.g. "en", "hi")
  - SequenceNumber: 4B uint32 (Big-Endian)
  - Timestamp: 8B float64 IEEE 754 (Big-Endian)
  - AudioBytes: 4B uint32 (0 for pure text)
  - AuthTagLen: 2B uint16 (32 for raw HMAC-SHA256)
[ Variable Length Body ]
  - AuthTag: 32 Raw Binary Bytes (HMAC-SHA256)
  - SenderLen: 1B uint8
  - SenderID: N Bytes UTF-8 (N <= 64)
  - SessionLen: 1B uint8
  - SessionID: M Bytes UTF-8 (M <= 64)
  - PayloadLen: 2B uint16 (P <= 65535)
  - Payload: P Bytes UTF-8 Transcribed Text
```

---

## 4. Frozen Cryptographic Security & Verification Order

```
Incoming Stream Frame
   ↓
1. StreamFrameDecoder: Validate 4-byte length prefix <= 65536 bytes.
   ↓
2. Header & Bounds Check: Validate Magic "IT", Version 2, MsgType, Priority, UTF-8.
   ↓
3. HMAC-SHA256 Verification: Verify 32-byte raw binary signature over canonical header+body.
   ↓
4. Timestamp Freshness: Verify packet age <= 30.0 s, future clock skew <= 5.0 s.
   ↓
5. Sliding Replay Window: 64-bit bitmask validation per (SenderID, SessionID).
   ↓
6. TrustStore Authorization: Verify SenderID is paired and status == "TRUSTED".
   ↓
7. Priority Playback Queue: Route to PriorityPlaybackController (preempt on DISTRESS).
   ↓
8. Neural ONNX TTS: Synthesize speech and play audio output.
```

---

## 5. Frozen Operating Modes

- **PTT Mode**: Microphone streams only while PTT button is held; VAD background thread is paused.
- **Hands-Free VAD Mode**: Continuous microphone streaming through Silero VAD; speech segmentation creates tactical frames automatically without manual button presses.
