import os
import sys
import time
from typing import Dict, Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.models.registry import DEFAULT_LANGUAGE_REGISTRY
from app.models.manager import ModelManager
from app.stt.engine import WhisperSTT, OnnxSTT
from app.tts.engine import Pyttsx3TTS, NeuralTTSEngine

def get_ram_usage_mb() -> float:
    """Attempt to read process resident memory."""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except Exception:
        return 0.0

def benchmark_ai_layer():
    print("=" * 80)
    print("iTANTRA AI LAYER BENCHMARK: LOCAL OFFLINE STT & TTS ENGINES")
    print("=" * 80)

    manager = ModelManager()

    # 1. Registry Inspection
    print("\n[1] MODEL REGISTRY & LANGUAGE AVAILABILITY:")
    print("-" * 70)
    print(f"{'CODE':<6} | {'LANGUAGE':<12} | {'STT STATUS':<14} | {'TTS STATUS':<14} | {'MODEL SIZE'}")
    print("-" * 70)
    for p in manager.get_available_models():
        stt_str = "✓ VERIFIED" if p.stt_available else "✗ NOT INSTALLED"
        tts_str = "✓ VERIFIED" if p.tts_available else "✗ NOT INSTALLED"
        size_str = f"{p.model_size_mb:.1f} MB" if p.model_size_mb > 0 else "N/A"
        print(f"{p.code:<6} | {p.name:<12} | {stt_str:<14} | {tts_str:<14} | {size_str}")

    # 2. STT Engine Initialization & Benchmark
    print("\n[2] STT ENGINE (WhisperSTT / OnnxSTT):")
    print("-" * 70)
    t0 = time.perf_counter()
    stt = WhisperSTT()
    stt_init_ms = (time.perf_counter() - t0) * 1000.0
    print(f"Startup Time:     {stt_init_ms:.2f} ms")
    print(f"Backend Engine:   {stt.get_engine_info()['backend']}")
    print(f"RAM Usage:        {get_ram_usage_mb():.2f} MB")

    sample_wav = "samples/checkpoint_en.wav"
    if os.path.exists(sample_wav):
        txt, lat = stt.transcribe(sample_wav, language="en")
        print(f"STT Latency (EN): {lat*1000:.1f} ms")
        print(f"STT Transcript:   '{txt}'")

    # 3. TTS Engine Initialization & Benchmark
    print("\n[3] TTS ENGINE (Pyttsx3TTS / NeuralTTSEngine):")
    print("-" * 70)
    t0 = time.perf_counter()
    tts = Pyttsx3TTS()
    tts_init_ms = (time.perf_counter() - t0) * 1000.0
    print(f"Startup Time:     {tts_init_ms:.2f} ms")
    print(f"Backend Engine:   {tts.get_engine_info()['backend']}")

    out_en, lat_en = tts.synthesize("Meet me at checkpoint 4.", language="en", play_audio=False)
    print(f"TTS Latency (EN): {lat_en*1000:.1f} ms (Saved: {os.path.basename(out_en)})")

    out_ta, lat_ta = tts.synthesize("வணக்கம்.", language="ta", play_audio=False)
    print(f"TTS Latency (TA): {lat_ta*1000:.1f} ms (Saved: {os.path.basename(out_ta)})")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    benchmark_ai_layer()
