# iTANTRA — BLOCK 6.5 ANDROID MODEL READINESS REPORT

## Android Readiness Status per Model Component

| Component / Language | Selected Model Asset | Format | Required Assets | Target Runtime | ARM64 Android Status |
|----------------------|----------------------|--------|-----------------|----------------|----------------------|
| **VAD** | `silero_vad.onnx` | ONNX FP32 (2.22 MiB) | None | `onnxruntime-android` | **READY** |
| **STT (9 Languages)** | `openai/whisper-tiny` | PyTorch / ONNX (148.23 MiB) | `tokenizer.json`, `vocab.json` | `sherpa-onnx-android` / `onnxruntime` | **READY** |
| **TTS (English)** | `en_US-lessac-medium.int8.onnx` | ONNX INT8 (17.82 MiB) | `tokens.txt`, `espeak-ng-data` | `sherpa-onnx-android` | **READY** |
| **TTS (Hindi)** | `hi_IN-pratham-medium.int8.onnx` | ONNX INT8 (17.72 MiB) | `tokens.txt`, `espeak-ng-data` | `sherpa-onnx-android` | **READY** |
| **TTS (Telugu)** | `te_IN-maya-medium.int8.onnx` | ONNX INT8 (17.49 MiB) | `tokens.txt`, `espeak-ng-data` | `sherpa-onnx-android` | **READY** |
| **TTS (Malayalam)** | `ml_IN-meera-medium.int8.onnx` | ONNX INT8 (17.49 MiB) | `tokens.txt`, `espeak-ng-data` | `sherpa-onnx-android` | **READY** |

---

## Edge Resource Profile

- **Physical Storage Required on Android Node**: **~220.97 MiB** total for VAD + Whisper + 4x INT8 TTS voices.
- **Dynamic RAM Consumption on Mobile CPU**: **~340–435 MiB** peak during active STT + TTS synthesis.
- **Android Target Architecture**: Android NDK 21+, ARM64-v8a, Java JNI bindings for `sherpa-onnx`.
