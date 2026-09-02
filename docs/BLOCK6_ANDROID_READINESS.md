# iTANTRA — BLOCK 6 ANDROID READINESS EVALUATION
## Edge Portability & Runtime Compatibility Audit

> [!NOTE]
> Android APK build is scheduled for a subsequent dedicated phase. This document audits technical portability, operator compatibility, and runtime asset requirements.

---

### 1. Model Format and Portability Matrix

| Component | Selected Model | Format | Required External Assets | Operators Used | ARM64 / Android Feasibility | Sherpa-ONNX / ONNX Runtime Mobile Compatibility |
|-----------|----------------|--------|--------------------------|----------------|-----------------------------|--------------------------------------------------|
| **VAD** | `silero_vad.onnx` | ONNX (FP32) | None (Single file) | Conv1d, LSTM, MatMul, Relu | **READY** | Full native support via `onnxruntime-android` / `sherpa-onnx`. |
| **STT** | `openai/whisper-tiny` | PyTorch / ONNX | `vocab.json`, `tokenizer.json` | MatMul, LayerNorm, MultiHeadAttention, Softmax | **READY** | Standard architecture directly exportable to ONNX or runnable via Sherpa-ONNX offline Whisper. |
| **TTS (English)** | `vits-piper-en_US-lessac-medium` | ONNX (INT8 / FP32) | `tokens.txt`, `espeak-ng-data` | Conv1d, ConvTranspose1d, Relu, Softplus | **READY** | Native support in `sherpa-onnx-android` with C++ JNI bindings. |
| **TTS (Hindi)** | `vits-piper-hi_IN-pratham-medium` | ONNX (INT8 / FP32) | `tokens.txt`, `espeak-ng-data` | Conv1d, ConvTranspose1d, Relu, Softplus | **READY** | Native support in `sherpa-onnx-android` with C++ JNI bindings. |
| **TTS (Telugu)** | `vits-piper-te_IN-maya-medium` | ONNX (INT8 / FP32) | `tokens.txt`, `espeak-ng-data` | Conv1d, ConvTranspose1d, Relu, Softplus | **READY** | Native support in `sherpa-onnx-android` with C++ JNI bindings. |
| **TTS (Malayalam)** | `vits-piper-ml_IN-meera-medium` | ONNX (INT8 / FP32) | `tokens.txt`, `espeak-ng-data` | Conv1d, ConvTranspose1d, Relu, Softplus | **READY** | Native support in `sherpa-onnx-android` with C++ JNI bindings. |

---

### 2. Android Deployment Resource Budget

- **Total Selected Models Disk Footprint**:
  - `openai/whisper-tiny` (STT): 148.23 MiB
  - `silero_vad.onnx` (VAD): 2.22 MiB
  - 4x Quantized INT8 TTS (`en`, `hi`, `te`, `ml`): ~70.52 MiB (17.6 MiB each)
  - **Total Offline Storage on Android**: **~220.97 MiB** (easily fits within standard Android APK/OBB asset limits).
- **Estimated Runtime RAM on ARM64**:
  - STT inference: ~280–350 MiB
  - TTS synthesis: ~45–65 MiB
  - VAD streaming: ~15–20 MiB
  - **Total Dynamic RAM**: **~340–435 MiB** (well within typical 2GB–4GB Android hardware specifications).

---

### 3. Conclusion

**STATUS: READY FOR ANDROID PHASE**
- All production models execute via standard ONNX CPU operators supported by ONNX Runtime Mobile and Sherpa-ONNX C++ Android runtime.
- Zero dependencies on Windows APIs, desktop voices, or cloud endpoints.
