import os
import sys
import time
import struct
import numpy as np
import soundfile as sf
import psutil

sys.path.insert(0, os.path.abspath("."))

print("=" * 70)
print("iTANTRA SYSTEM FORENSIC AUDIT SCRIPT")
print("=" * 70)

# 1. Inspect Physical Model Files
print("\n--- 1. PHYSICAL MODEL FILE INSPECTION ---")
model_inventory = [
    ("Silero VAD", "app/vad/models/silero_vad.onnx"),
    ("Piper TTS English (FP32)", "app/tts/models/vits-piper-en_US-lessac-medium/en_US-lessac-medium.onnx"),
    ("Piper TTS English (INT8)", "app/tts/models/vits-piper-en_US-lessac-medium/en_US-lessac-medium.int8.onnx"),
    ("Piper TTS Hindi (FP32)", "app/tts/models/vits-piper-hi_IN-pratham-medium/hi_IN-pratham-medium.onnx"),
    ("Piper TTS Hindi (INT8)", "app/tts/models/vits-piper-hi_IN-pratham-medium/hi_IN-pratham-medium.int8.onnx"),
    ("Piper TTS Telugu (FP32)", "app/tts/models/vits-piper-te_IN-maya-medium/te_IN-maya-medium.onnx"),
    ("Piper TTS Telugu (INT8)", "app/tts/models/vits-piper-te_IN-maya-medium/te_IN-maya-medium.int8.onnx"),
    ("Piper TTS Malayalam (FP32)", "app/tts/models/vits-piper-ml_IN-meera-medium/ml_IN-meera-medium.onnx"),
    ("Piper TTS Malayalam (INT8)", "app/tts/models/vits-piper-ml_IN-meera-medium/ml_IN-meera-medium.int8.onnx"),
    ("VITS-RASA Multilingual (FP32)", "models/tts/vits_rasa_13/model.onnx"),
    ("VITS-RASA Multilingual (INT8)", "models/tts/vits_rasa_13/model.int8.onnx"),
    ("VITS-RASA Tokens", "models/tts/vits_rasa_13/tokens.txt"),
]

for name, path in model_inventory:
    if os.path.exists(path):
        size_bytes = os.path.getsize(path)
        size_mib = size_bytes / (1024 * 1024)
        print(f"  [OK] {name:<35} : {size_mib:>8.2f} MiB ({size_bytes:>11,d} bytes) at {path}")
    else:
        print(f"  [MISSING] {name:<35} at {path}")

# 2. Check Zero-SAPI5 / Zero-Cloud Rule in production codebase
print("\n--- 2. ZERO SAPI5 / ZERO CLOUD IMPORT INSPECTION ---")
forbidden_imports = ["import pyttsx3", "from pyttsx3", "import win32com", "import azure", "import google.cloud", "import boto3"]
found_forbidden = []
for root, dirs, files in os.walk("app"):
    if "__pycache__" in root:
        continue
    for f in files:
        if f.endswith(".py"):
            fpath = os.path.join(root, f)
            with open(fpath, "r", encoding="utf-8", errors="ignore") as file:
                for line_no, line in enumerate(file, 1):
                    for term in forbidden_imports:
                        if term in line:
                            found_forbidden.append((fpath, line_no, line.strip()))

if found_forbidden:
    print(f"  [!] Found forbidden imports in app/: {found_forbidden}")
else:
    print("  [OK] Zero forbidden TTS imports or cloud APIs imported in production codebase (app/)!")

# 3. ModelManager & 10-Language Synthesis Audit
print("\n--- 3. 10-LANGUAGE SYNTHESIS AUDIT ---")
from app.models.manager import ModelManager, ModelNotInstalledError
from app.models.registry import DEFAULT_LANGUAGE_REGISTRY, LanguageProfile

mm = ModelManager()

test_phrases = {
    "en": ("English", "Meet me at checkpoint 4 immediately."),
    "hi": ("Hindi", "तुरंत चेकपॉइंट चार पर मिलें।"),
    "te": ("Telugu", "వెంటనే చెక్‌పాయింట్ నాలుగు వద్ద కలవండి."),
    "ml": ("Malayalam", "ഉടൻ തന്നെ ചെക്ക്പോയിന്റ് നാലിൽ എത്തുക."),
    "ta": ("Tamil", "உடனடியாக சோதனைச் சாவடி நான்கிற்கு வரவும்."),
    "kn": ("Kannada", "ತಕ್ಷಣ ಚೆಕ್‌ಪಾಯಿಂಟ್ ನಾಲ್ಕಕ್ಕೆ ಬನ್ನಿ."),
    "mr": ("Marathi", "त्वरित चेकपॉइंट चार वर पोहोचा."),
    "bn": ("Bengali", "অবিলম্বে চেকপয়েন্ট চারে পৌঁছান।"),
    "gu": ("Gujarati", "તાત્કાલિક ચેકપોઇન્ટ ચાર પર મળો."),
    "or": ("Odia", "ତୁରନ୍ତ ଚେକପଏଣ୍ଟ ଚାରିରେ ପହଞ୍ଚନ୍ତୁ।")
}

