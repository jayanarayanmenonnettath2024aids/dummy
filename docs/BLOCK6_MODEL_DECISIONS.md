# iTANTRA — BLOCK 6 MODEL SELECTION & QUALITY GATE DECISIONS

## Decision Criteria & Quality Gates
Every model candidate is evaluated across:
1. **Accuracy / Intelligibility Gate**: STT must preserve word sequences; TTS must produce clear intelligible audio without acoustic artifacts.
2. **Disk Footprint**: Must minimize on-device storage for eventual Android packaging.
3. **Runtime RAM**: Must fit within constrained edge device budgets.
4. **Offline Portability**: 100% local CPU execution without cloud APIs, SAPI5, or pyttsx3.

---

## Final Model Decisions

### 1. Speech-To-Text (STT)

| Component | Model Candidate | FP32 Size | INT8 Size | Accuracy Gate | Decision | Rationale |
|-----------|-----------------|-----------|-----------|---------------|----------|-----------|
| **Multilingual STT** | `openai/whisper-tiny` | 148.23 MiB | 115.90 MiB | FP32 Passed / INT8 Degraded | **KEEP FP32** | FP32 retains accurate attention sequence across 9 languages. INT8 linear quantization degraded phonetic beam search. |

---

### 2. Text-To-Speech (TTS)

| Language | Model Candidate | FP32 Size | INT8 Size | Intelligibility Gate | Decision | Rationale |
|----------|-----------------|-----------|-----------|----------------------|----------|-----------|
| **English (en)** | `vits-piper-en_US-lessac-medium` | 60.27 MiB | 17.82 MiB | PASSED (High) | **USE INT8** | 70.4% disk reduction, excellent audio clarity, fast synthesis latency. |
| **Hindi (hi)** | `vits-piper-hi_IN-pratham-medium` | 60.22 MiB | 17.72 MiB | PASSED (High) | **USE INT8** | 70.6% disk reduction, native Indic phoneme support, clean acoustic waveform. |
| **Telugu (te)** | `vits-piper-te_IN-maya-medium` | 60.03 MiB | 17.49 MiB | PASSED (High) | **USE INT8** | 70.9% disk reduction, verified offline VITS synthesis. |
| **Malayalam (ml)** | `vits-piper-ml_IN-meera-medium` | 60.03 MiB | 17.49 MiB | PASSED (High) | **USE INT8** | 70.9% disk reduction, verified offline VITS synthesis. |
| **Marathi (mr)** | `vits-piper-mr_IN-google-medium` | 73.21 MiB | - | PARTIAL | **CANDIDATE** | Official Google Piper model requires multi-char IPA dictionary parser. |
| **Bengali (bn)** | `vits-piper-bn_BD-google-medium` | 73.23 MiB | - | PARTIAL | **CANDIDATE** | Official Google Piper model requires multi-char IPA dictionary parser. |
| **Tamil (ta)** | Unreleased in Piper ONNX | - | - | UNAVAILABLE | **NO SUITABLE VERIFIED MODEL FOUND** | Explicitly reported; zero cloud/SAPI5 fallback. |
| **Gujarati (gu)** | Unreleased in Piper ONNX | - | - | UNAVAILABLE | **NO SUITABLE VERIFIED MODEL FOUND** | Explicitly reported; zero cloud/SAPI5 fallback. |
| **Kannada (kn)** | Unreleased in Piper ONNX | - | - | UNAVAILABLE | **NO SUITABLE VERIFIED MODEL FOUND** | Explicitly reported; zero cloud/SAPI5 fallback. |
| **Odia (or)** | Unreleased in Piper ONNX | - | - | UNAVAILABLE | **NO SUITABLE VERIFIED MODEL FOUND** | Explicitly reported; zero cloud/SAPI5 fallback. |

---

### 3. Voice Activity Detection (VAD)

| Component | Model Candidate | Disk Size | Precision | Decision | Rationale |
|-----------|-----------------|-----------|-----------|----------|-----------|
| **Streaming VAD** | `silero_vad.onnx` | 2.22 MiB | FP32 | **KEEP FP32** | Highly lightweight (2.22 MiB) with sub-millisecond (0.26 ms) chunk processing. |
