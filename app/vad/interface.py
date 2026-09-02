from abc import ABC, abstractmethod
from typing import Optional, Callable, Dict, Any
import numpy as np

class VoiceActivityDetector(ABC):
    """
    Abstract interface for streaming Voice Activity Detection.
    Processes short audio frames and emits speech segmentation events.
    """

    @abstractmethod
    def start(self) -> None:
        """Initialize and start the VAD state machine."""
        pass

    @abstractmethod
    def process_chunk(self, audio: np.ndarray) -> Optional[np.ndarray]:
        """
        Process a single audio chunk (16kHz float32 mono).
        Returns:
            np.ndarray of completed speech utterance if an utterance just ended, else None.
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop VAD and release any active streaming state."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset internal accumulator and RNN/ONNX states."""
        pass

    @abstractmethod
    def on_speech_started(self, callback: Callable[[float], None]) -> None:
        """Register callback for when speech activity begins (timestamp: float)."""
        pass

    @abstractmethod
    def on_speech_chunk(self, callback: Callable[[np.ndarray], None]) -> None:
        """Register callback for each intermediate speech chunk."""
        pass

    @abstractmethod
    def on_speech_ended(self, callback: Callable[[np.ndarray, float], None]) -> None:
        """Register callback for when speech finishes (utterance_audio: np.ndarray, duration_ms: float)."""
        pass
