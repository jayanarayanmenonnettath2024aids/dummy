import os
from typing import Dict, Any, List, Optional
from app.models.registry import LanguageProfile, DEFAULT_LANGUAGE_REGISTRY

class ModelNotInstalledError(Exception):
    """Raised when a requested language model is not installed or available locally."""
    pass

class ModelManager:
    """
    Manages discovery, capability tracking, runtime caching, and precision abstraction (FP32/INT8)
    for local STT & Neural ONNX TTS models.
    """
    def __init__(self, registry: Optional[Dict[str, LanguageProfile]] = None, precision: str = "fp32"):
        self._registry: Dict[str, LanguageProfile] = registry or dict(DEFAULT_LANGUAGE_REGISTRY)
        self.precision: str = precision.lower()
        self._loaded_stt_engines: Dict[str, Any] = {}
        self._loaded_tts_engines: Dict[str, Any] = {}

    def set_precision(self, precision: str):
        """Switch between 'fp32' and 'int8' models at runtime."""
        prec = precision.lower()
        if prec not in ["fp32", "int8"]:
            raise ValueError("Invalid precision: must be 'fp32' or 'int8'")
        if self.precision != prec:
            self.precision = prec
            self._loaded_tts_engines.clear()

    def get_precision(self) -> str:
        return self.precision

    def get_available_models(self) -> List[LanguageProfile]:
        """Returns all configured language profiles and their verified status."""
        return list(self._registry.values())

    def get_installed_models(self) -> List[LanguageProfile]:
        """Returns only languages where at least STT or TTS is installed and verified."""
        return [p for p in self._registry.values() if p.stt_available or p.tts_available]

    def is_available(self, language: str, task: str = "all") -> bool:
        """
        Check if a given language is supported and installed for the requested task.
        task: 'stt', 'tts', or 'all'
        """
        lang = language.lower()[:2]
        profile = self._registry.get(lang)
        if not profile:
            return False

        task = task.lower()
        if task == "stt":
            return profile.stt_available
        elif task == "tts":
            return profile.tts_available
        else:
            return profile.stt_available and profile.tts_available

    def get_model_size(self, language: str) -> float:
        """Returns model size in MiB for the given language."""
        lang = language.lower()[:2]
        profile = self._registry.get(lang)
        return profile.disk_size_mib if profile else 0.0

    def get_total_disk_footprint_mib(self) -> float:
        """
        Computes the TRUE non-duplicated on-disk footprint across all installed models.
        Shared multilingual STT models and unique TTS models are counted exactly once.
        """
        unique_stt = set()
        unique_tts = set()
        total_disk = 0.0
        for p in self._registry.values():
            if p.stt_installed and p.stt_model not in unique_stt:
                unique_stt.add(p.stt_model)
                total_disk += p.disk_size_mib
            if p.tts_installed and p.tts_model not in unique_tts:
                unique_tts.add(p.tts_model)
                total_disk += (17.6 if self.precision == "int8" else p.tts_disk_size_mib)
        # Add Silero VAD (2.22 MiB)
        total_disk += 2.22
        return round(total_disk, 2)

    def get_unique_models(self) -> List[Dict[str, Any]]:
        """Returns list of unique physical models installed on disk without language duplication."""
        return [
            {
                "name": "openai/whisper-tiny",
                "type": "Multilingual STT",
                "format": "safetensors / PyTorch FP32",
                "disk_size_mib": 148.23,
                "runtime_ram_mib": 416.25,
                "languages": ["en", "hi", "ta", "gu", "mr", "kn", "ml", "te", "bn"]
            },
            {
                "name": "silero_vad.onnx",
                "type": "Voice Activity Detection",
                "format": "ONNX FP32",
                "disk_size_mib": 2.22,
                "runtime_ram_mib": 20.72,
                "languages": ["Language-Agnostic"]
            },
            {
                "name": "vits-piper-en_US-lessac-medium.onnx",
                "type": "Neural ONNX TTS (English)",
                "format": "ONNX (FP32: 60.27MB / INT8: 17.82MB)",
                "disk_size_mib": 17.82 if self.precision == "int8" else 60.27,
                "runtime_ram_mib": 30.13,
                "languages": ["en"]
            },
            {
                "name": "vits-piper-hi_IN-pratham-medium.onnx",
                "type": "Neural ONNX TTS (Hindi)",
                "format": "ONNX (FP32: 60.22MB / INT8: 17.72MB)",
                "disk_size_mib": 17.72 if self.precision == "int8" else 60.22,
                "runtime_ram_mib": 30.13,
                "languages": ["hi"]
            },
            {
                "name": "vits-piper-te_IN-maya-medium.onnx",
                "type": "Neural ONNX TTS (Telugu)",
                "format": "ONNX (FP32: 60.03MB / INT8: 17.49MB)",
                "disk_size_mib": 17.49 if self.precision == "int8" else 60.03,
                "runtime_ram_mib": 30.13,
                "languages": ["te"]
            },
            {
                "name": "vits-piper-ml_IN-meera-medium.onnx",
                "type": "Neural ONNX TTS (Malayalam)",
                "format": "ONNX (FP32: 60.03MB / INT8: 17.49MB)",
                "disk_size_mib": 17.49 if self.precision == "int8" else 60.03,
                "runtime_ram_mib": 30.13,
                "languages": ["ml"]
            }
        ]

    def register_custom_profile(self, profile: LanguageProfile):
        """Register or update a language profile dynamically."""
        self._registry[profile.code.lower()] = profile

    def load_model(self, language: str, task: str = "stt"):
        """
        Load and cache the appropriate local AI engine for the requested language.
        Raises ModelNotInstalledError if the language model is not installed.
        """
        lang = language.lower()[:2]
        task = task.lower()

        if not self.is_available(lang, task=task):
            raise ModelNotInstalledError(
                f"MODEL NOT INSTALLED: Language '{lang}' is not installed for task '{task}'. "
                f"Available languages: {[p.code for p in self.get_installed_models()]}"
            )

        if task == "stt":
            if lang in self._loaded_stt_engines:
                return self._loaded_stt_engines[lang]
            
            from app.stt.engine import WhisperSTT
            profile = self._registry[lang]
            model_name = profile.stt_model or "openai/whisper-tiny"
            engine = WhisperSTT(model_name=model_name)
            self._loaded_stt_engines[lang] = engine
            return engine

        elif task == "tts":
            cache_key = f"{lang}_{self.precision}"
            if cache_key in self._loaded_tts_engines:
                return self._loaded_tts_engines[cache_key]
            
            profile = self._registry[lang]
            if profile.tts_engine_type == "vits_rasa":
                from app.tts.vits_rasa_engine import NeuralVitsRasaTTSEngine
                engine = NeuralVitsRasaTTSEngine(precision=self.precision)
            else:
                from app.tts.engine import NeuralONNXTTSEngine
                engine = NeuralONNXTTSEngine(precision=self.precision)

            self._loaded_tts_engines[cache_key] = engine
            return engine

        raise ValueError(f"Unknown task type: '{task}' (expected 'stt' or 'tts')")

    def unload_model(self, language: str):
        """Unload and free cached model memory for a language."""
        lang = language.lower()[:2]
        for key in list(self._loaded_stt_engines.keys()):
            if key.startswith(lang):
                del self._loaded_stt_engines[key]
        for key in list(self._loaded_tts_engines.keys()):
            if key.startswith(lang):
                del self._loaded_tts_engines[key]

    def get_language_name(self, language: str) -> str:
        lang = language.lower()[:2]
        profile = self._registry.get(lang)
        return profile.name if profile else language.upper()
