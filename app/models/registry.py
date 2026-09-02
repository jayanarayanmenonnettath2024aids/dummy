from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

# Shared Multilingual Whisper-tiny Model Specs
SHARED_WHISPER_DISK_MIB = 148.23      # 155,434,464 bytes
SHARED_WHISPER_RAM_MIB = 416.25       # Total process RAM (+397.86 MiB delta)
SHARED_WHISPER_PARAMS = 37760640      # ~37.76M parameters

@dataclass
class LanguageProfile:
    """
    Profile defining local STT and Neural ONNX TTS capability for a given language.
    Strictly distinguishes disk footprint, runtime RAM, parameter counts,
    and portable neural ONNX models. SAPI5 is not used as production TTS.
    """
    code: str                             # ISO 639-1 language code (e.g. 'en', 'ta', 'hi')
    name: str                             # Human readable language name
    stt_model: str = "openai/whisper-tiny"
    tts_model: Optional[str] = None
    stt_installed: bool = True            # Available via shared Whisper-tiny
    stt_tested: bool = False              # Verified with real local inference
    tts_installed: bool = False           # Verified local neural ONNX voice model exists
    tts_tested: bool = False              # Verified local neural ONNX synthesis
    is_shared_stt_model: bool = True      # Single shared multilingual weights
    disk_size_mib: float = SHARED_WHISPER_DISK_MIB
    tts_disk_size_mib: float = 0.0        # Individual TTS model file size
    runtime_ram_mib: float = SHARED_WHISPER_RAM_MIB
    sample_rate: int = 16000
    stt_engine_type: str = "whisper"      # "whisper", "onnx", "none"
    tts_engine_type: str = "neural_onnx"  # "neural_onnx", "none"

    # Backward compatibility properties
    @property
    def stt_available(self) -> bool:
        return self.stt_installed and self.stt_tested

    @property
    def tts_available(self) -> bool:
        return self.tts_installed and self.tts_tested

    @property
    def model_size_mb(self) -> float:
        return self.disk_size_mib + self.tts_disk_size_mib

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "stt_model": self.stt_model,
            "tts_model": self.tts_model,
            "stt_installed": self.stt_installed,
            "stt_tested": self.stt_tested,
            "tts_installed": self.tts_installed,
            "tts_tested": self.tts_tested,
            "stt_available": self.stt_available,
            "tts_available": self.tts_available,
            "is_shared_stt_model": self.is_shared_stt_model,
            "disk_size_mib": self.disk_size_mib,
            "tts_disk_size_mib": self.tts_disk_size_mib,
            "runtime_ram_mib": self.runtime_ram_mib,
            "model_size_mb": self.model_size_mb,
            "sample_rate": self.sample_rate,
            "stt_engine_type": self.stt_engine_type,
            "tts_engine_type": self.tts_engine_type,
            "status": "SUPPORTED + TESTED" if (self.stt_tested and self.tts_tested) else (
                "PARTIAL (STT TESTED)" if (self.stt_tested and not self.tts_tested) else (
                    "INSTALLED — NOT VERIFIED" if (self.stt_installed or self.tts_installed) else "NOT AVAILABLE"
                )
            )
        }


