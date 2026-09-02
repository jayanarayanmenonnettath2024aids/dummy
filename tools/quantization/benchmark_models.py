import os
import sys
import time
import psutil
import sherpa_onnx
import soundfile as sf

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def get_process_ram_mib():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)

MODELS = [
    {
        "lang": "en",
        "name": "English (lessac-medium)",
        "folder": "vits-piper-en_US-lessac-medium",
        "fp32": "en_US-lessac-medium.onnx",
        "int8": "en_US-lessac-medium.int8.onnx",
        "text": "Meet me at checkpoint 4 for immediate tactical briefing."
    },
    {
        "lang": "hi",
        "name": "Hindi (pratham-medium)",
        "folder": "vits-piper-hi_IN-pratham-medium",
        "fp32": "hi_IN-pratham-medium.onnx",
        "int8": "hi_IN-pratham-medium.int8.onnx",
        "text": "चेकपॉइंट चार पर तुरंत रिपोर्ट करें।"
    },
    {
        "lang": "te",
        "name": "Telugu (maya-medium)",
        "folder": "vits-piper-te_IN-maya-medium",
        "fp32": "te_IN-maya-medium.onnx",
        "int8": "te_IN-maya-medium.int8.onnx",
        "text": "వెంటనే చెక్‌పాయింట్ నాలుగుకి రిపోర్ట్ చేయండి."
    },
    {
        "lang": "ml",
        "name": "Malayalam (meera-medium)",
        "folder": "vits-piper-ml_IN-meera-medium",
        "fp32": "ml_IN-meera-medium.onnx",
        "int8": "ml_IN-meera-medium.int8.onnx",
        "text": "ചെക്ക്പോയിന്റ് നാലിലേക്ക് ഉടൻ റിപ്പോർട്ട് ചെയ്യുക."
    }
]

def benchmark_single(model_path: str, tokens_path: str, data_dir: str, text: str):
    ram_before = get_process_ram_mib()
    t0 = time.perf_counter()
    cfg = sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(
            vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                model=model_path,
                tokens=tokens_path,
                data_dir=data_dir if os.path.exists(data_dir) else ""
            ),
            num_threads=2,
            provider="cpu"
        )
    )
    engine = sherpa_onnx.OfflineTts(cfg)
    t_load = (time.perf_counter() - t0) * 1000
    ram_after = get_process_ram_mib()

    t_synth_start = time.perf_counter()
    audio = engine.generate(text, sid=0, speed=1.0)
    t_synth = (time.perf_counter() - t_synth_start) * 1000

    dur = len(audio.samples) / audio.sample_rate if audio.sample_rate else 0.0
    disk_mib = os.path.getsize(model_path) / (1024 * 1024)

    return {
        "disk_mib": disk_mib,
        "load_ms": t_load,
        "synth_ms": t_synth,
        "dur_s": dur,
        "ram_delta_mib": max(0.0, ram_after - ram_before)
    }

def main():
    print("=" * 90)
    print("iTANTRA BLOCK 6 — SIDE-BY-SIDE FP32 vs INT8 TTS BENCHMARK")
    print("=" * 90)

    base_dir = "app/tts/models"

    print(f"{'Language':<12} | {'Precision':<6} | {'Disk (MiB)':<10} | {'Load (ms)':<10} | {'Synth (ms)':<10} | {'Dur (s)':<8} | {'Reduction'}")
    print("-" * 90)

    for item in MODELS:
        folder = os.path.join(base_dir, item["folder"])
        tokens = os.path.join(folder, "tokens.txt")
        espeak = os.path.join(folder, "espeak-ng-data")

        fp32_path = os.path.join(folder, item["fp32"])
        int8_path = os.path.join(folder, item["int8"])

        if os.path.exists(fp32_path):
            res_fp32 = benchmark_single(fp32_path, tokens, espeak, item["text"])
            print(f"{item['lang'].upper():<12} | {'FP32':<6} | {res_fp32['disk_mib']:<10.2f} | {res_fp32['load_ms']:<10.1f} | {res_fp32['synth_ms']:<10.1f} | {res_fp32['dur_s']:<8.2f} | Baseline")

        if os.path.exists(int8_path):
            res_int8 = benchmark_single(int8_path, tokens, espeak, item["text"])
            red = ((res_fp32['disk_mib'] - res_int8['disk_mib']) / res_fp32['disk_mib']) * 100
            print(f"{item['lang'].upper():<12} | {'INT8':<6} | {res_int8['disk_mib']:<10.2f} | {res_int8['load_ms']:<10.1f} | {res_int8['synth_ms']:<10.1f} | {res_int8['dur_s']:<8.2f} | -{red:.1f}%")

        print("-" * 90)

if __name__ == "__main__":
    main()
