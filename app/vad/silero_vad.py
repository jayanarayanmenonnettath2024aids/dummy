import os
import time
import collections
from typing import Optional, List, Callable, Dict, Any
import numpy as np
import onnxruntime as ort
from scipy.signal import resample

from app.vad.config import VADConfig
from app.vad.interface import VoiceActivityDetector

class SileroVADDetector(VoiceActivityDetector):
    """
    Streaming Voice Activity Detector using local Silero VAD ONNX model.
    Processes 16 kHz mono audio in 512-sample chunks (32 ms per frame)
    with 64-sample context preservation, pre-speech buffering, post-speech padding,
    and configurable thresholds.
    """
    def __init__(self, config: Optional[VADConfig] = None, model_path: Optional[str] = None):
        self.config = config or VADConfig()
        self.model_path = model_path or self._resolve_model_path()
        self._session: Optional[ort.InferenceSession] = None
        self._is_running = False

        # State machine constants
        self.STATE_IDLE = "IDLE"
        self.STATE_SPEECH_ACTIVE = "SPEECH_ACTIVE"
        self._state = self.STATE_IDLE

        # Model recurrent state (2, 1, 128) and 64-sample context
        self._rnn_state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, 64), dtype=np.float32)

        # Buffers
        self._sample_rate_tensor = np.array(self.config.sample_rate, dtype=np.int64)
        self._chunk_duration_ms = (self.config.chunk_size / self.config.sample_rate) * 1000.0  # 32.0 ms
        
        pre_chunks_count = max(1, int(self.config.pre_speech_buffer_ms / self._chunk_duration_ms))
        self._pre_speech_ring = collections.deque(maxlen=pre_chunks_count)
        
        self._active_utterance_chunks: List[np.ndarray] = []
        self._consecutive_silence_ms: float = 0.0
        self._speech_start_time: float = 0.0
        self._pending_raw_samples = np.array([], dtype=np.float32)

        # Callbacks
        self._started_callbacks: List[Callable[[float], None]] = []
        self._chunk_callbacks: List[Callable[[np.ndarray], None]] = []
        self._ended_callbacks: List[Callable[[np.ndarray, float], None]] = []

        self._initialize_onnx()

    def _resolve_model_path(self) -> str:
        """Locate bundled silero_vad.onnx model."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        bundled_path = os.path.join(current_dir, "models", "silero_vad.onnx")
        if os.path.exists(bundled_path):
            return bundled_path

        cache_path = os.path.expanduser("~/.cache/torch/hub/snakers4_silero-vad_master/src/silero_vad/data/silero_vad.onnx")
        if os.path.exists(cache_path):
            return cache_path

        return bundled_path

    def _initialize_onnx(self):
        """Initialize ONNX Runtime inference session with CPU provider."""
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Silero VAD ONNX model not found at: {self.model_path}")

        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        opts.log_severity_level = 3  # Error only
        self._session = ort.InferenceSession(self.model_path, sess_options=opts, providers=["CPUExecutionProvider"])
        self.reset()

    def start(self) -> None:
        self._is_running = True
        self.reset()

    def stop(self) -> None:
        self._is_running = False
        self.reset()

    def reset(self) -> None:
        """Reset internal recurrent state and buffers."""
        self._state = self.STATE_IDLE
        self._rnn_state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, 64), dtype=np.float32)
        self._pre_speech_ring.clear()
        self._active_utterance_chunks = []
        self._consecutive_silence_ms = 0.0
        self._speech_start_time = 0.0
        self._pending_raw_samples = np.array([], dtype=np.float32)

    def on_speech_started(self, callback: Callable[[float], None]) -> None:
        self._started_callbacks.append(callback)

    def on_speech_chunk(self, callback: Callable[[np.ndarray], None]) -> None:
        self._chunk_callbacks.append(callback)

    def on_speech_ended(self, callback: Callable[[np.ndarray, float], None]) -> None:
        self._ended_callbacks.append(callback)

    def _predict_chunk(self, chunk_512: np.ndarray) -> float:
        """Perform single chunk inference through Silero VAD ONNX with 64-sample context."""
        chunk_input = chunk_512.reshape(1, self.config.chunk_size).astype(np.float32)
        # Prepend 64 context samples -> (1, 576)
        x = np.concatenate([self._context, chunk_input], axis=1)

        outputs = self._session.run(
            None,
            {
                "input": x,
                "state": self._rnn_state,
                "sr": self._sample_rate_tensor
            }
        )
        prob = float(outputs[0][0][0])
        self._rnn_state = outputs[1]
        self._context = x[:, -64:].copy()
        return prob

    def process_chunk(self, audio: np.ndarray, sample_rate: int = 16000) -> Optional[np.ndarray]:
        """
        Stream audio array (float32 mono), segmenting into 512-sample frames.
        Returns complete utterance np.ndarray if end of speech was detected on this chunk, else None.
        """
        if audio is None or len(audio) == 0:
            return None

        # Convert stereo to mono
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Resample if not 16kHz
        if sample_rate != self.config.sample_rate:
            target_samples = int(len(audio) * self.config.sample_rate / sample_rate)
            audio = resample(audio, target_samples).astype(np.float32)

        # Concatenate with leftover samples from previous call
        if len(self._pending_raw_samples) > 0:
            audio = np.concatenate([self._pending_raw_samples, audio])
            self._pending_raw_samples = np.array([], dtype=np.float32)

        chunk_size = self.config.chunk_size
        num_full_chunks = len(audio) // chunk_size
        completed_utterance: Optional[np.ndarray] = None

        for i in range(num_full_chunks):
            chunk = audio[i * chunk_size : (i + 1) * chunk_size]
            res = self._process_single_frame(chunk)
            if res is not None:
                completed_utterance = res

        # Store remaining sub-frame samples for next invocation
        remainder_len = len(audio) % chunk_size
        if remainder_len > 0:
            self._pending_raw_samples = audio[-remainder_len:].copy()

        return completed_utterance

    def _process_single_frame(self, chunk: np.ndarray) -> Optional[np.ndarray]:
        """Process an exact 512-sample frame through the VAD state machine."""
        prob = self._predict_chunk(chunk)
        is_speech = prob >= self.config.speech_start_threshold

        if self._state == self.STATE_IDLE:
            if is_speech:
                # Transition to SPEECH_ACTIVE
                self._state = self.STATE_SPEECH_ACTIVE
                self._speech_start_time = time.time()
                self._consecutive_silence_ms = 0.0

                # Prepend pre-speech buffer chunks
                self._active_utterance_chunks = list(self._pre_speech_ring)
                self._active_utterance_chunks.append(chunk)

                # Fire speech started callback
                for cb in self._started_callbacks:
                    try:
                        cb(self._speech_start_time)
                    except Exception as e:
                        print(f"[!] VAD speech_started callback error: {e}")
            else:
                # Still idle, maintain pre-speech ring buffer
                self._pre_speech_ring.append(chunk)

        elif self._state == self.STATE_SPEECH_ACTIVE:
            self._active_utterance_chunks.append(chunk)

            # Fire chunk callback
            for cb in self._chunk_callbacks:
                try:
                    cb(chunk)
                except Exception as e:
                    print(f"[!] VAD speech_chunk callback error: {e}")

            if is_speech:
                self._consecutive_silence_ms = 0.0
            else:
                self._consecutive_silence_ms += self._chunk_duration_ms

            accumulated_samples = sum(len(c) for c in self._active_utterance_chunks)
            accumulated_ms = (accumulated_samples / self.config.sample_rate) * 1000.0

            # Termination conditions: Silence timeout OR Maximum utterance duration
            silence_timeout = self._consecutive_silence_ms >= self.config.silence_duration_ms
            max_duration_reached = accumulated_ms >= self.config.maximum_utterance_ms

            if silence_timeout or max_duration_reached:
                # Total duration check against minimum speech threshold
                total_duration_ms = accumulated_ms

                if total_duration_ms < self.config.minimum_speech_ms:
                    # Reject brief clicks / transient noise
                    self.reset()
                    return None

                utterance = np.concatenate(self._active_utterance_chunks, axis=0)
                
                # Fire speech ended callback
                for cb in self._ended_callbacks:
                    try:
                        cb(utterance, total_duration_ms)
                    except Exception as e:
                        print(f"[!] VAD speech_ended callback error: {e}")

                self.reset()
                return utterance

        return None