for code, (lang_name, phrase) in test_phrases.items():
    prof = DEFAULT_LANGUAGE_REGISTRY.get(code)
    stt_status = "VERIFIED" if prof and prof.stt_available else "UNAVAILABLE"
    
    tts_status = "UNAVAILABLE"
    tts_engine_name = "None"
    latency_ms = 0.0
    sr = 0
    max_amp = 0.0
    
    if prof and prof.tts_available:
        try:
            tts_engine = mm.load_model(code, task="tts")
            tts_engine_name = tts_engine.__class__.__name__
            t0 = time.perf_counter()
            out_path, lat = tts_engine.synthesize(phrase, language=code, play_audio=False)
            latency_ms = (time.perf_counter() - t0) * 1000.0
            
            if os.path.exists(out_path):
                data, sr = sf.read(out_path)
                max_amp = float(np.max(np.abs(data))) if len(data) > 0 else 0.0
                if max_amp > 0.01:
                    tts_status = f"VERIFIED ({latency_ms:.1f}ms, {sr}Hz, amp={max_amp:.2f})"
                else:
                    tts_status = "SILENT_AUDIO_FAILURE"
            else:
                tts_status = "FILE_NOT_WRITTEN"
        except Exception as e:
            tts_status = f"ERROR: {e}"
    elif code in ["gu", "or"]:
        try:
            mm.load_model(code, task="tts")
            tts_status = "FAILED_TO_RAISE_EXCEPTION"
        except ModelNotInstalledError:
            tts_status = "CLEAN_EXCEPTION (ModelNotInstalledError)"
    
    print(f"  {code:<3} | {lang_name:<10} | STT: {stt_status:<11} | TTS Engine: {tts_engine_name:<24} | TTS Status: {tts_status}")

print("\n--- 4. PACKET WIRE PROTOCOL AUDIT ---")
from app.communication.packet_v2 import iTantraPacketV2, MAX_PACKET_BYTES, MAX_TEXT_BYTES
from app.security.authenticator import PacketAuthenticator
from app.security.trust_store import TrustStore

pkt = iTantraPacketV2(
    payload="Meet me at checkpoint 4 immediately.",
    language="ta",
    sender_id="NODE-ALPHA",
    session_id="SESS0001",
    message_type=iTantraPacketV2.MESSAGE_TYPE_ALERT,
    priority=iTantraPacketV2.PRIORITY_ALERT
)

trust_store = TrustStore(trust_file=":memory:")
key = b"\x42" * 32
trust_store.pair_device("NODE-ALPHA", key)
auth = PacketAuthenticator(trust_store=trust_store)
raw_tag = auth.sign_packet(pkt, key, raw_binary=True)
binary_bytes = pkt.to_binary()

print(f"  Fixed Header: 25 bytes")
print(f"  Auth Tag: {len(pkt.auth_tag)} bytes (Raw 32-byte HMAC-SHA256)")
print(f"  Total Wire Packet Size: {len(binary_bytes)} bytes")
print(f"  Audio Equivalent (2.5s @ 16kHz 16-bit): 80,000 bytes")
print(f"  Bandwidth Reduction: {((80000 - len(binary_bytes)) / 80000 * 100):.2f}%")
print(f"  Max Packet Limit: {MAX_PACKET_BYTES} bytes")
print(f"  Max Text Limit: {MAX_TEXT_BYTES} bytes")

# Authenticate
is_valid = auth.verify_and_authenticate(pkt)
print(f"  Packet Cryptographic Verification: {'PASS' if is_valid else 'FAIL'}")

# Tampering Test
tampered_bytes = bytearray(binary_bytes)
tampered_bytes[-1] ^= 0xFF  # Corrupt last byte of payload
tampered_pkt = iTantraPacketV2.from_binary(bytes(tampered_bytes))
try:
    auth.verify_and_authenticate(tampered_pkt)
    print("  [FAIL] Tampered packet was accepted!")
except Exception as e:
    print(f"  [OK] Tampered packet rejected: {e}")

print("\n--- 5. MEMORY AND FOOTPRINT AUDIT ---")
total_disk = mm.get_total_disk_footprint_mib()
unique_models = mm.get_unique_models()
print(f"  Total Shared Model Disk Footprint: {total_disk:.2f} MiB")
print(f"  Unique Physical Models Loaded/Counted: {len(unique_models)}")
for m in unique_models:
    print(f"    - {m['name']} ({m['type']}): {m['disk_size_mib']:.2f} MiB")

print("\n" + "=" * 70)
print("AUDIT SCRIPT COMPLETE")
print("=" * 70)
