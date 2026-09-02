# iTANTRA — BLOCK 6 NEURAL TTS QUANTIZATION EVALUATION
## FP32 Baseline vs Dynamic INT8 Quantization

Evaluated on official lightweight VITS ONNX neural speech synthesis models using `onnxruntime.quantization` and `sherpa_onnx.OfflineTts` CPU inference.

| Language | Model Name | FP32 Size | INT8 Size | Reduction | FP32 Latency | INT8 Latency | Intelligibility | Decision |
|----------|------------|-----------|-----------|-----------|--------------|--------------|-----------------|----------|
| English (en) | vits-piper-en_US-lessac-medium | 60.27 MiB | 17.82 MiB | -70.4% | 184.8 ms | 192.4 ms | HIGH | USE INT8 |
| Hindi (hi) | vits-piper-hi_IN-pratham-medium | 60.22 MiB | 17.72 MiB | -70.6% | 110.7 ms | 134.2 ms | HIGH | USE INT8 |
| Telugu (te) | vits-piper-te_IN-maya-medium | 60.03 MiB | 17.49 MiB | -70.9% | 195.3 ms | 218.6 ms | HIGH | USE INT8 |
| Malayalam (ml) | vits-piper-ml_IN-meera-medium | 60.03 MiB | 17.49 MiB | -70.9% | 168.4 ms | 188.1 ms | HIGH | USE INT8 |

---

### Key Technical Findings:
1. **Model Footprint Savings**: Dynamic INT8 quantization shrinks VITS ONNX model weights from **60.1 MiB down to ~17.6 MiB per language** (average **70.7% size reduction**).
2. **Speech Intelligibility**: Synthesis audio across English, Hindi, Telugu, and Malayalam remains fully intelligible with valid sample rates (22,050 Hz) and intact duration contours.
3. **Preservation**: The original FP32 models (`*.onnx`) remain untouched alongside the optimized (`*.int8.onnx`) models.
