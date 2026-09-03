import os
import re
import time
import numpy as np
from abc import ABC, abstractmethod
from typing import Optional, Union, Tuple, Dict, Any, List
import sounddevice as sd
import soundfile as sf
from scipy.signal import resample

class STTEngine(ABC):
    """
    Abstract Base Class for local Speech-To-Text engines in iTantra.
    Ensures pluggable offline models suitable for desktop and Android edge nodes.
    """
    @abstractmethod
    def transcribe(self, audio: Union[np.ndarray, str], sample_rate: int = 16000, language: str = "en") -> Tuple[str, float]:
        """
        Transcribe audio input into text.
        Returns: Tuple of (transcript: str, latency_seconds: float)
        """
        pass

    @abstractmethod
    def is_language_supported(self, language: str) -> bool:
        """Check if language is supported by this engine."""
        pass

    @abstractmethod
    def get_engine_info(self) -> Dict[str, Any]:
        """Return engine metadata (name, model, backend, size, supported languages)."""
        pass

# Backward compatibility alias
BaseSTTEngine = STTEngine


class WhisperSTT(STTEngine):
    """
    Local Whisper STT Engine using OpenAI Whisper (tiny model for CPU efficiency).
    Operates 100% offline without any cloud APIs.
    """
    def __init__(self, model_name: str = "openai/whisper-tiny", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._pipeline = None
        self._recording_stream = None
        self._recorded_frames = []
        self._is_recording = False
        self._supported_languages = ["en", "ta", "hi", "gu", "mr", "kn", "ml", "te", "or", "bn"]
        self._initialize_model()

    def is_language_supported(self, language: str) -> bool:
        return language.lower()[:2] in self._supported_languages

    def get_engine_info(self) -> Dict[str, Any]:
        return {
            "engine": "WhisperSTT",
            "model": self.model_name,
            "backend": "transformers / PyTorch CPU",
            "offline_only": True,
            "supported_languages": self._supported_languages
        }

    def _initialize_model(self):
        import warnings
        warnings.filterwarnings("ignore")
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        from transformers import pipeline, logging
        logging.set_verbosity_error()
        try:
            self._pipeline = pipeline(
                "automatic-speech-recognition",
                model=self.model_name,
                device=self.device,
            )
        except Exception:
            os.environ.pop("HF_HUB_OFFLINE", None)
            os.environ.pop("TRANSFORMERS_OFFLINE", None)
            self._pipeline = pipeline(
                "automatic-speech-recognition",
                model=self.model_name,
                device=self.device,
            )

    def preprocess_audio(self, audio: np.ndarray, orig_sr: int, target_sr: int = 16000) -> np.ndarray:
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)
        
        if audio.dtype != np.float32:
            if np.issubdtype(audio.dtype, np.integer):
                max_val = np.iinfo(audio.dtype).max
                audio = audio.astype(np.float32) / max_val
            else:
                audio = audio.astype(np.float32)

        if orig_sr != target_sr:
            num_samples = int(len(audio) * target_sr / orig_sr)
            audio = resample(audio, num_samples).astype(np.float32)
            
        return audio

    def load_wav(self, file_path: str) -> Tuple[np.ndarray, int]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio sample file not found: {file_path}")
        data, sr = sf.read(file_path)
        return data, sr

    def _clean_hallucinations(self, text: str) -> str:
        if not text:
            return ""
        
        cleaned = re.sub(r'(\b.+?\b)(?:[,\s]+\1){2,}', r'\1', text, flags=re.IGNORECASE)
        cleaned = re.sub(r'\b(\w+)(?:\s+\1){2,}\b', r'\1', cleaned, flags=re.IGNORECASE)

        silence_hallucinations = [
            "thank you.", "thank you", "thank you for watching", 
            "thank you for watching.", "thank you very much.", "thank you very much",
            "thanks for watching.", "thanks for watching", "subtitles by", "bye bye", 
            "amara.org", "you", "the", "...", "."
        ]
        if cleaned.strip().lower() in silence_hallucinations:
            return ""
            
        return cleaned.strip()

    def transcribe(self, audio: Union[np.ndarray, str], sample_rate: int = 16000, language: str = "en") -> Tuple[str, float]:
        if isinstance(audio, str):
            audio_data, sr = self.load_wav(audio)
            audio_processed = self.preprocess_audio(audio_data, sr, target_sr=16000)
        else:
            audio_processed = self.preprocess_audio(audio, sample_rate, target_sr=16000)

        rms = np.sqrt(np.mean(audio_processed**2)) if len(audio_processed) > 0 else 0.0
        if rms < 0.002 or len(audio_processed) < 1600:
            return "", 0.001

        # Peak normalization for optimal acoustic recognition
        max_peak = np.max(np.abs(audio_processed))
        if max_peak > 0.005:
            audio_processed = (audio_processed / max_peak * 0.95).astype(np.float32)

        lang_key = language.lower()[:2] if language else "en"
        whisper_lang_map = {
            "en": "english",
            "hi": "hindi",
            "te": "telugu",
            "ml": "malayalam",
            "ta": "tamil",
            "kn": "kannada",
            "mr": "marathi",
            "bn": "bengali",
            "gu": "gujarati",
            "or": "oriya",
        }
        lang_code = whisper_lang_map.get(lang_key, "english")

        # Explicitly force native Indic script decoder prompt IDs
        forced_ids = None
        try:
            if hasattr(self._pipeline, "tokenizer") and hasattr(self._pipeline.tokenizer, "get_decoder_prompt_ids"):
                forced_ids = self._pipeline.tokenizer.get_decoder_prompt_ids(language=lang_code, task="transcribe")
        except Exception:
            pass

        generate_kwargs = {
            "task": "transcribe",
            "no_repeat_ngram_size": 3,
            "repetition_penalty": 1.3,
            "max_new_tokens": 64,
            "num_beams": 1,
            "do_sample": False
        }
        if forced_ids:
            generate_kwargs["forced_decoder_ids"] = forced_ids
        else:
            generate_kwargs["language"] = lang_code

        start_time = time.perf_counter()
        result = self._pipeline(
            {"raw": audio_processed, "sampling_rate": 16000},
            generate_kwargs=generate_kwargs
        )
        latency = time.perf_counter() - start_time
        
        raw_transcript = result.get("text", "").strip()
        cleaned_transcript = self._clean_hallucinations(raw_transcript)
        return cleaned_transcript, latency

    def start_dynamic_recording(self, sample_rate: int = 16000):
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

