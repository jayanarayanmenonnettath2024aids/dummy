import time
import threading
from typing import Optional, Callable, Dict, Any
import numpy as np
import sounddevice as sd

from app.vad.config import VADConfig
from app.vad.silero_vad import SileroVADDetector

class VADStreamProcessor:
    """
    Manages continuous live audio capture and streaming VAD processing.
    Supports switching between 'ptt' mode (manual) and 'voice' mode (hands-free VAD).
    When in 'voice' mode, audio stream is monitored in real-time and completed
    utterances are dispatched directly to the STT / transmission pipeline.
    """
    def __init__(
        self,
        vad_detector: Optional[SileroVADDetector] = None,
        config: Optional[VADConfig] = None,
        on_utterance_ready: Optional[Callable[[np.ndarray, float], None]] = None,
        on_vad_state_change: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ):
        self.config = config or VADConfig()
        self.detector = vad_detector or SileroVADDetector(config=self.config)
        self.on_utterance_ready = on_utterance_ready
        self.on_vad_state_change = on_vad_state_change

        self.mode = "ptt"  # "ptt" or "voice"
        self.is_running = False
        self._mic_stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()

        # Wire internal detector callbacks
        self.detector.on_speech_started(self._handle_speech_started)
        self.detector.on_speech_ended(self._handle_speech_ended)

    def _handle_speech_started(self, timestamp: float):
        if self.on_vad_state_change:
            self.on_vad_state_change("SPEECH_STARTED", {"timestamp": timestamp})

    def _handle_speech_ended(self, utterance: np.ndarray, duration_ms: float):
        if self.on_vad_state_change:
            self.on_vad_state_change("SPEECH_ENDED", {"duration_ms": duration_ms})
        if self.on_utterance_ready and len(utterance) > 0:
            self.on_utterance_ready(utterance, duration_ms)

    def set_mode(self, mode: str) -> str:
        """Switch operational mode ('ptt' or 'voice')."""
        mode = mode.lower().strip()
        if mode not in ["ptt", "voice"]:
            mode = "ptt"

        with self._lock:
            if self.mode == mode:
                return self.mode

            self.mode = mode
            if self.mode == "voice":
                self.start_live_mic()
            else:
                self.stop_live_mic()

        return self.mode

    def start_live_mic(self):
        """Start hardware microphone continuous capture stream for VAD."""
        if self._mic_stream is not None:
            return

        self.detector.start()
        
        def audio_callback(indata, frames, time_info, status):
            if not self.is_running or self.mode != "voice":
                return
            audio_chunk = indata[:, 0].copy()  # Mono float32
            self.detector.process_chunk(audio_chunk)

        try:
            self._mic_stream = sd.InputStream(
                samplerate=self.config.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=self.config.chunk_size,
                callback=audio_callback
            )
            self._mic_stream.start()
            self.is_running = True
            print("[VAD] Voice Mode Activated: Continuous microphone streaming started.")
        except Exception as e:
            print(f"[!] VAD microphone stream init error: {e}")

    def stop_live_mic(self):
        """Stop hardware microphone capture stream."""
        if self._mic_stream:
            try:
                self._mic_stream.stop()
                self._mic_stream.close()
            except Exception:
                pass
            self._mic_stream = None
        self.is_running = False
        self.detector.stop()
        print("[VAD] Voice Mode Deactivated.")

    def process_external_audio_chunk(self, audio: np.ndarray) -> Optional[np.ndarray]:
        """Process an audio chunk passed from browser WebRTC/WebSocket."""
        return self.detector.process_chunk(audio)

    def update_config(self, new_config: VADConfig):
        """Update VAD configuration parameters dynamically."""
        self.config = new_config
        self.detector.config = new_config
