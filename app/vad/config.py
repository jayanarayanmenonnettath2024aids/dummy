from dataclasses import dataclass, asdict
from typing import Dict, Any

@dataclass
class VADConfig:
    """
    Configuration parameters for streaming Voice Activity Detection (VAD).
    All parameters are dynamic and configurable at runtime.
    """
    speech_start_threshold: float = 0.5     # Probability threshold to trigger speech start [0.0 - 1.0]
    silence_duration_ms: float = 700.0       # Consecutive silence needed to finalize utterance (600-800ms default)
    minimum_speech_ms: float = 250.0         # Minimum speech required to reject brief clicks/noise
    maximum_utterance_ms: float = 15000.0    # Maximum duration before forcing segmentation
    pre_speech_buffer_ms: float = 300.0      # Leading audio retained before speech trigger
    post_speech_buffer_ms: float = 200.0     # Trailing audio padding retained after speech ends
    sample_rate: int = 16000                 # Audio sample rate in Hz (16 kHz mono)
    chunk_size: int = 512                    # Processing chunk size in samples (32ms at 16kHz)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VADConfig":
        return cls(
            speech_start_threshold=float(data.get("speech_start_threshold", 0.5)),
            silence_duration_ms=float(data.get("silence_duration_ms", 700.0)),
            minimum_speech_ms=float(data.get("minimum_speech_ms", 250.0)),
            maximum_utterance_ms=float(data.get("maximum_utterance_ms", 15000.0)),
            pre_speech_buffer_ms=float(data.get("pre_speech_buffer_ms", 300.0)),
            post_speech_buffer_ms=float(data.get("post_speech_buffer_ms", 200.0)),
            sample_rate=int(data.get("sample_rate", 16000)),
            chunk_size=int(data.get("chunk_size", 512))
        )
