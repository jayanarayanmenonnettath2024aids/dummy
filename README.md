# iTantra: Offline Low-Data-Rate Speech-to-Speech Communication System
**Smart India Hackathon 2026 — Problem Statement SIH26173 (Round-1 Prototype)**

---

## 1. Executive Summary & Problem Statement

Conventional voice communication systems transmit continuous raw or compressed audio streams, consuming between **16 kbps to 64+ kbps** of bandwidth. In remote tactical zones, disaster relief operations, maritime environments, or severely constrained wireless links (e.g., HF/VHF radio, LoRa, satellite IoT), high-bandwidth links are either unavailable, jammed, or cost-prohibitive.

**iTantra** resolves this challenge with an edge-first neural paradigm:
```
[Speaker] 
   └──> Local Edge STT (Speech-to-Text)
           └──> Compressed Text / Semantic Data Payload (~20–40 Bytes)
                   └──> Constrained Network Transport (TCP / Wi-Fi / Radio / LoRa)
                           └──> Local Edge TTS (Text-to-Speech)
                                   └──> [Synthesized Speech Output]
```

### Key Highlights
- **>99.7% Bandwidth Reduction**: Transmits only text/metadata payloads (~30 bytes) instead of 100+ KB audio frames.
- **100% Offline & Edge-Native**: Operates without internet connectivity or cloud APIs (OpenAI, Google, Azure, AWS, ElevenLabs).
- **Sub-Second End-to-End Latency**: Measured ~750–850 ms total pipeline latency on standard CPU hardware.
- **Transport Independence**: Decoupled transport layer ready for Wi-Fi, Ethernet, Bluetooth, Serial, LoRa, or custom transceivers.

---

## 2. System Architecture

```
+-----------------------------------------------------------------------------------+
|                                  DEVICE A (Transmitter)                           |
|  [Microphone / Sample] ──> [Pre-processing] ──> [Whisper-Tiny STT] ──> [Packetizer]  |
+-----------------------------------------------------------------------------------+
                                          │
                        [iTantra Packet: ~250-280 bytes]
                        (Raw Text: 20-40 bytes, No Audio)
                                          │
                                          ▼
                               [Transport Layer: TCP / LAN]
                                          │
                                          ▼
+-----------------------------------------------------------------------------------+
|                                  DEVICE B (Receiver)                              |
|  [TCP Listener] ──> [Depacketizer & Telemetry] ──> [Local Neural TTS] ──> [Speaker] |
+-----------------------------------------------------------------------------------+
```

### Packet Format Specification (`iTantraPacket`)
```json
{
  "ver": "1.0",
  "src": "NODE-A",
  "ses": "a3f89e21",
  "seq": 1,
  "lang": "en",
  "text": "Emergency team report to sector four.",
  "audio_bytes": 137816,
  "t1": 1725080000.120,
  "t2": 1725080000.687,
  "t3": 1725080000.700,
  "t4": 1725080000.718,
  "sec_tag": "FUTURE_SECURITY_TAG_PLACEHOLDER"
}
```

---

## 3. Real Measured Benchmark Results

*Measured on Windows 11 Intel CPU (Zero GPU/CUDA acceleration used)*:

| Metric | Raw Audio Stream | iTantra Payload | Reduction / Impact |
|---|---|---|---|
| **Payload Size (4s speech)** | 137,816 bytes | 34 bytes (Raw) / 284 bytes (Frame) | **99.98% (Text) / 99.78% (Wire)** |
| **STT Latency** | N/A | 567.9 ms | Local inference |
| **Network Latency** | ~200–500 ms (Audio stream) | 18.3 ms | Single packet frame |
| **TTS Latency** | N/A | 182.6 ms | Local synthesis |
| **Total End-to-End Latency**| Stream dependent | **750.5 ms – 838.1 ms** | **Sub-second neural loop** |
| **Internet Dependency** | Cloud API required | **NONE (100% Offline)** | Works in air-gapped setups |

---

## 4. Project Structure

