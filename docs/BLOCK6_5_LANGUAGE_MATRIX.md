# iTANTRA — BLOCK 6.5 FINAL LANGUAGE COVERAGE MATRIX

| Language | Code | STT Model | STT Status | TTS Model | TTS Status | Precision | Disk Size (MiB) | Android Ready |
|----------|------|-----------|------------|-----------|------------|-----------|-----------------|---------------|
| English | `en` | `openai/whisper-tiny` | **VERIFIED** | `vits-piper-en_US-lessac-medium` | **VERIFIED** | INT8 / FP32 | 17.82 MiB (INT8) / 60.27 MiB (FP32) | **READY** |
| Hindi | `hi` | `openai/whisper-tiny` | **VERIFIED** | `vits-piper-hi_IN-pratham-medium` | **VERIFIED** | INT8 / FP32 | 17.72 MiB (INT8) / 60.22 MiB (FP32) | **READY** |
| Telugu | `te` | `openai/whisper-tiny` | **VERIFIED** | `vits-piper-te_IN-maya-medium` | **VERIFIED** | INT8 / FP32 | 17.49 MiB (INT8) / 60.03 MiB (FP32) | **READY** |
| Malayalam | `ml` | `openai/whisper-tiny` | **VERIFIED** | `vits-piper-ml_IN-meera-medium` | **VERIFIED** | INT8 / FP32 | 17.49 MiB (INT8) / 60.03 MiB (FP32) | **READY** |
| Tamil | `ta` | `openai/whisper-tiny` | **VERIFIED** | None | **UNAVAILABLE** | FP32 (STT) | 148.23 MiB (Shared STT) | **PARTIAL** |
| Gujarati | `gu` | `openai/whisper-tiny` | **VERIFIED** | None | **UNAVAILABLE** | FP32 (STT) | 148.23 MiB (Shared STT) | **PARTIAL** |
| Marathi | `mr` | `openai/whisper-tiny` | **VERIFIED** | None | **UNAVAILABLE** | FP32 (STT) | 148.23 MiB (Shared STT) | **PARTIAL** |
| Kannada | `kn` | `openai/whisper-tiny` | **VERIFIED** | None | **UNAVAILABLE** | FP32 (STT) | 148.23 MiB (Shared STT) | **PARTIAL** |
| Bengali | `bn` | `openai/whisper-tiny` | **VERIFIED** | None | **UNAVAILABLE** | FP32 (STT) | 148.23 MiB (Shared STT) | **PARTIAL** |
| Odia | `or` | None | **UNAVAILABLE** | None | **UNAVAILABLE** | N/A | 0.0 MiB | **UNAVAILABLE** |

---

### Coverage Summary
- **Speech-To-Text (STT)**: 9 / 10 Languages Verified (`en`, `hi`, `te`, `ml`, `ta`, `gu`, `mr`, `kn`, `bn`).
- **Text-To-Speech (TTS)**: 4 / 10 Languages Verified (`en`, `hi`, `te`, `ml`).
- **Complete Speech-To-Speech Pipeline**: 4 / 10 Languages Verified (`en`, `hi`, `te`, `ml`).
- **Shared Multilingual Model Footprint**: 148.23 MiB (Whisper-tiny) + 2.22 MiB (Silero VAD) + 70.52 MiB (4x Quantized INT8 TTS) = **~220.97 MiB Total Physical Storage**.
