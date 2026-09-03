# iTANTRA — BLOCK 9.5 EXPANDED LANGUAGE STATUS MATRIX

## 1. Complete 10-Language Production Capability Matrix

| Language | ISO Code | STT Engine | STT Status | TTS Engine | TTS Status | Precision | Classification | Quality Gate |
|----------|----------|------------|------------|------------|------------|-----------|----------------|--------------|
| **English** | `en` | `whisper-tiny` | **VERIFIED** | `vits-piper-en_US-lessac` | **VERIFIED** | INT8 | **SUPPORTED + VERIFIED** | 🟢 FULLY VERIFIED |
| **Hindi** | `hi` | `whisper-tiny` | **VERIFIED** | `vits-piper-hi_IN-pratham` | **VERIFIED** | INT8 | **SUPPORTED + VERIFIED** | 🟢 FULLY VERIFIED |
| **Telugu** | `te` | `whisper-tiny` | **VERIFIED** | `vits-piper-te_IN-maya` | **VERIFIED** | INT8 | **SUPPORTED + VERIFIED** | 🟢 FULLY VERIFIED |
| **Malayalam** | `ml` | `whisper-tiny` | **VERIFIED** | `vits-piper-ml_IN-meera` | **VERIFIED** | INT8 | **SUPPORTED + VERIFIED** | 🟢 FULLY VERIFIED |
| **Tamil** | `ta` | `whisper-tiny` | **VERIFIED** | `vits_rasa_13` | **VERIFIED** | FP32 | **SUPPORTED + VERIFIED** | 🟢 FULLY VERIFIED |
| **Kannada** | `kn` | `whisper-tiny` | **VERIFIED** | `vits_rasa_13` | **VERIFIED** | FP32 | **SUPPORTED + VERIFIED** | 🟢 FULLY VERIFIED |
| **Marathi** | `mr` | `whisper-tiny` | **VERIFIED** | `vits_rasa_13` | **VERIFIED** | FP32 | **SUPPORTED + VERIFIED** | 🟢 FULLY VERIFIED |
| **Bengali** | `bn` | `whisper-tiny` | **VERIFIED** | `vits_rasa_13` | **VERIFIED** | FP32 | **SUPPORTED + VERIFIED** | 🟢 FULLY VERIFIED |
| **Gujarati** | `gu` | `whisper-tiny` | **VERIFIED** | None | UNAVAILABLE | — | **STT ONLY** | 🟡 TTS PENDING |
| **Odia** | `or` | None | UNAVAILABLE | None | UNAVAILABLE | — | **DEFERRED** | 🔴 DEFERRED |

---

## 2. Summary of Progress
- **Full Speech-to-Speech (STT + Neural TTS)**: **8 of 10 Languages** (`en`, `hi`, `te`, `ml`, `ta`, `kn`, `mr`, `bn`).
- **Speech-to-Text Only**: **1 Language** (`gu`).
- **Deferred / Unsupported Vocab**: **1 Language** (`or`).