```
iTantra/
├── app/
│   ├── stt/
│   │   ├── __init__.py
│   │   └── engine.py             # Whisper-tiny STT engine & microphone capture
│   ├── tts/
│   │   ├── __init__.py
│   │   └── engine.py             # Local offline TTS engine & playback
│   ├── communication/
│   │   ├── __init__.py
│   │   ├── interface.py          # Abstract Transport Interface & iTantraPacket
│   │   └── tcp_transport.py      # TCP Socket Transport implementation
│   ├── metrics/
│   │   ├── __init__.py
│   │   └── metrics.py            # Latency, Bandwidth comparison & CLI Dashboard
│   └── demo/
│       ├── __init__.py
│       └── demo.py               # Local loop, Transmitter, and Receiver orchestration
├── samples/
│   ├── checkpoint_en.wav         # "Meet me at checkpoint four."
│   ├── emergency_en.wav          # "Emergency team report to sector four."
│   └── rescue_en.wav             # "Supplies dispatched to base camp."
├── tests/
│   ├── __init__.py
│   ├── test_stt.py               # STT unit tests
│   ├── test_tts.py               # TTS unit tests
│   ├── test_transport.py         # Network socket & serialization tests
│   ├── test_metrics.py           # Bandwidth & latency calculation tests
│   └── test_edge_cases.py        # Empty input, Unicode/Tamil, connection failure
├── requirements.txt              # Dependency specifications
├── run_demo.py                   # Main CLI Entry point and Interactive Menu
└── README.md                     # Documentation
```

---

## 5. Quick Start & Execution Guide

### 5.1 Installation
```bash
pip install -r requirements.txt
```

### 5.2 Running the Interactive Demo Menu
Simply execute:
```bash
python run_demo.py
```
This presents a menu to select:
1. **Single Node Local Loop**: Mic/Sample → STT → TTS → Speaker
2. **Transmitter Node (Device A)**: Mic/Sample → STT → Network Packet
3. **Receiver Node (Device B)**: Network Packet → TTS → Speaker
4. **Run Unit & Integration Test Suite**

---

### 5.3 Command Line Modes

#### Mode 1: Single Node Neural Voice Loop (Fallback Sample)
```bash
python run_demo.py --mode local --source fallback --sample samples/emergency_en.wav
```

#### Mode 2: Single Node Neural Voice Loop (Live Microphone)
```bash
python run_demo.py --mode local --source live
```

#### Mode 3: Two-Device / Two-Process Distributed Demonstration
**Step 1: Start Receiver Node (Device B):**
```bash
python run_demo.py --mode rx --port 65432
```

**Step 2: Start Transmitter Node (Device A):**
```bash
# On Device A (replace 127.0.0.1 with Device B's local LAN IP if running across physical laptops):
python run_demo.py --mode tx --host 127.0.0.1 --port 65432 --source fallback --sample samples/checkpoint_en.wav
```

---

## 6. Running Automated Verification Tests

Run the full automated test suite covering STT, TTS, TCP transport, latency metrics, and edge cases (empty strings, Tamil Unicode, packet corruption, connection timeouts):
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## 7. Future Roadmap (Round-2 & Beyond)

1. **Multilingual Expansion**: Scale to 10 scheduled Indian languages using fine-tuned IndicWhisper and IndicTTS models.
2. **Model Distillation & Quantization**: Quantize STT/TTS models to INT8/INT4 using ONNX Runtime and llama.cpp for <100MB RAM footprints.
3. **Android & Embedded Edge Deployment**: Package pipeline into Android NDK / C++ runtime for tactical handhelds.
4. **Constrained Transceivers**: Interface directly with LoRa SX1262 and VHF/UHF tactical radio transceivers via UART/SPI.
5. **End-to-End Cryptography**: Implement AES-256-GCM authenticated payload encryption and ECDSA packet signing.
6. **Store-and-Forward Mesh**: Implement delay-tolerant mesh packet routing for multi-hop tactical networks.
