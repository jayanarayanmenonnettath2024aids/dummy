import os
import sys
import time
import numpy as np
import onnx
from onnxruntime.quantization import quantize_dynamic, QuantType
import sherpa_onnx
import soundfile as sf

MODEL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../models/tts/vits_rasa_13"))
FP32_PATH = os.path.join(MODEL_DIR, "model.onnx")
INT8_PATH = os.path.join(MODEL_DIR, "model.int8.onnx")
TOKENS_PATH = os.path.join(MODEL_DIR, "tokens.txt")

def quantize_model():
    print("=" * 65)
    print("  AI4Bharat VITS-RASA Dynamic INT8 Quantization  ")
    print("=" * 65)
    
    if not os.path.exists(FP32_PATH):
        raise FileNotFoundError(f"FP32 model not found at {FP32_PATH}")
        
    fp32_size_mb = os.path.getsize(FP32_PATH) / (1024 * 1024)
    print(f"[*] Input FP32 Model : {FP32_PATH} ({fp32_size_mb:.2f} MiB)")
    print(f"[*] Target INT8 Model: {INT8_PATH}")
    
    t0 = time.perf_counter()
    quantize_dynamic(
        model_input=FP32_PATH,
        model_output=INT8_PATH,
        weight_type=QuantType.QInt8
    )
    quant_time = time.perf_counter() - t0
    
    int8_size_mb = os.path.getsize(INT8_PATH) / (1024 * 1024)
    reduction = ((fp32_size_mb - int8_size_mb) / fp32_size_mb) * 100.0
    print(f"[+] Quantization Complete in {quant_time:.2f} s")
    print(f"[+] Output INT8 Model: {int8_size_mb:.2f} MiB ({reduction:.1f}% size reduction)")

    # Test INT8 Model with Sherpa-ONNX
    print("\n[*] Validating INT8 Model in Sherpa-ONNX...")
    config = sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(
            vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                model=INT8_PATH,
                tokens=TOKENS_PATH,
                data_dir="",
                noise_scale=0.667,
                noise_scale_w=0.8,
                length_scale=1.0
            ),
            provider="cpu",
            num_threads=2,
            debug=0
        )
    )
    tts_int8 = sherpa_onnx.OfflineTts(config)
    print(f"[+] INT8 Engine initialized. Testing Tamil synthesis...")
    
    t0 = time.perf_counter()
    audio = tts_int8.generate("கட்டளை மையத்திற்கு தகவல் தெரிவிக்கவும்", sid=0, speed=1.0)
    int8_lat = (time.perf_counter() - t0) * 1000.0
    samples = np.array(audio.samples, dtype=np.float32)
    dur = len(samples) / audio.sample_rate
    rtf = (int8_lat / 1000.0) / dur
    
    print(f"[+] INT8 Synthesis Success: Duration={dur:.2f}s | Latency={int8_lat:.2f}ms | RTF={rtf:.3f}")
    print(f"[+] Max Amplitude: {np.max(np.abs(samples)):.4f} | Silent: {np.max(np.abs(samples)) < 1e-4}")

if __name__ == "__main__":
    quantize_model()