# Target 10 Indian Regional Languages + English
DEFAULT_LANGUAGE_REGISTRY: Dict[str, LanguageProfile] = {
    "en": LanguageProfile(
        code="en",
        name="English",
        stt_model="openai/whisper-tiny",
        tts_model="Piper VITS (vits-piper-en_US-lessac-medium.onnx)",
        stt_installed=True,
        stt_tested=True,
        tts_installed=True,
        tts_tested=True,
        is_shared_stt_model=True,
        disk_size_mib=148.23,
        tts_disk_size_mib=60.27,
        runtime_ram_mib=416.25,
        stt_engine_type="whisper",
        tts_engine_type="neural_onnx"
    ),
    "hi": LanguageProfile(
        code="hi",
        name="Hindi",
        stt_model="openai/whisper-tiny",
        tts_model="Piper VITS (vits-piper-hi_IN-pratham-medium.onnx)",
        stt_installed=True,
        stt_tested=True,
        tts_installed=True,
        tts_tested=True,
        is_shared_stt_model=True,
        disk_size_mib=148.23,
        tts_disk_size_mib=60.22,
        runtime_ram_mib=416.25,
        stt_engine_type="whisper",
        tts_engine_type="neural_onnx"
    ),
    "ta": LanguageProfile(
        code="ta",
        name="Tamil",
        stt_model="openai/whisper-tiny",
        tts_model="None (NOT AVAILABLE - No verified neural ONNX voice)",
        stt_installed=True,
        stt_tested=True,
        tts_installed=False,
        tts_tested=False,
        is_shared_stt_model=True,
        disk_size_mib=148.23,
        tts_disk_size_mib=0.0,
        runtime_ram_mib=416.25,
        stt_engine_type="whisper",
        tts_engine_type="none"
    ),
    "gu": LanguageProfile(
        code="gu",
        name="Gujarati",
        stt_model="openai/whisper-tiny",
        tts_model="None (NOT AVAILABLE)",
        stt_installed=True,
        stt_tested=False,
        tts_installed=False,
        tts_tested=False,
        is_shared_stt_model=True,
        disk_size_mib=148.23,
        tts_disk_size_mib=0.0,
        runtime_ram_mib=416.25,
        stt_engine_type="whisper",
        tts_engine_type="none"
    ),
    "mr": LanguageProfile(
        code="mr",
        name="Marathi",
        stt_model="openai/whisper-tiny",
        tts_model="None (NOT AVAILABLE)",
        stt_installed=True,
        stt_tested=False,
        tts_installed=False,
        tts_tested=False,
        is_shared_stt_model=True,
        disk_size_mib=148.23,
        tts_disk_size_mib=0.0,
        runtime_ram_mib=416.25,
        stt_engine_type="whisper",
        tts_engine_type="none"
    ),
    "kn": LanguageProfile(
        code="kn",
        name="Kannada",
        stt_model="openai/whisper-tiny",
        tts_model="None (NOT AVAILABLE)",
        stt_installed=True,
        stt_tested=False,
        tts_installed=False,
        tts_tested=False,
        is_shared_stt_model=True,
        disk_size_mib=148.23,
        tts_disk_size_mib=0.0,
        runtime_ram_mib=416.25,
        stt_engine_type="whisper",
        tts_engine_type="none"
    ),
    "ml": LanguageProfile(
        code="ml",
        name="Malayalam",
        stt_model="openai/whisper-tiny",
        tts_model="None (NOT AVAILABLE)",
        stt_installed=True,
        stt_tested=False,
        tts_installed=False,
        tts_tested=False,
        is_shared_stt_model=True,
        disk_size_mib=148.23,
        tts_disk_size_mib=0.0,
        runtime_ram_mib=416.25,
        stt_engine_type="whisper",
        tts_engine_type="none"
    ),
    "te": LanguageProfile(
        code="te",
        name="Telugu",
        stt_model="openai/whisper-tiny",
        tts_model="None (NOT AVAILABLE)",
        stt_installed=True,
        stt_tested=False,
        tts_installed=False,
        tts_tested=False,
        is_shared_stt_model=True,
        disk_size_mib=148.23,
        tts_disk_size_mib=0.0,
        runtime_ram_mib=416.25,
        stt_engine_type="whisper",
        tts_engine_type="none"
    ),
    "or": LanguageProfile(
        code="or",
        name="Odia",
        stt_model="openai/whisper-tiny",
        tts_model="None (NOT AVAILABLE)",
        stt_installed=True,
        stt_tested=False,
        tts_installed=False,
        tts_tested=False,
        is_shared_stt_model=True,
        disk_size_mib=148.23,
        tts_disk_size_mib=0.0,
        runtime_ram_mib=416.25,
        stt_engine_type="whisper",
        tts_engine_type="none"
    ),
    "bn": LanguageProfile(
        code="bn",
        name="Bengali",
        stt_model="openai/whisper-tiny",
        tts_model="None (NOT AVAILABLE)",
        stt_installed=True,
        stt_tested=False,
        tts_installed=False,
        tts_tested=False,
        is_shared_stt_model=True,
        disk_size_mib=148.23,
        tts_disk_size_mib=0.0,
        runtime_ram_mib=416.25,
        stt_engine_type="whisper",
        tts_engine_type="none"
    )
}
