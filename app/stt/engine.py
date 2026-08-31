import os
import time
import numpy as np
from abc import ABC, abstractmethod
from typing import Optional, Union, Tuple
import sounddevice as sd
import soundfile as sf
from scipy.signal import resample

class BaseSTTEngine(ABC):
    """Abstract Base Class for Speech-To-Text engines."""
    
    @abstractmethod
    def transcribe(self, audio: Union[np.ndarray, str], sample_rate: int = 16000, language: str = "en") -> Tuple[str, float]:
        """
        Transcribe audio input into text.
        
        Args:
            audio: Numpy array of audio samples or path to a WAV file.
            sample_rate: Sample rate of the audio array (default 16000).
            language: Target language code ('en', 'ta', etc.)
            
        Returns:
            Tuple of (transcript: str, latency_seconds: float)
        """
        pass


class WhisperSTTEngine(BaseSTTEngine):
    """
    Local STT engine using OpenAI Whisper (tiny model for CPU efficiency).
    Operates 100% offline without any cloud APIs.
    """
    def __init__(self, model_name: str = "openai/whisper-tiny", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._pipeline = None
        self._recording_stream = None
        self._recorded_frames = []
        self._is_recording = False
        self._initialize_model()

    def start_dynamic_recording(self, sample_rate: int = 16000):
        """Start dynamic audio stream recording for Push-To-Talk."""
        if self._is_recording:
            return
        self._recorded_frames = []
        self._is_recording = True
        
        def callback(indata, frames, time_info, status):
            if self._is_recording:
                self._recorded_frames.append(indata.copy())

        self._recording_stream = sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype='float32',
            callback=callback
        )
        self._recording_stream.start()

    def stop_dynamic_recording(self) -> np.ndarray:
        """Stop dynamic audio recording and return captured audio array."""
        if not self._is_recording:
            return np.array([], dtype=np.float32)
        
        self._is_recording = False
        if self._recording_stream:
            self._recording_stream.stop()
            self._recording_stream.close()
            self._recording_stream = None

        if not self._recorded_frames:
            return np.array([], dtype=np.float32)
        
        audio = np.concatenate(self._recorded_frames, axis=0).squeeze()
        return audio

    def record_microphone(self, duration_seconds: float = 4.0, sample_rate: int = 16000) -> np.ndarray:
        """Record audio from the default input device for a fixed duration."""
        print(f"[*] Recording for {duration_seconds}s (Speak now)...")
        recording = sd.rec(
            int(duration_seconds * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype='float32'
        )
        sd.wait()
        print("[*] Recording complete.")
        return recording.squeeze()

    def _initialize_model(self):
        import warnings
        warnings.filterwarnings("ignore")
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        from transformers import pipeline, logging
        logging.set_verbosity_error()
        try:
            # Load from offline cache
            self._pipeline = pipeline(
                "automatic-speech-recognition",
                model=self.model_name,
                device=self.device,
            )
        except Exception:
            # If not in cache, temporarily enable online fetch
            os.environ.pop("HF_HUB_OFFLINE", None)
            os.environ.pop("TRANSFORMERS_OFFLINE", None)
            self._pipeline = pipeline(
                "automatic-speech-recognition",
                model=self.model_name,
                device=self.device,
            )

    def preprocess_audio(self, audio: np.ndarray, orig_sr: int, target_sr: int = 16000) -> np.ndarray:
        """Convert multi-channel audio to mono and resample to target_sr."""
        # Convert stereo to mono
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)
        
        # Ensure float32 in [-1.0, 1.0]
        if audio.dtype != np.float32:
            if np.issubdtype(audio.dtype, np.integer):
                max_val = np.iinfo(audio.dtype).max
                audio = audio.astype(np.float32) / max_val
            else:
                audio = audio.astype(np.float32)

        # Resample if needed
        if orig_sr != target_sr:
            num_samples = int(len(audio) * target_sr / orig_sr)
            audio = resample(audio, num_samples).astype(np.float32)
            
        return audio

    def record_microphone(self, duration_seconds: float = 4.0, sample_rate: int = 16000) -> np.ndarray:
        """Record audio from the default input device."""
        print(f"[*] Recording for {duration_seconds}s (Speak now)...")
        recording = sd.rec(
            int(duration_seconds * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype='float32'
        )
        sd.wait()
        print("[*] Recording complete.")
        return recording.squeeze()

    def load_wav(self, file_path: str) -> Tuple[np.ndarray, int]:
        """Load audio from a WAV file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio sample file not found: {file_path}")
        data, sr = sf.read(file_path)
        return data, sr

    def _clean_hallucinations(self, text: str) -> str:
        """Filter out repetitive phrase loops and common Whisper silence hallucinations."""
        import re
        if not text:
            return ""
        
        # Collapse phrases repeating 3 or more times (e.g. "let's go, let's go, let's go" -> "let's go")
        cleaned = re.sub(r'(\b.+?\b)(?:[,\s]+\1){2,}', r'\1', text, flags=re.IGNORECASE)
        
        # Also clean repeating single words
        cleaned = re.sub(r'\b(\w+)(?:\s+\1){2,}\b', r'\1', cleaned, flags=re.IGNORECASE)

        # Filter out common Whisper hallucinations that occur on ambient silence
        silence_hallucinations = [
            "thank you.", "thank you", "thank you for watching", 
            "thank you for watching.", "subtitles by", "bye bye", "amara.org"
        ]
        if cleaned.strip().lower() in silence_hallucinations:
            return ""
            
        return cleaned.strip()

    def transcribe(self, audio: Union[np.ndarray, str], sample_rate: int = 16000, language: str = "en") -> Tuple[str, float]:
        """
        Perform local STT inference on audio array or WAV file with hallucination prevention.
        """
        # Handle file input vs array input
        if isinstance(audio, str):
            audio_data, sr = self.load_wav(audio)
            audio_processed = self.preprocess_audio(audio_data, sr, target_sr=16000)
        else:
            audio_processed = self.preprocess_audio(audio, sample_rate, target_sr=16000)

        # Silence / Energy gate: discard pure silence/ambient hiss (< -45 dB)
        rms = np.sqrt(np.mean(audio_processed**2)) if len(audio_processed) > 0 else 0.0
        if rms < 0.003 or len(audio_processed) < 1600:  # less than 0.1s or pure silence
            return "", 0.001

        # Build generate_kwargs with anti-repetition penalty
        lang_code = "english" if language.lower() in ["en", "english"] else ("tamil" if language.lower() in ["ta", "tamil"] else language)
        generate_kwargs = {
            "language": lang_code,
            "task": "transcribe",
            "no_repeat_ngram_size": 3,
            "repetition_penalty": 1.25,
            "max_new_tokens": 96
        }

        start_time = time.perf_counter()
        result = self._pipeline(
            {"raw": audio_processed, "sampling_rate": 16000},
            generate_kwargs=generate_kwargs
        )
        latency = time.perf_counter() - start_time
        
        raw_transcript = result.get("text", "").strip()
        cleaned_transcript = self._clean_hallucinations(raw_transcript)
        return cleaned_transcript, latency
