import os
import time
import tempfile
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any, List
import sounddevice as sd
import soundfile as sf
import numpy as np

class TTSEngine(ABC):
    """
    Abstract Base Class for local Text-To-Speech engines in iTantra.
    Provides pluggable offline speech synthesis for desktop and Android edge nodes.
    """
    @abstractmethod
    def synthesize(
        self,
        text: str,
        language: str = "en",
        output_path: Optional[str] = None,
        play_audio: bool = True
    ) -> Tuple[str, float]:
        """
        Synthesize speech from text.
        Returns: Tuple of (output_audio_path: str, latency_seconds: float)
        """
        pass

    def is_language_supported(self, language: str) -> bool:
        """Check if language is supported by this engine."""
        return True

    def get_engine_info(self) -> Dict[str, Any]:
        """Return engine metadata (name, model, backend, offline status)."""
        return {"engine": self.__class__.__name__, "offline_only": True}

# Backward compatibility alias
BaseTTSEngine = TTSEngine


class NeuralONNXTTSEngine(TTSEngine):
    """
    High-Performance Portable Neural ONNX TTS Engine (Sherpa-ONNX / Piper VITS).
    Pure ONNX CPU inference designed for offline desktop and Android ARM64 deployment.
    Does NOT rely on Windows SAPI5, pyttsx3, cloud APIs, or OS-dependent voices.
    Supports FP32 and Quantized INT8 neural model weights.
    """
    MODELS_BASE_DIR = os.path.join(os.path.dirname(__file__), "models")

    LANGUAGE_MODELS = {
        "en": {
            "dir": "vits-piper-en_US-lessac-medium",
            "model_file_fp32": "en_US-lessac-medium.onnx",
            "model_file_int8": "en_US-lessac-medium.int8.onnx",
            "model_file": "en_US-lessac-medium.onnx",
            "tokens_file": "tokens.txt",
            "data_dir": "espeak-ng-data",
            "name": "Piper VITS English (lessac-medium)",
            "precision": "FP32",
            "disk_size_mib": 60.27,
            "int8_disk_size_mib": 17.82
        },
        "hi": {
            "dir": "vits-piper-hi_IN-pratham-medium",
            "model_file_fp32": "hi_IN-pratham-medium.onnx",
            "model_file_int8": "hi_IN-pratham-medium.int8.onnx",
            "model_file": "hi_IN-pratham-medium.onnx",
            "tokens_file": "tokens.txt",
            "data_dir": "espeak-ng-data",
            "name": "Piper VITS Hindi (pratham-medium)",
            "precision": "FP32",
            "disk_size_mib": 60.22,
            "int8_disk_size_mib": 17.72
        },
        "te": {
            "dir": "vits-piper-te_IN-maya-medium",
            "model_file_fp32": "te_IN-maya-medium.onnx",
            "model_file_int8": "te_IN-maya-medium.int8.onnx",
            "model_file": "te_IN-maya-medium.onnx",
            "tokens_file": "tokens.txt",
            "data_dir": "espeak-ng-data",
            "name": "Piper VITS Telugu (maya-medium)",
            "precision": "FP32",
            "disk_size_mib": 60.03,
            "int8_disk_size_mib": 17.49
        },
        "ml": {
            "dir": "vits-piper-ml_IN-meera-medium",
            "model_file_fp32": "ml_IN-meera-medium.onnx",
            "model_file_int8": "ml_IN-meera-medium.int8.onnx",
            "model_file": "ml_IN-meera-medium.onnx",
            "tokens_file": "tokens.txt",
            "data_dir": "espeak-ng-data",
            "name": "Piper VITS Malayalam (meera-medium)",
            "precision": "FP32",
            "disk_size_mib": 60.03,
            "int8_disk_size_mib": 17.49
        }
    }

    def __init__(self, models_dir: Optional[str] = None, precision: str = "fp32"):
        self.models_dir = models_dir or self.MODELS_BASE_DIR
        self.precision = precision.lower()
        self._loaded_models: Dict[str, Any] = {}

    def set_precision(self, precision: str):
        """Switch between 'fp32' and 'int8' models at runtime."""
        prec = precision.lower()
        if prec not in ["fp32", "int8"]:
            raise ValueError("Invalid precision: must be 'fp32' or 'int8'")
        if self.precision != prec:
            self.precision = prec
            self._loaded_models.clear()

    def get_precision(self) -> str:
        return self.precision

    def _get_or_load_tts(self, lang_code: str):
        lang = lang_code.lower()[:2]
        cache_key = f"{lang}_{self.precision}"
        if cache_key in self._loaded_models:
            return self._loaded_models[cache_key]

        if lang not in self.LANGUAGE_MODELS:
            raise ValueError(
                f"MODEL NOT INSTALLED: Neural ONNX TTS model for language '{lang}' is not installed locally. "
                f"Available neural models: {list(self.LANGUAGE_MODELS.keys())}"
            )

        meta = self.LANGUAGE_MODELS[lang]
        model_folder = os.path.join(self.models_dir, meta["dir"])
        
        # Select target precision file
        target_model_file = meta["model_file_int8"] if self.precision == "int8" else meta["model_file_fp32"]
        vits_path = os.path.join(model_folder, target_model_file)
        if not os.path.exists(vits_path):
            # Fallback to standard FP32 if INT8 is missing
            vits_path = os.path.join(model_folder, meta["model_file_fp32"])

        tokens_path = os.path.join(model_folder, meta["tokens_file"])
        data_path = os.path.join(model_folder, meta["data_dir"])

        if not os.path.exists(vits_path) or not os.path.exists(tokens_path):
            raise FileNotFoundError(
                f"MODEL NOT INSTALLED: Neural ONNX files missing at {vits_path}"
            )

        try:
            import sherpa_onnx
            tts_config = sherpa_onnx.OfflineTtsConfig(
                model=sherpa_onnx.OfflineTtsModelConfig(
                    vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                        model=vits_path,
                        tokens=tokens_path,
                        data_dir=data_path if os.path.exists(data_path) else ""
                    ),
                    num_threads=2,
                    provider="cpu"
                )
            )
            tts_instance = sherpa_onnx.OfflineTts(tts_config)
            self._loaded_models[cache_key] = tts_instance
            return tts_instance
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Sherpa-ONNX VITS engine for '{lang}': {e}")

    def is_language_supported(self, language: str) -> bool:
        lang = language.lower()[:2]
        if lang not in self.LANGUAGE_MODELS:
            return False
        meta = self.LANGUAGE_MODELS[lang]
        model_folder = os.path.join(self.models_dir, meta["dir"])
        vits_path = os.path.join(model_folder, meta["model_file_fp32"])
        return os.path.exists(vits_path)

    def get_engine_info(self) -> Dict[str, Any]:
        return {
            "engine": "NeuralONNXTTSEngine",
            "backend": "Sherpa-ONNX VITS (ONNX Runtime CPU)",
            "precision": self.precision.upper(),
            "supported_languages": [l for l in self.LANGUAGE_MODELS if self.is_language_supported(l)],
            "offline_only": True,
            "android_compatible": True
        }

    def synthesize(
        self,
        text: str,
        language: str = "en",
        output_path: Optional[str] = None,
        play_audio: bool = True
    ) -> Tuple[str, float]:
        if not text or not text.strip():
            text = "..."

        lang = language.lower()[:2]
        tts_instance = self._get_or_load_tts(lang)

        if output_path is None:
            temp_dir = tempfile.gettempdir()
            output_path = os.path.join(temp_dir, f"itantra_neural_tts_{lang}_{int(time.time()*1000)}.wav")

        t_start = time.perf_counter()
        audio = tts_instance.generate(text, sid=0, speed=1.0)
        t_latency = time.perf_counter() - t_start

        if len(audio.samples) == 0:
            raise RuntimeError(f"Synthesis returned empty audio for text: '{text}' in language '{lang}'")

        samples_arr = np.array(audio.samples, dtype=np.float32)
        sf.write(output_path, samples_arr, audio.sample_rate)

        if play_audio:
            try:
                sd.play(samples_arr, audio.sample_rate)
                sd.wait()
            except Exception as e:
                print(f"[!] Audio playback notice: {e}")

        return output_path, t_latency


