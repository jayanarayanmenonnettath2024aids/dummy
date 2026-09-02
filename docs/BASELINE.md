# iTantra — Baseline Technical Audit (Block 0)
**Smart India Hackathon 2026 — Problem Statement SIH26173**
*Date of Audit: September 2, 2026*

---

## 1. Executive Summary

This document establishes the baseline architecture, measurements, dependencies, limitations, and verification test results of the existing **iTantra** tactical neural walkie-talkie prototype prior to feature development (Block 0 Baseline Audit).

All **14 out of 14** existing unit and integration tests passed cleanly, and end-to-end speech transmission (`Speech → STT → Text JSON Packet → TCP Transport → Receiver → Offline TTS → Audio`) was successfully verified with ~99.8% bandwidth reduction compared to raw audio.

---

## 2. System Architecture & Component Mapping

The system implements an offline, internet-independent, low-bitrate tactical voice communication pipeline where spoken voice is transcribed to text on the transmitting node, transmitted across low-bandwidth data channels as a lightweight JSON packet, and synthesized back to voice on the receiver node.

```
+-----------------------------------------------------------------------------------+
|                              TRANSMITTER NODE (Device A)                           |
|                                                                                   |
|  [ Microphone / WAV Sample ]                                                      |
|             |                                                                     |
|             v (16kHz Mono Float32 Audio)                                          |
|  [ Local STT Engine: HuggingFace Transformers + OpenAI Whisper-Tiny ]             |
|             |                                                                     |
|             v (Text String + Timestamps)                                          |
|  [ iTantraPacket Framing & Telemetry Structuring ]                                |
|             |                                                                     |
|             v (4-Byte Length-Prefixed UTF-8 JSON Payload)                         |
|  [ TCPTransport / PeerTransceiver Client ]                                         |
+--------------------------------------|--------------------------------------------+
                                       |
                     [ TCP Socket / 802.11 / LAN / Radio ]
                                       |
+--------------------------------------v--------------------------------------------+
|                              RECEIVER NODE (Device B)                             |
|                                                                                   |
|  [ TCPTransport / PeerTransceiver Server Listener Thread (Port 65432) ]           |
|             |                                                                     |
|             v (Sends 1-byte 0x06 ACK, Parses iTantraPacket)                       |
|  [ Text & Metadata Extraction + Latency Telemetry Calculation ]                   |
|             |                                                                     |
|             v (Text Payload + Target Language)                                    |
|  [ Local TTS Engine: pyttsx3 (SAPI5 / System TTS Synthesizer) ]                   |
|             |                                                                     |
|             v (Synthesized WAV Audio Output)                                      |
|  [ Local Speaker Playback via sounddevice / soundfile ]                           |
+-----------------------------------------------------------------------------------+
```

### Component Breakdown

1. **Speech-to-Text (STT) Implementation (`app/stt/engine.py`):**
   - Class: `WhisperSTTEngine` implementing `BaseSTTEngine`.
   - Model: `openai/whisper-tiny` via HuggingFace `pipeline("automatic-speech-recognition")`.
   - Inference Device: CPU (torch float32).
   - Features: Audio preprocessing (mono conversion, 16kHz resampling via `scipy.signal.resample`), energy/RMS silence threshold gating (`rms < 0.003`), anti-hallucination regex cleaner, and `repetition_penalty=1.25`.
   - Audio Capture: Push-To-Talk dynamic recording stream via `sounddevice.InputStream`.

2. **Text-to-Speech (TTS) Implementation (`app/tts/engine.py`):**
   - Class: `Pyttsx3TTSEngine` (aliased as `LocalTTSEngine`) implementing `BaseTTSEngine`.
   - Engine: Offline native OS synthesizer via `pyttsx3` (Windows SAPI5 / macOS NSSpeechSynthesizer / Linux espeak).
   - Target Voice Matching: English and Tamil voice discovery by locale ID.
   - Execution: Saves synthesized audio to temporary WAV file and plays asynchronously/synchronously via `sounddevice` / `soundfile`.

