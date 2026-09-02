import os
import json
import onnx

MODELS = [
    ("app/tts/models/vits-piper-te_IN-maya-medium/te_IN-maya-medium.onnx", "app/tts/models/vits-piper-te_IN-maya-medium/te_IN-maya-medium.onnx.json", "Telugu", "te"),
    ("app/tts/models/vits-piper-ml_IN-meera-medium/ml_IN-meera-medium.onnx", "app/tts/models/vits-piper-ml_IN-meera-medium/ml_IN-meera-medium.onnx.json", "Malayalam", "ml"),
    ("app/tts/models/vits-piper-mr_IN-google-medium/mr_IN-google-medium.onnx", "app/tts/models/vits-piper-mr_IN-google-medium/mr_IN-google-medium.onnx.json", "Marathi", "mr"),
    ("app/tts/models/vits-piper-bn_BD-google-medium/bn_BD-google-medium.onnx", "app/tts/models/vits-piper-bn_BD-google-medium/bn_BD-google-medium.onnx.json", "Bengali", "bn")
]

def add_metadata(onnx_path: str, json_path: str, lang_name: str, lang_code: str):
    if not os.path.exists(onnx_path) or not os.path.exists(json_path):
        return
    with open(json_path, "r", encoding="utf-8") as f:
        meta_json = json.load(f)
    
    sr = str(meta_json.get("audio", {}).get("sample_rate", 22050))
    n_speakers = str(meta_json.get("num_speakers", 1))
    
    model = onnx.load(onnx_path)
    
    meta_dict = {
        "model_type": "vits",
        "comment": "piper",
        "language": lang_name,
        "voice": lang_code,
        "has_espeak": "1",
        "n_speakers": n_speakers,
        "sample_rate": sr
    }
    
    # Clear and set
    del model.metadata_props[:]
    for k, v in meta_dict.items():
        entry = model.metadata_props.add()
        entry.key = k
        entry.value = str(v)
        
    onnx.save(model, onnx_path)
    print(f"[Metadata] Injected Sherpa-ONNX metadata into {onnx_path} (SR: {sr}, Speakers: {n_speakers})")

if __name__ == "__main__":
    for onnx_p, json_p, l_name, l_code in MODELS:
        add_metadata(onnx_p, json_p, l_name, l_code)