class UnifiedTTSEngine(TTSEngine):
    """
    Unified Multi-Backend Neural TTS Engine for iTantra.
    Seamlessly routes speech synthesis across Piper INT8 (en, hi, te, ml)
    and AI4Bharat VITS-RASA FP32 (ta, kn, mr, bn) via ModelManager.
    """
    def __init__(self, precision: str = "int8"):
        from app.models.manager import ModelManager
        self.mm = ModelManager(precision=precision)

    def synthesize(
        self,
        text: str,
        language: str = "en",
        output_path: Optional[str] = None,
        play_audio: bool = True
    ) -> Tuple[str, float]:
        lang = language.lower()[:2] if language else "en"
        engine = self.mm.load_model(lang, task="tts")
        return engine.synthesize(text=text, language=lang, output_path=output_path, play_audio=play_audio)

    def is_language_supported(self, language: str) -> bool:
        lang = language.lower()[:2] if language else "en"
        return self.mm.is_available(lang, task="tts")

    def get_engine_info(self) -> Dict[str, Any]:
        return {
            "engine": "UnifiedTTSEngine",
            "offline_only": True,
            "supported_languages": [p.code for p in self.mm.get_installed_models() if p.tts_available]
        }


class LocalTTSEngine(UnifiedTTSEngine):
    """Production drop-in alias."""
    pass


class Pyttsx3TTS(TTSEngine):
    """Legacy Desktop fallback."""
    def synthesize(self, text: str, language: str = "en", output_path: str = None, play_audio: bool = True):
        raise NotImplementedError("SAPI5 / pyttsx3 is disabled in production. Use NeuralONNXTTSEngine or UnifiedTTSEngine.")

# Backward compatibility aliases
Pyttsx3TTSEngine = Pyttsx3TTS
NeuralTTSEngine = NeuralONNXTTSEngine

