import os
import sys
import time
import psutil
import torch
import numpy as np
import soundfile as sf
import sherpa_onnx
import onnxruntime as ort
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def get_process_ram_mib():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)

def benchmark_stt():
    print("=" * 60)
    print("1. BENCHMARKING STT BASELINE (openai/whisper-tiny FP32)")
    print("=" * 60)
    
    stt_dir = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub", "models--openai--whisper-tiny")
    safetensors_path = os.path.join(stt_dir, "snapshots", "16922a94593ef33a39e55728a07f9c2d1b826f4c", "model.safetensors")
    
    disk_size_bytes = 0
    if os.path.exists(safetensors_path):
        disk_size_bytes = os.path.getsize(safetensors_path)
    elif os.path.exists(stt_dir):
        for root, _, files in os.walk(stt_dir):
            for f in files:
                disk_size_bytes += os.path.getsize(os.path.join(root, f))

    disk_size_mib = disk_size_bytes / (1024 * 1024)

    ram_before = get_process_ram_mib()
    t0 = time.perf_counter()
    processor = AutoProcessor.from_pretrained("openai/whisper-tiny")
    model = AutoModelForSpeechSeq2Seq.from_pretrained("openai/whisper-tiny")
    model.eval()
    t_load = (time.perf_counter() - t0) * 1000
    ram_after = get_process_ram_mib()
    ram_stt = max(0.0, ram_after - ram_before)

    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())

    # Inference test on sample
    sample_path = "samples/checkpoint_en.wav"
    audio_data, sr = sf.read(sample_path)
    if sr != 16000:
        pass
    
    t_inf_start = time.perf_counter()
    input_features = processor(audio_data, sampling_rate=16000, return_tensors="pt").input_features
    predicted_ids = model.generate(input_features, language="en", task="transcribe")
    transcript = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0].strip()
    t_inf = (time.perf_counter() - t_inf_start) * 1000

    audio_duration_sec = len(audio_data) / sr
    rtf = (t_inf / 1000.0) / audio_duration_sec

    print(f"STT Model: openai/whisper-tiny")
    print(f"Disk Size: {disk_size_mib:.2f} MiB")
    print(f"Parameters: {total_params / 1e6:.2f}M ({total_params:,} parameters)")
    print(f"Precision: FP32")
    print(f"Runtime RAM Delta: {ram_stt:.2f} MiB (Total Process RSS: {ram_after:.2f} MiB)")
    print(f"Model Load Time: {t_load:.2f} ms")
    print(f"Transcript: '{transcript}'")
    print(f"Audio Duration: {audio_duration_sec:.2f} s")
    print(f"Inference Latency: {t_inf:.2f} ms")
    print(f"Real-Time Factor (RTF): {rtf:.3f}")
    
    return {
        "disk_size_mib": disk_size_mib,
        "parameters": total_params,
        "precision": "FP32",
        "runtime_ram_mib": ram_stt,
        "load_time_ms": t_load,
        "inference_latency_ms": t_inf,
        "rtf": rtf
    }

