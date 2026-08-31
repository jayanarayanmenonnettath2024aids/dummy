import os
import time
import tempfile
from abc import ABC, abstractmethod
from typing import Optional, Tuple
import sounddevice as sd
import soundfile as sf
import pyttsx3

class BaseTTSEngine(ABC):
    """Abstract Base Class for Text-To-Speech engines."""
    
    @abstractmethod
    def synthesize(self, text: str, language: str = "en", output_path: Optional[str] = None, play_audio: bool = True) -> Tuple[str, float]:
        """
        Synthesize speech from text.
        
        Args:
            text: Text string to synthesize.
            language: Language code ('en', 'ta', etc.)
            output_path: Optional file path to save the generated WAV.
            play_audio: Whether to automatically play the synthesized audio.
            
        Returns:
            Tuple of (output_audio_path: str, latency_seconds: float)
        """
        pass


class Pyttsx3TTSEngine(BaseTTSEngine):
    """
    Offline local TTS engine using pyttsx3 (SAPI5 on Windows / NSSpeechSynthesizer on macOS / espeak on Linux).
    Guarantees fast, low-latency, zero-cloud operation.
    """
    def __init__(self, rate: int = 160, volume: float = 1.0):
        self.rate = rate
        self.volume = volume

    def _get_engine(self):
        engine = pyttsx3.init()
        engine.setProperty('rate', self.rate)
        engine.setProperty('volume', self.volume)
        return engine

    def synthesize(self, text: str, language: str = "en", output_path: Optional[str] = None, play_audio: bool = True) -> Tuple[str, float]:
        if not text or not text.strip():
            text = "..."

        if output_path is None:
            temp_dir = tempfile.gettempdir()
            output_path = os.path.join(temp_dir, f"itantra_tts_{int(time.time()*1000)}.wav")

        start_time = time.perf_counter()
        
        # Initialize engine instance per call to avoid event loop conflicts in multithreaded / socket contexts
        engine = self._get_engine()
        
        # Match voice if available
        voices = engine.getProperty('voices')
        target_lang = language.lower()
        for voice in voices:
            if target_lang in ["ta", "tamil"] and ("tamil" in voice.name.lower() or "ta" in voice.id.lower()):
                engine.setProperty('voice', voice.id)
                break
            elif target_lang in ["en", "english"] and ("english" in voice.name.lower() or "david" in voice.name.lower() or "zira" in voice.name.lower()):
                engine.setProperty('voice', voice.id)
                break

        # Save to file
        engine.save_to_file(text, output_path)
        engine.runAndWait()
        
        latency = time.perf_counter() - start_time

        # Play audio locally if requested
        if play_audio and os.path.exists(output_path):
            try:
                data, fs = sf.read(output_path)
                sd.play(data, fs)
                sd.wait()
            except Exception as e:
                # Non-fatal if audio device is busy
                print(f"[!] Notice: Playback skipped ({e})")

        return output_path, latency


# Default TTSEngine alias
LocalTTSEngine = Pyttsx3TTSEngine
