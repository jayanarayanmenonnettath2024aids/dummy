import os
import sys
import time
import sherpa_onnx
import soundfile as sf
import numpy as np

# Ensure UTF-8 console output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

MODEL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../models/tts/vits_rasa_13"))
MODEL_PATH = os.path.join(MODEL_DIR, "model.onnx")
TOKENS_PATH = os.path.join(MODEL_DIR, "tokens.txt")

print(f"Model path: {MODEL_PATH} ({os.path.getsize(MODEL_PATH)} bytes)")
print(f"Tokens path: {TOKENS_PATH} ({os.path.getsize(TOKENS_PATH)} bytes)")

# Test phrases for the 4 target languages
TESTS = {
    "ta": "கட்டளை மையத்திற்கு தகவல் தெரிவிக்கவும்",
    "kn": "ಆದೇಶ ಕೇಂದ್ರಕ್ಕೆ ಮಾಹಿತಿ ನೀಡಿರಿ",
    "mr": "कमांड केंद्राला माहिती द्या",
    "bn": "কমান্ড সেন্টারে তথ্য পাঠান",
    "te": "కమాండ్ పోస్ట్‌కు నివేదించండి",
    "ml": "കമാൻഡ് പോസ്റ്റിൽ റിപ്പോർട്ട് ചെയ്യുക"
}

# Configure Sherpa-ONNX VITS TTS
config = sherpa_onnx.OfflineTtsConfig(
    model=sherpa_onnx.OfflineTtsModelConfig(
        vits=sherpa_onnx.OfflineTtsVitsModelConfig(
            model=MODEL_PATH,
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

print("[*] Initializing Sherpa-ONNX VITS-RASA TTS engine...")
t0 = time.perf_counter()
tts = sherpa_onnx.OfflineTts(config)
init_time = (time.perf_counter() - t0) * 1000.0
print(f"[+] Initialized in {init_time:.2f} ms. Sample rate: {tts.sample_rate}")

OUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../artifacts/tts_validation"))
os.makedirs(OUT_DIR, exist_ok=True)

for lang, text in TESTS.items():
    print(f"\n[*] Testing Language [{lang}]: '{text}'")
    t0 = time.perf_counter()
    try:
        # Generate speech
        audio = tts.generate(text, sid=0, speed=1.0)
        synth_time = (time.perf_counter() - t0) * 1000.0
        
        samples = np.array(audio.samples, dtype=np.float32)
        dur = len(samples) / audio.sample_rate
        rtf = (synth_time / 1000.0) / dur if dur > 0 else 0
        
        out_file = os.path.join(OUT_DIR, f"{lang}.wav")
        sf.write(out_file, samples, audio.sample_rate)
        
        is_silent = np.all(samples == 0) or np.max(np.abs(samples)) < 1e-4
        has_nan = np.isnan(samples).any() or np.isinf(samples).any()
        
        print(f"  [+] Success! Output: {out_file}")
        print(f"  [+] Duration: {dur:.2f}s | Sample Rate: {audio.sample_rate}Hz | Latency: {synth_time:.2f}ms | RTF: {rtf:.3f}")
        print(f"  [+] Silent: {is_silent} | NaN/Inf: {has_nan} | Max Amplitude: {np.max(np.abs(samples)):.4f}")
    except Exception as e:
        print(f"  [!] Synthesis failed for [{lang}]: {e}")