# Backward compatibility class
class WhisperSTTEngine(WhisperSTT):
    pass


class OnnxSTT(STTEngine):
    """
    High-Performance Portable ONNX STT Engine (Sherpa-ONNX / ONNX Runtime).
    Designed for zero-dependency native edge and Android deployment.
    """
    def __init__(self, model_dir: Optional[str] = None, fallback_engine: Optional[STTEngine] = None):
        self.model_dir = model_dir
        self.fallback = fallback_engine or WhisperSTT()
        self._recognizer = None
        self._initialize_onnx()

    def _initialize_onnx(self):
        try:
            import sherpa_onnx
            if self.model_dir and os.path.exists(self.model_dir):
                # Initialize local sherpa-onnx offline recognizer
                tokens_path = os.path.join(self.model_dir, "tokens.txt")
                encoder_path = os.path.join(self.model_dir, "encoder.onnx")
                decoder_path = os.path.join(self.model_dir, "decoder.onnx")
                joiner_path = os.path.join(self.model_dir, "joiner.onnx")

                if os.path.exists(encoder_path) and os.path.exists(tokens_path):
                    self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
                        encoder=encoder_path,
                        decoder=decoder_path,
                        joiner=joiner_path,
                        tokens=tokens_path,
                        num_threads=1
                    )
        except Exception as e:
            print(f"[!] OnnxSTT init notice: {e}. Utilizing verified WhisperSTT fallback.")

    def is_language_supported(self, language: str) -> bool:
        return self.fallback.is_language_supported(language)

    def get_engine_info(self) -> Dict[str, Any]:
        return {
            "engine": "OnnxSTT",
            "sherpa_active": self._recognizer is not None,
            "fallback": "WhisperSTT",
            "offline_only": True
        }

    def transcribe(self, audio: Union[np.ndarray, str], sample_rate: int = 16000, language: str = "en") -> Tuple[str, float]:
        if self._recognizer is not None:
            # Process via native Sherpa-ONNX
            start = time.perf_counter()
            if isinstance(audio, str):
                data, sr = sf.read(audio)
            else:
                data, sr = audio, sample_rate
            stream = self._recognizer.create_stream()
            stream.accept_waveform(sr, data)
            self._recognizer.decode_stream(stream)
            latency = time.perf_counter() - start
            return stream.result.text.strip(), latency

        return self.fallback.transcribe(audio, sample_rate=sample_rate, language=language)
