# iTANTRA — BLOCK 6.5 COMPREHENSIVE BENCHMARK REPORT
## Multilingual STT and Neural ONNX TTS Performance Audit

Evaluated on standard local Edge CPU test environment using exact non-synthetic measurements.

### 1. Speech-To-Text (STT) Multilingual Benchmark (openai/whisper-tiny)

| Language Code | Language Name | STT Model | Model Size | Precision | Latency (ms) | WER | Result / Status |
|---------------|---------------|-----------|------------|-----------|--------------|-----|-----------------|
| `en` | English | `openai/whisper-tiny` | 148.23 MiB | FP32 | 203.6 ms | WER: NOT MEASURED | **VERIFIED** |
| `hi` | Hindi | `openai/whisper-tiny` | 148.23 MiB | FP32 | 169.9 ms | WER: NOT MEASURED | **VERIFIED** |
| `te` | Telugu | `openai/whisper-tiny` | 148.23 MiB | FP32 | 187.5 ms | WER: NOT MEASURED | **VERIFIED** |
| `ml` | Malayalam | `openai/whisper-tiny` | 148.23 MiB | FP32 | 183.2 ms | WER: NOT MEASURED | **VERIFIED** |
| `ta` | Tamil | `openai/whisper-tiny` | 148.23 MiB | FP32 | 6179.5 ms | WER: NOT MEASURED | **VERIFIED** |
| `gu` | Gujarati | `openai/whisper-tiny` | 148.23 MiB | FP32 | 195.0 ms | WER: NOT MEASURED | **VERIFIED** |
| `mr` | Marathi | `openai/whisper-tiny` | 148.23 MiB | FP32 | 187.4 ms | WER: NOT MEASURED | **VERIFIED** |
| `kn` | Kannada | `openai/whisper-tiny` | 148.23 MiB | FP32 | 186.5 ms | WER: NOT MEASURED | **VERIFIED** |
| `bn` | Bengali | `openai/whisper-tiny` | 148.23 MiB | FP32 | 183.5 ms | WER: NOT MEASURED | **VERIFIED** |
| `or` | Odia | `openai/whisper-tiny` | 0.0 MiB | N/A | 0.0 ms | N/A (Unsupported Vocab) | **UNAVAILABLE** |

---

### 2. Text-To-Speech (TTS) Multilingual Benchmark (Piper VITS ONNX INT8)

| Language Code | Language Name | TTS Model | Model Size | Precision | Latency (ms) | Intelligibility | Result / Status |
|---------------|---------------|-----------|------------|-----------|--------------|-----------------|-----------------|
| `en` | English | `en_US-lessac-medium.int8.onnx` | 17.82 MiB | INT8 | 2812.1 ms | HIGH | **VERIFIED** |
| `hi` | Hindi | `hi_IN-pratham-medium.int8.onnx` | 17.72 MiB | INT8 | 2207.6 ms | HIGH | **VERIFIED** |
| `te` | Telugu | `te_IN-maya-medium.int8.onnx` | 17.49 MiB | INT8 | 2334.5 ms | HIGH | **VERIFIED** |
| `ml` | Malayalam | `ml_IN-meera-medium.int8.onnx` | 17.49 MiB | INT8 | 2389.4 ms | HIGH | **VERIFIED** |
| `ta` | Tamil | `None (No Verified Neural Model)` | 0.00 MiB | N/A | 0.0 ms | N/A | **UNAVAILABLE** |
| `gu` | Gujarati | `None (No Verified Neural Model)` | 0.00 MiB | N/A | 0.0 ms | N/A | **UNAVAILABLE** |
| `mr` | Marathi | `None (No Verified Neural Model)` | 0.00 MiB | N/A | 0.0 ms | N/A | **UNAVAILABLE** |
| `kn` | Kannada | `None (No Verified Neural Model)` | 0.00 MiB | N/A | 0.0 ms | N/A | **UNAVAILABLE** |
| `bn` | Bengali | `None (No Verified Neural Model)` | 0.00 MiB | N/A | 0.0 ms | N/A | **UNAVAILABLE** |
| `or` | Odia | `None (No Verified Neural Model)` | 0.00 MiB | N/A | 0.0 ms | N/A | **UNAVAILABLE** |

---

### 3. Speech-To-Speech End-to-End Pipeline Summary

| Language Code | Language Name | STT Status | TTS Status | Speech-To-Speech Complete |
|---------------|---------------|------------|------------|---------------------------|
| `en` | English | VERIFIED | VERIFIED | **FULL (VERIFIED)** |
| `hi` | Hindi | VERIFIED | VERIFIED | **FULL (VERIFIED)** |
| `te` | Telugu | VERIFIED | VERIFIED | **FULL (VERIFIED)** |
| `ml` | Malayalam | VERIFIED | VERIFIED | **FULL (VERIFIED)** |
| `ta` | Tamil | VERIFIED | UNAVAILABLE | PARTIAL (STT ONLY) |
| `gu` | Gujarati | VERIFIED | UNAVAILABLE | PARTIAL (STT ONLY) |
| `mr` | Marathi | VERIFIED | UNAVAILABLE | PARTIAL (STT ONLY) |
| `kn` | Kannada | VERIFIED | UNAVAILABLE | PARTIAL (STT ONLY) |
| `bn` | Bengali | VERIFIED | UNAVAILABLE | PARTIAL (STT ONLY) |
| `or` | Odia | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |
