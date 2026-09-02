import os
import sys
import time
import json
import onnx
import onnxruntime.quantization as oq
import sherpa_onnx

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

MODELS_DIR = "app/tts/models"

TTS_MODELS = [
    {
        "lang": "en",
        "name": "vits-piper-en_US-lessac-medium",
        "fp32_onnx": "en_US-lessac-medium.onnx",
        "int8_onnx": "en_US-lessac-medium.int8.onnx",
        "test_text": "Meet me at checkpoint 4 for immediate tactical briefing."
    },
    {
        "lang": "hi",
        "name": "vits-piper-hi_IN-pratham-medium",
        "fp32_onnx": "hi_IN-pratham-medium.onnx",
        "int8_onnx": "hi_IN-pratham-medium.int8.onnx",
        "test_text": "चेकपॉइंट चार पर तुरंत रिपोर्ट करें।"
    },
    {
        "lang": "te",
        "name": "vits-piper-te_IN-maya-medium",
        "fp32_onnx": "te_IN-maya-medium.onnx",
        "int8_onnx": "te_IN-maya-medium.int8.onnx",
        "test_text": "వెంటనే చెక్‌పాయింట్ నాలుగుకి రిपोర్ట్ చేయండి."
    },
    {
        "lang": "ml",
        "name": "vits-piper-ml_IN-meera-medium",
        "fp32_onnx": "ml_IN-meera-medium.onnx",
        "int8_onnx": "ml_IN-meera-medium.int8.onnx",
        "test_text": "ചെക്ക്പോയിന്റ് നാലിലേക്ക് ഉടൻ റിപ്പോർട്ട് ചെയ്യുക."
    }
]

def quantize_model(model_info: dict) -> dict:
    folder = os.path.join(MODELS_DIR, model_info["name"])
    src_fp32 = os.path.join(folder, model_info["fp32_onnx"])
    dst_int8 = os.path.join(folder, model_info["int8_onnx"])
    tokens_path = os.path.join(folder, "tokens.txt")
    data_dir = os.path.join(folder, "espeak-ng-data")

    if not os.path.exists(src_fp32):
        print(f"[!] FP32 model not found at {src_fp32}")
        return {}

    fp32_size = os.path.getsize(src_fp32) / (1024 * 1024)
    print(f"\n[{model_info['lang'].upper()}] Quantizing {model_info['name']} (FP32: {fp32_size:.2f} MiB) -> INT8 ...")

    t0 = time.perf_counter()
    oq.quantize_dynamic(
        model_input=src_fp32,
        model_output=dst_int8,
        weight_type=oq.QuantType.QInt8,
        extra_options={"EnableShapeInference": False}
    )
    t_quant = time.perf_counter() - t0

    int8_size = os.path.getsize(dst_int8) / (1024 * 1024)
    reduction = ((fp32_size - int8_size) / fp32_size) * 100

    # Copy metadata properties from FP32 model to INT8 model
    m_src = onnx.load(src_fp32)
    m_dst = onnx.load(dst_int8)
    del m_dst.metadata_props[:]
    for p in m_src.metadata_props:
        entry = m_dst.metadata_props.add()
        entry.key = p.key
        entry.value = p.value
    onnx.save(m_dst, dst_int8)

    print(f"[{model_info['lang'].upper()}] INT8 Quantization Finished in {t_quant:.2f}s | Size: {int8_size:.2f} MiB ({reduction:.1f}% reduction)")

    # Verify synthesis
    cfg_int8 = sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(
            vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                model=dst_int8,
                tokens=tokens_path,
                data_dir=data_dir if os.path.exists(data_dir) else ""
            ),
            num_threads=2,
            provider="cpu"
        )
    )
    tts = sherpa_onnx.OfflineTts(cfg_int8)
    t_synth_start = time.perf_counter()
    audio = tts.generate(model_info["test_text"], sid=0, speed=1.0)
    t_synth = (time.perf_counter() - t_synth_start) * 1000

    dur = len(audio.samples) / audio.sample_rate if audio.sample_rate else 0.0
    print(f"[{model_info['lang'].upper()}] INT8 Synthesis Latency: {t_synth:.1f}ms | Audio Dur: {dur:.2f}s | Status: OK")

    return {
        "lang": model_info["lang"],
        "name": model_info["name"],
        "fp32_size_mib": fp32_size,
        "int8_size_mib": int8_size,
        "reduction_percent": reduction,
        "int8_latency_ms": t_synth,
        "audio_dur_s": dur
    }

def main():
    print("=" * 80)
    print("iTANTRA BLOCK 6 — NEURAL TTS INT8 QUANTIZATION PIPELINE")
    print("=" * 80)

    results = []
    for m in TTS_MODELS:
        res = quantize_model(m)
        if res:
            results.append(res)

    print("\n" + "=" * 80)
    print("TTS QUANTIZATION SUMMARY")
    print("=" * 80)
    for r in results:
        print(f"{r['lang'].upper()}: FP32 {r['fp32_size_mib']:.2f}MB -> INT8 {r['int8_size_mib']:.2f}MB (-{r['reduction_percent']:.1f}%) | Latency: {r['int8_latency_ms']:.1f}ms")

if __name__ == "__main__":
    main()