def benchmark_tts():
    print("\n" + "=" * 60)
    print("2. BENCHMARKING TTS BASELINE (VITS Piper ONNX FP32)")
    print("=" * 60)
    
    tts_models = {
        "en": {
            "name": "vits-piper-en_US-lessac-medium",
            "dir": "app/tts/models/vits-piper-en_US-lessac-medium",
            "model_file": "en_US-lessac-medium.onnx",
            "text": "Meet me at checkpoint 4 for immediate tactical briefing."
        },
        "hi": {
            "name": "vits-piper-hi_IN-pratham-medium",
            "dir": "app/tts/models/vits-piper-hi_IN-pratham-medium",
            "model_file": "hi_IN-pratham-medium.onnx",
            "text": "चेकपॉइंट चार पर तुरंत रिपोर्ट करें।"
        }
    }
    
    results = {}
    for lang, info in tts_models.items():
        model_path = os.path.join(info["dir"], info["model_file"])
        tokens_path = os.path.join(info["dir"], "tokens.txt")
        espeak_path = os.path.join(info["dir"], "espeak-ng-data")
        
        # Disk size
        disk_bytes = 0
        for root, _, files in os.walk(info["dir"]):
            for f in files:
                disk_bytes += os.path.getsize(os.path.join(root, f))
        disk_mib = disk_bytes / (1024 * 1024)
        
        # Load time & RAM
        ram_before = get_process_ram_mib()
        t0 = time.perf_counter()
        tts_cfg = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                    model=model_path,
                    tokens=tokens_path,
                    data_dir=espeak_path if os.path.exists(espeak_path) else "",
                    noise_scale=0.667,
                    noise_scale_w=0.8,
                    length_scale=1.0
                ),
                num_threads=2,
                provider="cpu"
            )
        )
        tts_engine = sherpa_onnx.OfflineTts(tts_cfg)
        t_load = (time.perf_counter() - t0) * 1000
        ram_after = get_process_ram_mib()
        ram_tts = max(0.0, ram_after - ram_before)
        
        # Synthesis benchmark
        t_synth_start = time.perf_counter()
        audio = tts_engine.generate(info["text"], sid=0, speed=1.0)
        t_synth = (time.perf_counter() - t_synth_start) * 1000
        
        audio_dur = len(audio.samples) / audio.sample_rate if audio.sample_rate else 0.0
        rtf = (t_synth / 1000.0) / audio_dur if audio_dur > 0 else 0.0
        
        print(f"\n--- Language: {lang.upper()} ({info['name']}) ---")
        print(f"Disk Size: {disk_mib:.2f} MiB (Model ONNX: {os.path.getsize(model_path)/(1024*1024):.2f} MiB)")
        print(f"Precision: FP32")
        print(f"Runtime RAM Delta: {ram_tts:.2f} MiB")
        print(f"Model Load Time: {t_load:.2f} ms")
        print(f"Text: '{info['text']}'")
        print(f"Generated Audio Duration: {audio_dur:.2f} s ({len(audio.samples)} samples @ {audio.sample_rate} Hz)")
        print(f"Synthesis Latency: {t_synth:.2f} ms")
        print(f"Real-Time Factor (RTF): {rtf:.3f}")
        
        results[lang] = {
            "model": info["name"],
            "disk_size_mib": disk_mib,
            "precision": "FP32",
            "runtime_ram_mib": ram_tts,
            "load_time_ms": t_load,
            "synthesis_latency_ms": t_synth,
            "rtf": rtf,
            "audio_dur_s": audio_dur
        }
    return results

def benchmark_vad():
    print("\n" + "=" * 60)
    print("3. BENCHMARKING VAD BASELINE (silero_vad.onnx FP32)")
    print("=" * 60)
    
    vad_path = "app/vad/models/silero_vad.onnx"
    disk_mib = os.path.getsize(vad_path) / (1024 * 1024)
    
    ram_before = get_process_ram_mib()
    t0 = time.perf_counter()
    session = ort.InferenceSession(vad_path, providers=["CPUExecutionProvider"])
    t_load = (time.perf_counter() - t0) * 1000
    ram_after = get_process_ram_mib()
    ram_vad = max(0.0, ram_after - ram_before)
    
    # Run 100 chunks (32ms / 512 samples each @ 16kHz)
    dummy_chunk = np.random.uniform(-0.1, 0.1, (1, 512)).astype(np.float32)
    state = np.zeros((2, 1, 128), dtype=np.float32)
    sr_tensor = np.array(16000, dtype=np.int64)
    
    latencies = []
    for _ in range(100):
        t_start = time.perf_counter()
        ort_inputs = {
            "input": dummy_chunk,
            "state": state,
            "sr": sr_tensor
        }
        out, state = session.run(None, ort_inputs)
        latencies.append((time.perf_counter() - t_start) * 1000)
    
    avg_chunk_lat = np.mean(latencies)
    
    print(f"Model: silero_vad.onnx")
    print(f"Disk Size: {disk_mib:.2f} MiB")
    print(f"Precision: FP32")
    print(f"Runtime RAM Delta: {ram_vad:.2f} MiB")
    print(f"Model Load Time: {t_load:.2f} ms")
    print(f"Average Inference Latency per 32ms chunk: {avg_chunk_lat:.3f} ms")
    
    return {
        "disk_size_mib": disk_mib,
        "runtime_ram_mib": ram_vad,
        "load_time_ms": t_load,
        "chunk_latency_ms": avg_chunk_lat
    }

if __name__ == "__main__":
    stt_res = benchmark_stt()
    tts_res = benchmark_tts()
    vad_res = benchmark_vad()
