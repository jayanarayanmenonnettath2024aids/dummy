# iTANTRA — BLOCK 9.5 ANDROID MODEL READINESS REPORT

## 1. Executive Summary

The **AI4Bharat VITS-RASA ONNX** model (`model.onnx`, 117.62 MiB) is evaluated as **ANDROID CANDIDATE (HIGH FEASIBILITY)** for deployment on mobile edge hardware via `sherpa-onnx` Android AAR / JNI bindings.

---

## 2. Model Properties & Execution Requirements

- **Framework**: `sherpa-onnx` C++ Core with ONNX Runtime Mobile backend.
- **Model Files Required**:
  - `model.onnx` (117.62 MiB)
  - `tokens.txt` (9.5 KiB)
- **Runtime Dependencies**: Zero Python runtime required. Pure C++ / JNI execution.
- **Token Processing**: Direct UTF-8 character index lookup (no complex IPA / eSpeak-NG C++ rules required).
- **Target OS**: Android 9.0+ (API level 28+), `arm64-v8a` architecture.
- **Memory Footprint**: `~120–160 MiB` peak RSS during active synthesis.

---

## 3. Comparative Architecture Overview for Android Port

| Subsystem | Android Implementation Path | Desktop Reference Equivalent |
|-----------|-----------------------------|------------------------------|
| **VAD** | `sherpa-onnx` Silero VAD C++ | `app/vad/silero_vad.py` |
| **STT** | `sherpa-onnx` Whisper C++ | `app/stt/engine.py` |
| **TTS (English, Hindi, etc.)** | `sherpa-onnx` Piper VITS INT8 | `app/tts/engine.py` |
| **TTS (Tamil, Kannada, etc.)** | `sherpa-onnx` VITS-RASA FP32 | `app/tts/vits_rasa_engine.py` |
| **Security & Protocol** | `iTantraPacketV2` + `HMAC-SHA256` (Java/Kotlin) | `app/communication/packet_v2.py` |
