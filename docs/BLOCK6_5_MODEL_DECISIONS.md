# iTANTRA — BLOCK 6.5 FINAL MODEL DECISIONS & ARCHITECTURAL FREEZE

## Architectural Decision: OPTION A
**Single Shared Multilingual STT (`openai/whisper-tiny`) + Language-Specific Modular Neural ONNX TTS Models (`vits-piper-*`)**.

### Justification:
1. **Model Footprint Efficiency**: The multilingual STT model (`openai/whisper-tiny` 148.23 MiB) is shared across 9 languages without duplicating weights.
2. **Modular Edge Packaging**: Individual neural TTS voices (17.5 MiB each in INT8) can be dynamically packaged or downloaded on-demand per node configuration without loading monolithic gigabyte-scale multilingual voice models.
3. **Low Dynamic RAM**: CPU inference consumes <400 MiB RAM, satisfying strict mobile edge requirements.

---

## Language-by-Language Model Decisions

### 1. English (`en`)
- **STT**: `openai/whisper-tiny` $\rightarrow$ **KEEP CURRENT (FP32)**
- **TTS**: `vits-piper-en_US-lessac-medium` $\rightarrow$ **KEEP CURRENT (INT8)**
- **Status**: **VERIFIED COMPLETE SPEECH-TO-SPEECH**

### 2. Hindi (`hi`)
- **STT**: `openai/whisper-tiny` $\rightarrow$ **KEEP CURRENT (FP32)**
- **TTS**: `vits-piper-hi_IN-pratham-medium` $\rightarrow$ **KEEP CURRENT (INT8)**
- **Status**: **VERIFIED COMPLETE SPEECH-TO-SPEECH**

### 3. Telugu (`te`)
- **STT**: `openai/whisper-tiny` $\rightarrow$ **KEEP CURRENT (FP32)**
- **TTS**: `vits-piper-te_IN-maya-medium` $\rightarrow$ **ADD MODEL (INT8)**
- **Status**: **VERIFIED COMPLETE SPEECH-TO-SPEECH**

### 4. Malayalam (`ml`)
- **STT**: `openai/whisper-tiny` $\rightarrow$ **KEEP CURRENT (FP32)**
- **TTS**: `vits-piper-ml_IN-meera-medium` $\rightarrow$ **ADD MODEL (INT8)**
- **Status**: **VERIFIED COMPLETE SPEECH-TO-SPEECH**

### 5. Tamil (`ta`)
- **STT**: `openai/whisper-tiny` $\rightarrow$ **KEEP CURRENT (FP32)**
- **TTS**: No verified lightweight offline Piper ONNX model released $\rightarrow$ **NO VERIFIED SUITABLE MODEL**
- **Status**: **PARTIAL (STT ONLY)**

### 6. Gujarati (`gu`)
- **STT**: `openai/whisper-tiny` $\rightarrow$ **KEEP CURRENT (FP32)**
- **TTS**: No verified lightweight offline Piper ONNX model released $\rightarrow$ **NO VERIFIED SUITABLE MODEL**
- **Status**: **PARTIAL (STT ONLY)**

### 7. Marathi (`mr`)
- **STT**: `openai/whisper-tiny` $\rightarrow$ **KEEP CURRENT (FP32)**
- **TTS**: Google Piper model requires multi-char IPA dictionary parser $\rightarrow$ **NO VERIFIED SUITABLE MODEL**
- **Status**: **PARTIAL (STT ONLY)**

### 8. Kannada (`kn`)
- **STT**: `openai/whisper-tiny` $\rightarrow$ **KEEP CURRENT (FP32)**
- **TTS**: No verified lightweight offline Piper ONNX model released $\rightarrow$ **NO VERIFIED SUITABLE MODEL**
- **Status**: **PARTIAL (STT ONLY)**

### 9. Bengali (`bn`)
- **STT**: `openai/whisper-tiny` $\rightarrow$ **KEEP CURRENT (FP32)**
- **TTS**: Google Piper model requires multi-char IPA dictionary parser $\rightarrow$ **NO VERIFIED SUITABLE MODEL**
- **Status**: **PARTIAL (STT ONLY)**

### 10. Odia (`or`)
- **STT**: Missing in Whisper-tiny vocabulary; alternative Indic models exceed edge budget (>1 GB) $\rightarrow$ **NO VERIFIED SUITABLE MODEL**
- **TTS**: No verified lightweight offline Piper ONNX model released $\rightarrow$ **NO VERIFIED SUITABLE MODEL**
- **Status**: **UNAVAILABLE**
