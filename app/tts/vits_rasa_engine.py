import os
import sys
import time
from typing import Tuple, Optional, Dict, Any, List
import numpy as np

# Ensure UTF-8 console support
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

class NeuralVitsRasaTTSEngine:
    """
    Offline Neural Text-to-Speech Engine utilizing AI4Bharat VITS-RASA architecture
    via sherpa-onnx runtime. Provides multi-speaker Indian language neural synthesis
    for Tamil (ta), Kannada (kn), Marathi (mr), Bengali (bn), Telugu (te), and Malayalam (ml).
    
    Zero dependencies on Windows SAPI5, pyttsx3, or cloud endpoints.
    """
    
    SUPPORTED_LANGUAGES = {
        "ta": {"name": "Tamil", "default_sid": 0},
        "kn": {"name": "Kannada", "default_sid": 0},
        "mr": {"name": "Marathi", "default_sid": 0},
        "bn": {"name": "Bengali", "default_sid": 0},
        "te": {"name": "Telugu", "default_sid": 0},
        "ml": {"name": "Malayalam", "default_sid": 0},
    }

    MODEL_DIR_NAME = "vits_rasa_13"
    FP32_MODEL_FILE = "model.onnx"
    INT8_MODEL_FILE = "model.int8.onnx"
    TOKENS_FILE = "tokens.txt"

    def __init__(
        self,
        models_dir: Optional[str] = None,
        precision: str = "fp32",
        num_threads: int = 2
    ):
        if models_dir is None:
            self.models_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "../../models/tts")
            )
        else:
            self.models_dir = os.path.abspath(models_dir)

        self.precision = precision.lower()
        self.num_threads = num_threads
        self.engine = None
        self._sample_rate = 24000
        self._model_path = ""
        self._tokens_path = ""

    def is_language_supported(self, lang: str) -> bool:
        """Returns True if the given ISO-639-1 language code is supported by VITS-RASA."""
        return lang.lower() in self.SUPPORTED_LANGUAGES

    def get_supported_languages(self) -> List[str]:
        """Returns list of supported language codes."""
        return list(self.SUPPORTED_LANGUAGES.keys())

    def get_model_paths(self) -> Tuple[str, str]:
        """Returns (model_path, tokens_path)."""
        target_dir = os.path.join(self.models_dir, self.MODEL_DIR_NAME)
        model_name = self.INT8_MODEL_FILE if self.precision == "int8" else self.FP32_MODEL_FILE
        model_path = os.path.join(target_dir, model_name)
        if not os.path.exists(model_path) and self.precision == "int8":
            # Fallback to FP32 if INT8 is missing
            model_path = os.path.join(target_dir, self.FP32_MODEL_FILE)

        tokens_path = os.path.join(target_dir, self.TOKENS_FILE)
        return model_path, tokens_path

    def load_model(self):
        """Loads the Sherpa-ONNX VITS-RASA model into memory."""
        if self.engine is not None:
            return

        model_path, tokens_path = self.get_model_paths()
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"MODEL NOT INSTALLED: VITS-RASA ONNX model missing at {model_path}"
            )
        if not os.path.exists(tokens_path):
            raise FileNotFoundError(
                f"MODEL NOT INSTALLED: VITS-RASA tokens.txt missing at {tokens_path}"
            )

        try:
            import sherpa_onnx
            config = sherpa_onnx.OfflineTtsConfig(
                model=sherpa_onnx.OfflineTtsModelConfig(
                    vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                        model=model_path,
                        tokens=tokens_path,
                        data_dir="",
                        noise_scale=0.667,
                        noise_scale_w=0.8,
                        length_scale=1.0
                    ),
                    provider="cpu",
                    num_threads=self.num_threads,
                    debug=0
                )
            )
            self.engine = sherpa_onnx.OfflineTts(config)
            self._sample_rate = self.engine.sample_rate
            self._model_path = model_path
            self._tokens_path = tokens_path
        except ImportError as e:
            raise ImportError(f"sherpa_onnx is required for NeuralVitsRasaTTSEngine: {e}")

    def unload_model(self):
        """Unloads the neural model and releases memory."""
        self.engine = None

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def synthesize(
        self,
        text: str,
        language: str = "ta",
        sid: int = 0,
        speed: float = 1.0,
        output_path: Optional[str] = None,
        play_audio: bool = False
    ) -> Tuple[str, float]:
        """
        Synthesizes text into 24kHz PCM WAV file using offline VITS-RASA inference.
        Returns (output_path, latency_seconds).
        """
        import tempfile
        import soundfile as sf

        lang = language.lower().strip()[:2]
        if not self.is_language_supported(lang):
            raise ValueError(
                f"TTS model unavailable for language: {lang}. "
                f"Supported languages: {list(self.SUPPORTED_LANGUAGES.keys())}"
            )

        if not text or not text.strip():
            text = "..."

        if output_path is None:
            temp_dir = tempfile.gettempdir()
            output_path = os.path.join(temp_dir, f"itantra_vits_rasa_{lang}_{int(time.time()*1000)}.wav")

        if self.engine is None:
            self.load_model()

        t0 = time.perf_counter()
        try:
            audio = self.engine.generate(text.strip(), sid=sid, speed=speed)
            latency = time.perf_counter() - t0
        except Exception as e:
            raise RuntimeError(f"VITS-RASA synthesis error on text '{text}': {e}")

        samples = np.array(audio.samples, dtype=np.float32)
        if len(samples) == 0:
            raise RuntimeError(f"VITS-RASA generated 0 samples for input text '{text}'")

        sf.write(output_path, samples, audio.sample_rate)

        if play_audio:
            try:
                import sounddevice as sd
                sd.play(samples, samplerate=audio.sample_rate)
                sd.wait()
            except Exception:
                pass

        return output_path, latency
