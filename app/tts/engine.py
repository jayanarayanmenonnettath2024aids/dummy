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
    """
    # Model catalog mapping ISO language codes to local model subdirectories
    MODELS_BASE_DIR = os.path.join(os.path.dirname(__file__), "models")

    LANGUAGE_MODELS = {
        "en": {
            "dir": "vits-piper-en_US-lessac-medium",
            "model_file": "en_US-lessac-medium.onnx",
            "tokens_file": "tokens.txt",
            "data_dir": "espeak-ng-data",
            "name": "Piper VITS English (lessac-medium)",
            "precision": "FP32",
            "disk_size_mib": 60.27
        },
        "hi": {
            "dir": "vits-piper-hi_IN-pratham-medium",
            "model_file": "hi_IN-pratham-medium.onnx",
            "tokens_file": "tokens.txt",
            "data_dir": "espeak-ng-data",
            "name": "Piper VITS Hindi (pratham-medium)",
            "precision": "FP32",
            "disk_size_mib": 60.22
        }
    }

    def __init__(self, models_dir: Optional[str] = None):
        self.models_dir = models_dir or self.MODELS_BASE_DIR
        self._loaded_models: Dict[str, Any] = {}
        self._initialize_available_models()

    def _initialize_available_models(self):
        """Discovers and prepares available local ONNX VITS models."""
        for lang, meta in self.LANGUAGE_MODELS.items():
            model_folder = os.path.join(self.models_dir, meta["dir"])
            vits_path = os.path.join(model_folder, meta["model_file"])
            tokens_path = os.path.join(model_folder, meta["tokens_file"])
            if os.path.exists(vits_path) and os.path.exists(tokens_path):
                # Lazy-loaded upon first synthesis or pre-loaded on request
                pass

    def _get_or_load_tts(self, lang_code: str):
        lang = lang_code.lower()[:2]
        if lang in self._loaded_models:
            return self._loaded_models[lang]

        if lang not in self.LANGUAGE_MODELS:
            raise ValueError(
                f"MODEL NOT INSTALLED: Neural ONNX TTS model for language '{lang}' is not installed locally. "
                f"Available neural models: {list(self.LANGUAGE_MODELS.keys())}"
            )

        meta = self.LANGUAGE_MODELS[lang]
        model_folder = os.path.join(self.models_dir, meta["dir"])
        vits_path = os.path.join(model_folder, meta["model_file"])
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
                    num_threads=1
                )
            )
            tts_instance = sherpa_onnx.OfflineTts(tts_config)
            self._loaded_models[lang] = tts_instance
            return tts_instance
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Sherpa-ONNX VITS engine for '{lang}': {e}")

    def is_language_supported(self, language: str) -> bool:
        lang = language.lower()[:2]
        if lang not in self.LANGUAGE_MODELS:
            return False
        meta = self.LANGUAGE_MODELS[lang]
        model_folder = os.path.join(self.models_dir, meta["dir"])
        vits_path = os.path.join(model_folder, meta["model_file"])
        return os.path.exists(vits_path)

    def get_engine_info(self) -> Dict[str, Any]:
        return {
            "engine": "NeuralONNXTTSEngine",
            "backend": "Sherpa-ONNX VITS (ONNX Runtime CPU)",
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

        start = time.perf_counter()
        audio = tts_instance.generate(text, sid=0, speed=1.0)
        samples = np.array(audio.samples, dtype=np.float32)
        sf.write(output_path, samples, audio.sample_rate)
        latency = time.perf_counter() - start

        if play_audio and os.path.exists(output_path):
            try:
                data, fs = sf.read(output_path)
                sd.play(data, fs)
                sd.wait()
            except Exception as e:
                print(f"[!] Playback notice: {e}")

        return output_path, latency


# Aliases for Neural ONNX TTS
NeuralTTSEngine = NeuralONNXTTSEngine
LocalTTSEngine = NeuralONNXTTSEngine


class Pyttsx3TTS(TTSEngine):
    """
    Legacy desktop TTS engine adapter using pyttsx3 (SAPI5 / espeak).
    Retained solely for optional test comparisons.
    """
    def __init__(self, rate: int = 160, volume: float = 1.0):
        self.rate = rate
        self.volume = volume
        self._supported_languages = ["en"]

    def is_language_supported(self, language: str) -> bool:
        return language.lower()[:2] in self._supported_languages

    def get_engine_info(self) -> Dict[str, Any]:
        return {
            "engine": "Pyttsx3TTS",
            "backend": "pyttsx3 / Windows SAPI5 (Legacy)",
            "offline_only": True,
            "supported_languages": self._supported_languages
        }

    def synthesize(
        self,
        text: str,
        language: str = "en",
        output_path: Optional[str] = None,
        play_audio: bool = True
    ) -> Tuple[str, float]:
        import pyttsx3
        if not text or not text.strip():
            text = "..."

        if output_path is None:
            temp_dir = tempfile.gettempdir()
            output_path = os.path.join(temp_dir, f"itantra_legacy_tts_{int(time.time()*1000)}.wav")

        start_time = time.perf_counter()
        engine = pyttsx3.init()
        engine.setProperty('rate', self.rate)
        engine.setProperty('volume', self.volume)
        engine.save_to_file(text, output_path)
        engine.runAndWait()
        latency = time.perf_counter() - start_time

        if play_audio and os.path.exists(output_path):
            try:
                data, fs = sf.read(output_path)
                sd.play(data, fs)
                sd.wait()
            except Exception as e:
                print(f"[!] Playback notice: {e}")

        return output_path, latency

Pyttsx3TTSEngine = Pyttsx3TTS