3. **Packet Framing & Protocol (`app/communication/interface.py`):**
   - Class: `iTantraPacket`
   - Fields:
     - `ver`: Protocol version (default `"1.0"`)
     - `src`: Transmitting node identifier string (e.g., `"NODE-ALPHA"`)
     - `ses`: Session identifier UUID prefix
     - `seq`: Monotonically increasing sequence number
     - `lang`: Language code (`"en"`, `"ta"`)
     - `text`: Transcribed payload string
     - `audio_bytes`: Input audio byte size (for wire reduction telemetry)
     - `t1`: Capture start epoch timestamp
     - `t2`: STT finish epoch timestamp
     - `t3`: Transmission start epoch timestamp
     - `t4`: Reception finish epoch timestamp
     - `sec_tag`: Authentication / cryptographic tag placeholder

4. **Network Transport (`app/communication/tcp_transport.py` & `peer_transceiver.py`):**
   - Base Interface: `CommunicationInterface` (`send`, `receive`, `close`).
   - Transport: `TCPTransport` socket with 4-byte network-byte-order (`!I`) length prefix header and 1-byte `0x06` ACK reply.
   - Node Coordinator: `PeerTransceiver` runs a dedicated background listener daemon thread (`_listen_loop`) while allowing concurrent outgoing transmissions via `transmit()`.

5. **FastAPI Web Server & UI (`app/ui/server.py`, `app/ui/templates/index.html`, `app/ui/static/`):**
   - Framework: FastAPI + Uvicorn + WebSockets.
   - Endpoints:
     - `GET /`: Serves Mission Control HUD HTML dashboard.
     - `GET /api/status`: Node network state, local LAN IP, listening port, target peer IP/port.
     - `POST /api/connect`: Dynamic peer IP/port reconfiguration.
     - `POST /api/ptt/backend_start`: Triggers backend microphone capture stream.
     - `POST /api/ptt/backend_stop`: Stops capture, triggers STT inference, and transmits packet to peer.
     - `POST /api/send_audio_blob`: Ingests audio blob from browser WebRTC/MediaRecorder microphone.
     - `POST /api/send_sample`: Ingests pre-recorded tactical sample WAV files (`checkpoint`, `emergency`, `rescue`).
     - `POST /api/replay_tts`: Local audio resynthesis.
     - `GET /api/events`: Event history buffer.
     - `WebSocket /ws`: Real-time bidirectional telemetry streaming (transmission events, latencies, PTT state).

6. **CLI & Demo Launchers:**
   - `run_ui.py`: Launches FastAPI Web UI on configurable web and TCP ports with auto-detected LAN IP and optional auto-launching browser.
   - `run_demo.py`: Interactive and scriptable CLI launcher for local loop, transmitter node, and receiver node.

---

## 3. Dependencies & Hardware Baseline

- **Python Runtime:** Python 3.12 (CPython x86_64, Windows)
- **Core Dependencies:**
  - `torch >= 2.0.0`
  - `transformers >= 4.30.0`
  - `sounddevice >= 0.4.6`
  - `soundfile >= 0.12.1`
  - `scipy >= 1.10.0`
  - `pyttsx3 >= 2.90`
  - `colorama >= 0.4.6`
  - `numpy >= 1.24.0`
  - `fastapi >= 0.100.0`
  - `uvicorn[standard] >= 0.20.0`
  - `websockets >= 11.0.0`
  - `python-multipart >= 0.0.6`

### Model Footprint & Memory Accounting
- **STT Model Name:** `openai/whisper-tiny` (Single shared multilingual model)
- **Parameter Count:** 37,760,640 parameters (~37.76M parameters)
- **Weight Precision:** FP32 (Single precision float32, unquantized)
- **STT On-Disk File Size:** 144.06 MiB (151.06 MB) for `model.safetensors` (148.23 MiB / 155.43 MB total directory)
- **STT Runtime RAM Footprint:** 416.25 MiB total process RAM (+397.86 MiB additional RAM delta upon model load)
- **VAD Model (`silero_vad.onnx`):** 2.22 MiB on disk (~15.0 MiB runtime RAM)
- **TTS Model (`pyttsx3 / SAPI5`):** 0.00 MiB project disk (uses host OS system voices, ~0.01 MiB RAM delta)
- **Multilingual Architecture:** Single shared multilingual STT model serves all languages. There are NOT separate 151 MB model files per language.

---

## 4. Baseline Measurements & Benchmarks

Measured on local CPU runtime across tactical demo samples:

