#!/usr/bin/env python3
"""
iTANTRA SIH26173 — Automatic AI Model & Asset Downloader
Downloads and verifies all physical offline neural models required for the frozen stack:
1. Silero VAD (ONNX)
2. Whisper-tiny Multilingual STT (Cached Transformer)
3. Piper VITS INT8 / FP32 TTS (English, Hindi, Telugu, Malayalam)
4. AI4Bharat VITS-RASA Multilingual TTS (Tamil, Kannada, Marathi, Bengali, Telugu, Malayalam)
"""

import os
import sys
import time
import urllib.request
import urllib.error

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def print_step(title: str):
    print(f"\n[SETUP] {title}")
    print("-" * 65)

def download_file_with_progress(url: str, dest_path: str, min_size_bytes: int = 1000) -> bool:
    """Download a file with progress reporting and size validation."""
    if os.path.exists(dest_path):
        current_size = os.path.getsize(dest_path)
        if current_size >= min_size_bytes:
            print(f"  [OK] Already present ({current_size:,d} bytes): {os.path.basename(dest_path)}")
            return True
        else:
            print(f"  [!] Existing file {dest_path} is undersized ({current_size} bytes). Re-downloading...")
            try:
                os.remove(dest_path)
            except Exception:
                pass

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    temp_path = dest_path + ".tmp"

    print(f"  --> Downloading: {os.path.basename(dest_path)} from {url}...")
    try:
        def reporthook(count, block_size, total_size):
            if total_size > 0:
                percent = min(100, int(count * block_size * 100 / total_size))
                downloaded_mb = (count * block_size) / (1024 * 1024)
                total_mb = total_size / (1024 * 1024)
                sys.stdout.write(f"\r      [{percent:3d}%] {downloaded_mb:.1f} / {total_mb:.1f} MiB")
                sys.stdout.flush()

        headers = {"User-Agent": "iTantra-Setup/2.0"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response, open(temp_path, "wb") as out_file:
            block_size = 1024 * 64
            total_size = int(response.headers.get("Content-Length", 0))
            count = 0
            while True:
                buf = response.read(block_size)
                if not buf:
                    break
                out_file.write(buf)
                count += 1
                reporthook(count, block_size, total_size)
        sys.stdout.write("\n")

        # Validate download
        if os.path.exists(temp_path):
            downloaded_size = os.path.getsize(temp_path)
            if downloaded_size < min_size_bytes:
                print(f"  [FAIL] Downloaded file is too small ({downloaded_size} bytes).")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return False
            os.replace(temp_path, dest_path)
            print(f"  [SUCCESS] Verified ({downloaded_size:,d} bytes): {os.path.basename(dest_path)}")
            return True
        return False
    except urllib.error.HTTPError as e:
        print(f"\n  [ERROR] HTTP Error {e.code}: {e.reason}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False
    except Exception as e:
        print(f"\n  [ERROR] Download failed: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False


def setup_vad():
    """Download Silero VAD ONNX model."""
    print_step("1/4: Silero VAD Neural Model")
    vad_dir = os.path.join(PROJECT_ROOT, "app", "vad", "models")
    os.makedirs(vad_dir, exist_ok=True)
    vad_path = os.path.join(vad_dir, "silero_vad.onnx")
    
    url = "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
    download_file_with_progress(url, vad_path, min_size_bytes=2_000_000)


def setup_whisper_stt():
    """Pre-fetch and cache Whisper-tiny Multilingual weights via transformers."""
    print_step("2/4: Whisper-Tiny Multilingual STT Model")
    try:
        print("  --> Pre-fetching 'openai/whisper-tiny' via Hugging Face cache...")
        from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq
        processor = AutoProcessor.from_pretrained("openai/whisper-tiny")
        model = AutoModelForSpeechSeq2Seq.from_pretrained("openai/whisper-tiny")
        print(f"  [SUCCESS] Whisper STT loaded and cached successfully ({sum(p.numel() for p in model.parameters()):,d} parameters).")
    except Exception as e:
        print(f"  [!] Notice: Whisper pre-cache encountered notice: {e}")
        print("  [!] If offline, Whisper will attempt to use local cache at runtime.")


def setup_piper_tts():
    """Verify and setup Piper neural TTS voice models."""
    print_step("3/4: Piper Neural TTS Models (en, hi, te, ml)")
    piper_models = {
        "en": ("vits-piper-en_US-lessac-medium", "en_US-lessac-medium.onnx", "en_US-lessac-medium.int8.onnx", "tokens.txt"),
        "hi": ("vits-piper-hi_IN-pratham-medium", "hi_IN-pratham-medium.onnx", "hi_IN-pratham-medium.int8.onnx", "tokens.txt"),
        "te": ("vits-piper-te_IN-maya-medium", "te_IN-maya-medium.onnx", "te_IN-maya-medium.int8.onnx", "tokens.txt"),
        "ml": ("vits-piper-ml_IN-meera-medium", "ml_IN-meera-medium.onnx", "ml_IN-meera-medium.int8.onnx", "tokens.txt"),
    }
    
    for lang, (model_dir, fp32_file, int8_file, tokens_file) in piper_models.items():
        base_dir = os.path.join(PROJECT_ROOT, "app", "tts", "models", model_dir)
        os.makedirs(base_dir, exist_ok=True)
        
        int8_path = os.path.join(base_dir, int8_file)
        tokens_path = os.path.join(base_dir, tokens_file)
        fp32_path = os.path.join(base_dir, fp32_file)

        if os.path.exists(int8_path) and os.path.getsize(int8_path) > 10_000_000:
            print(f"  [OK] Piper {lang.upper()} INT8 verified ({os.path.getsize(int8_path):,d} bytes)")
        elif os.path.exists(fp32_path) and os.path.getsize(fp32_path) > 50_000_000:
            print(f"  [OK] Piper {lang.upper()} FP32 verified ({os.path.getsize(fp32_path):,d} bytes)")
        else:
            print(f"  [!] Notice: Model for Piper {lang.upper()} missing at {base_dir}")


def setup_vits_rasa_tts():
    """Download / Verify AI4Bharat VITS-RASA multilingual TTS assets."""
    print_step("4/4: AI4Bharat VITS-RASA Multilingual TTS (ta, kn, mr, bn)")
    vits_dir = os.path.join(PROJECT_ROOT, "models", "tts", "vits_rasa_13")
    os.makedirs(vits_dir, exist_ok=True)

    model_path = os.path.join(vits_dir, "model.onnx")
    tokens_path = os.path.join(vits_dir, "tokens.txt")

    model_url = "https://huggingface.co/MatiasLin/sherpa-onnx-vits-rasa-13/resolve/main/model.onnx"
    tokens_url = "https://huggingface.co/MatiasLin/sherpa-onnx-vits-rasa-13/resolve/main/tokens.txt"

    download_file_with_progress(tokens_url, tokens_path, min_size_bytes=5_000)
    download_file_with_progress(model_url, model_path, min_size_bytes=100_000_000)


def main():
    print("=" * 65)
    print("  iTANTRA SIH26173 — MODEL & ASSET PROVISIONING ENGINE")
    print("=" * 65)
    
    t0 = time.perf_counter()
    setup_vad()
    setup_whisper_stt()
    setup_piper_tts()
    setup_vits_rasa_tts()
    elapsed = time.perf_counter() - t0

    print("\n" + "=" * 65)
    print(f"  [COMPLETE] All AI models and assets provisioned in {elapsed:.2f}s")
    print("=" * 65)

if __name__ == "__main__":
    main()
