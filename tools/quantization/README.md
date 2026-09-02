# iTantra Quantization & Edge Optimization Suite

This directory contains scripts for benchmarking, evaluating, and quantizing Edge AI models for iTantra.

## Scripts Overview

- `benchmark_baseline.py`: Runs baseline measurement for FP32 STT (`openai/whisper-tiny`), TTS (`en_US`, `hi_IN`), and VAD (`silero_vad.onnx`).
- `benchmark_stt_multilingual.py`: Tests `openai/whisper-tiny` on all 10 Problem Statement languages.
- `benchmark_tts_multilingual.py`: Evaluates offline local VITS ONNX neural speech models across languages.
- `quantize_tts.py`: Quantizes FP32 VITS models to INT8 ONNX (`*.int8.onnx`), preserving all metadata properties.
- `quantize_stt.py`: Evaluates dynamic quantization on Whisper-tiny STT.
- `benchmark_models.py`: Runs side-by-side comparison of FP32 vs INT8 models.

## Usage

```bash
# 1. Benchmark FP32 Baseline
python tools/quantization/benchmark_baseline.py

# 2. Benchmark Multilingual STT
python tools/quantization/benchmark_stt_multilingual.py

# 3. Quantize TTS Models to INT8
python tools/quantization/quantize_tts.py

# 4. Compare FP32 vs INT8
python tools/quantization/benchmark_models.py
```