| Sample | Input Audio Size | Text Payload | Wire Packet Size | Wire Data Reduction | STT Latency | Net Latency (RTT) | TTS Latency | Total E2E Latency | E2E Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`checkpoint_en.wav`** | 102,544 bytes | 23 bytes | 248 bytes | **99.76%** | 799.94 ms | 1.24 ms | 409.56 ms | **1,210.74 ms** | **PASS** |
| **`emergency_en.wav`** | 137,816 bytes | 34 bytes | 259 bytes | **99.81%** | 708.75 ms | 17.83 ms | 188.71 ms | **915.29 ms** | **PASS** |
| **`rescue_en.wav`** | 123,046 bytes | 31 bytes | 255 bytes | **99.79%** | 741.15 ms | 21.49 ms | 133.47 ms | **896.10 ms** | **PASS** |

### Summary Averages
- **Average STT Latency:** ~749.9 ms
- **Average Network RTT Latency:** ~13.5 ms
- **Average TTS Latency:** ~243.9 ms
- **Average End-to-End Latency:** ~1,007.4 ms (~1.01 s)
- **Average Raw Audio Size:** ~121.1 KB
- **Average Transmitted Packet Size:** ~254 bytes
- **Bandwidth Reduction:** **> 99.7%**

---

## 5. Test Suite Verification Results

Command executed: `python -m unittest discover -s tests -v`

```text
test_empty_input_tts (test_edge_cases.TestEdgeCases.test_empty_input_tts) ... ok
test_long_input_payload (test_edge_cases.TestEdgeCases.test_long_input_payload) ... ok
test_malformed_packet_handling (test_edge_cases.TestEdgeCases.test_malformed_packet_handling) ... ok
test_receiver_unavailable_connection_failure (test_edge_cases.TestEdgeCases.test_receiver_unavailable_connection_failure) ... ok
test_unicode_tamil_packet (test_edge_cases.TestEdgeCases.test_unicode_tamil_packet) ... ok
test_metrics_calculation (test_metrics.TestMetrics.test_metrics_calculation) ... ok
test_stt_initialization (test_stt.TestSTTEngine.test_stt_initialization) ... ok
test_stt_transcription (test_stt.TestSTTEngine.test_stt_transcription) ... ok
test_bidirectional_transceiver_loop (test_transceiver.TestPeerTransceiver.test_bidirectional_transceiver_loop) ... ok
test_packet_serialization (test_transport.TestTCPTransport.test_packet_serialization) ... ok
test_tcp_send_receive_loop (test_transport.TestTCPTransport.test_tcp_send_receive_loop) ... ok
test_tts_initialization (test_tts.TestTTSEngine.test_tts_initialization) ... ok
test_tts_synthesis (test_tts.TestTTSEngine.test_tts_synthesis) ... ok
test_tts_unicode_tamil (test_tts.TestTTSEngine.test_tts_unicode_tamil) ... ok

----------------------------------------------------------------------
Ran 14 tests in 12.172s

OK (14 passed, 0 failed)
```

---

## 6. Current Baseline Limitations

1. **Manual IP Configuration:**
   - The user must manually input or provide CLI flags for the remote peer's IP and port (`--peer-host` / `POST /api/connect`). No auto-discovery (mDNS / UDP broadcast beacon) is currently present.
2. **Point-to-Point Single-Peer Link:**
   - Transmissions target a single destination address (`peer_host` / `peer_port`). No multi-node mesh, group channel, or broadcast tree exists yet.
3. **Transport Layer:**
   - Currently uses TCP with single-connection handshakes. Packet loss recovery on intermittent tactical wireless links (e.g. UDP with FEC or LoRa packetization) is not yet implemented.
4. **Security & Cryptography:**
   - Packet framing has a placeholder `sec_tag`, but payloads and metadata are unencrypted and unauthenticated in transit.
5. **Speech Synthesis Quality & Accents:**
   - `pyttsx3` relies on the host OS's default SAPI5 / platform TTS voices, which have varying quality across different operating systems.
6. **STT Model Footprint:**
   - Whisper-tiny runs on PyTorch CPU taking ~750ms inference time per 3-4s phrase. Further quantization (e.g., INT8 / ONNX / faster-whisper) could accelerate inference.

---

## 7. Audit Conclusion

The baseline application is fully functional, all 14 tests pass, and zero modifications to core business logic were required. The environment is verified and ready for subsequent feature blocks.
