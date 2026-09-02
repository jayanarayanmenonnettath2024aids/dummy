import os
import sys
import json
import urllib.request

BASE_HF_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

MODELS_TO_DOWNLOAD = {
    "te": {
        "folder": "vits-piper-te_IN-maya-medium",
        "onnx_rel": "te/te_IN/maya/medium/te_IN-maya-medium.onnx",
        "json_rel": "te/te_IN/maya/medium/te_IN-maya-medium.onnx.json",
        "onnx_name": "te_IN-maya-medium.onnx",
        "json_name": "te_IN-maya-medium.onnx.json"
    },
    "ml": {
        "folder": "vits-piper-ml_IN-meera-medium",
        "onnx_rel": "ml/ml_IN/meera/medium/ml_IN-meera-medium.onnx",
        "json_rel": "ml/ml_IN/meera/medium/ml_IN-meera-medium.onnx.json",
        "onnx_name": "ml_IN-meera-medium.onnx",
        "json_name": "ml_IN-meera-medium.onnx.json"
    },
    "mr": {
        "folder": "vits-piper-mr_IN-google-medium",
        "onnx_rel": "mr/mr_IN/google/medium/mr_IN-google-medium.onnx",
        "json_rel": "mr/mr_IN/google/medium/mr_IN-google-medium.onnx.json",
        "onnx_name": "mr_IN-google-medium.onnx",
        "json_name": "mr_IN-google-medium.onnx.json"
    },
    "bn": {
        "folder": "vits-piper-bn_BD-google-medium",
        "onnx_rel": "bn/bn_BD/google/medium/bn_BD-google-medium.onnx",
        "json_rel": "bn/bn_BD/google/medium/bn_BD-google-medium.onnx.json",
        "onnx_name": "bn_BD-google-medium.onnx",
        "json_name": "bn_BD-google-medium.onnx.json"
    }
}

def generate_tokens_txt(json_path: str, tokens_path: str):
    with open(json_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    phoneme_id_map = meta.get("phoneme_id_map", {})
    # Map id -> phoneme
    id_to_phone = {}
    for p, ids in phoneme_id_map.items():
        for i in ids:
            id_to_phone[i] = p
    
    max_id = max(id_to_phone.keys()) if id_to_phone else 0
    with open(tokens_path, "w", encoding="utf-8") as f:
        for idx in range(max_id + 1):
            phone = id_to_phone.get(idx, f"#{idx}")
            f.write(f"{phone} {idx}\n")
    print(f"[Tokens] Generated {tokens_path} with {max_id + 1} tokens.")

def main():
    target_base = "app/tts/models"
    os.makedirs(target_base, exist_ok=True)
    
    espeak_source = "app/tts/models/vits-piper-hi_IN-pratham-medium/espeak-ng-data"
    
    for lang, info in MODELS_TO_DOWNLOAD.items():
        folder_path = os.path.join(target_base, info["folder"])
        os.makedirs(folder_path, exist_ok=True)
        
        onnx_dest = os.path.join(folder_path, info["onnx_name"])
        json_dest = os.path.join(folder_path, info["json_name"])
        tokens_dest = os.path.join(folder_path, "tokens.txt")
        
        # Download ONNX
        if not os.path.exists(onnx_dest):
            url = f"{BASE_HF_URL}/{info['onnx_rel']}"
            print(f"[{lang.upper()}] Downloading ONNX from {url} ...")
            urllib.request.urlretrieve(url, onnx_dest)
            print(f"[{lang.upper()}] Saved {onnx_dest} ({os.path.getsize(onnx_dest)/(1024*1024):.2f} MiB)")
        else:
            print(f"[{lang.upper()}] {onnx_dest} already exists.")
            
        # Download JSON
        if not os.path.exists(json_dest):
            url = f"{BASE_HF_URL}/{info['json_rel']}"
            print(f"[{lang.upper()}] Downloading JSON from {url} ...")
            urllib.request.urlretrieve(url, json_dest)
            print(f"[{lang.upper()}] Saved {json_dest}")
        else:
            print(f"[{lang.upper()}] {json_dest} already exists.")
            
        # Generate tokens.txt
        if not os.path.exists(tokens_dest):
            generate_tokens_txt(json_dest, tokens_dest)
            
        # Symlink or link espeak-ng-data
        espeak_dest = os.path.join(folder_path, "espeak-ng-data")
        if not os.path.exists(espeak_dest) and os.path.exists(espeak_source):
            # In Windows, copy or reference
            import shutil
            shutil.copytree(espeak_source, espeak_dest)
            print(f"[{lang.upper()}] Copied espeak-ng-data to {espeak_dest}")

if __name__ == "__main__":
    main()
