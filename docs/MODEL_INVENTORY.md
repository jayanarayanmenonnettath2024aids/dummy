# iTantra Model Inventory, Language Support & Memory Accounting

**Smart India Hackathon 2026 — Problem Statement SIH26173**  
*Audited & Verified: September 3, 2026*

---

## 1. Physical Model Inventory

The table below catalogs every locally installed and verified model/voice in the repository.

| Model | Type | Purpose | Language(s) | Parameters | Disk Footprint | Runtime RAM | Precision | Quantized | Runtime Engine | Source | License | Tested |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **`openai/whisper-tiny`** | Seq2Seq Transformer ASR | Speech-To-Text (STT) | Multilingual (EN, TA, HI, +96 languages in unified vocabulary) | 37,760,640 (~37.76M) | **144.06 MiB** (151.06 MB) [`model.safetensors`]<br>*Total cache dir:* **148.23 MiB** (155.43 MB) | **416.25 MiB** total<br>(*Additional Delta:* **+397.86 MiB**) | FP32 | None (Unquantized) | HuggingFace Transformers / PyTorch CPU | OpenAI HuggingFace Hub | MIT | **YES** |
| **`silero_vad.onnx`** | Recurrent Neural Network (LSTM + Conv) | Voice Activity Detection (VAD) | Language-Agnostic Audio Streaming | ~2,100,000 (~2.1M) | **2.22 MiB** (2.33 MB) [2,327,524 bytes] | **~15.0 MiB** | FP32 | None (Unquantized) | ONNX Runtime (CPUExecutionProvider) | Silero Models | MIT | **YES** |
| **`vits-piper-en_US-lessac-medium.onnx`** | Neural VITS / Piper Architecture | Text-To-Speech (TTS) | English (`en_US`) | ~28,700,000 (~28.7M) | **60.27 MiB** (63.20 MB) | **~30.13 MiB** | FP32 | None (Unquantized) | Sherpa-ONNX / ONNX Runtime CPU | Piper / Sherpa-ONNX Hub | MIT | **YES** |
| **`vits-piper-hi_IN-pratham-medium.onnx`** | Neural VITS / Piper Architecture | Text-To-Speech (TTS) | Hindi (`hi_IN`) | ~28,700,000 (~28.7M) | **60.22 MiB** (63.15 MB) | **~30.13 MiB** | FP32 | None (Unquantized) | Sherpa-ONNX / ONNX Runtime CPU | Piper / Sherpa-ONNX Hub | MIT | **YES** |

> [!NOTE]
> **Units Definition:**
> - **MiB (Mebibytes):** Binary prefix ($1\text{ MiB} = 1024^2\text{ bytes} = 1,048,576\text{ bytes}$).
> - **MB (Megabytes):** Decimal prefix ($1\text{ MB} = 10^6\text{ bytes} = 1,000,000\text{ bytes}$).

---

## 2. STT Language Architecture Analysis

### Architectural Finding: **ONE SINGLE MULTILINGUAL MODEL**

The repository utilizes **ONE SINGLE MULTILINGUAL Whisper-tiny MODEL** (`openai/whisper-tiny`), **NOT** separate models per language.

- **Weight Sharing:** The file `~/.cache/huggingface/hub/models--openai--whisper-tiny/.../model.safetensors` (144.06 MiB) contains the unified neural weights for all supported languages.
- **Language Conditioning:** When transcribing English, Tamil, or Hindi, the same weights are evaluated; only the decoder prefix token (e.g., `<|en|>`, `<|ta|>`, `<|hi|>`) is switched during beam search / greedy decoding.
- **Storage Accounting:** Storing or referencing 10 languages does **NOT** require $10 \times 151\text{ MB} = 1.51\text{ GB}$. The entire multilingual STT capability occupies **148.23 MiB** total on disk.

```
openai/whisper-tiny (144.06 MiB Disk / 397.86 MiB RAM)
 ├── English (en) transcription
 ├── Tamil (ta) transcription
 ├── Hindi (hi) transcription
 └── 96+ additional world languages
```

---

## 3. Required Problem Statement Languages Matrix

Evaluation against the 10 target Indian regional languages + English:

| Language | ISO Code | STT Installed | STT Tested | TTS Installed (Neural ONNX) | TTS Tested (Neural ONNX) | Status Classification |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **English** | `en` | **YES** (Whisper-tiny) | **PASS** (784.6 ms) | **YES** (`vits-piper-en_US-lessac-medium.onnx`) | **PASS** (138.3 ms) | **SUPPORTED + TESTED** |
| **Hindi** | `hi` | **YES** (Whisper-tiny) | **PASS** (624.6 ms) | **YES** (`vits-piper-hi_IN-pratham-medium.onnx`) | **PASS** (172.4 ms) | **SUPPORTED + TESTED** |
| **Tamil** | `ta` | **YES** (Whisper-tiny) | **PASS** (1789.9 ms) | **NO** | **NO** | **PARTIAL (STT TESTED)** / **NOT AVAILABLE (TTS)** |
| **Gujarati** | `gu` | **YES** (Whisper-tiny) | NOT TESTED | **NO** | **NO** | **INSTALLED — NOT VERIFIED** (STT) / **NOT AVAILABLE** (TTS) |
| **Marathi** | `mr` | **YES** (Whisper-tiny) | NOT TESTED | **NO** | **NO** | **INSTALLED — NOT VERIFIED** (STT) / **NOT AVAILABLE** (TTS) |
| **Kannada** | `kn` | **YES** (Whisper-tiny) | NOT TESTED | **NO** | **NO** | **INSTALLED — NOT VERIFIED** (STT) / **NOT AVAILABLE** (TTS) |
| **Malayalam** | `ml` | **YES** (Whisper-tiny) | NOT TESTED | **NO** | **NO** | **INSTALLED — NOT VERIFIED** (STT) / **NOT AVAILABLE** (TTS) |
| **Telugu** | `te` | **YES** (Whisper-tiny) | NOT TESTED | **NO** | **NO** | **INSTALLED — NOT VERIFIED** (STT) / **NOT AVAILABLE** (TTS) |
| **Odia** | `or` | **YES** (Whisper-tiny) | NOT TESTED | **NO** | **NO** | **INSTALLED — NOT VERIFIED** (STT) / **NOT AVAILABLE** (TTS) |
| **Bengali** | `bn` | **YES** (Whisper-tiny) | NOT TESTED | **NO** | **NO** | **INSTALLED — NOT VERIFIED** (STT) / **NOT AVAILABLE** (TTS) |

---

## 4. Distinct Memory Footprint vs Disk Size

| Subsystem | On-Disk File Size | Runtime Memory (RAM) Footprint | Notes |
| :--- | :--- | :--- | :--- |
| **STT Subsystem** (`Whisper-tiny`) | **148.23 MiB** (155.43 MB) | **416.25 MiB** total (*+397.86 MiB delta*) | PyTorch runtime + weight tensors + tokenizer buffers |
| **VAD Subsystem** (`Silero VAD ONNX`) | **2.22 MiB** (2.33 MB) | **~15.00 MiB** | ONNX Runtime session & recurrent RNN states |
| **TTS English Subsystem** (`Piper VITS EN`) | **60.27 MiB** (63.20 MB) | **~30.13 MiB** | Sherpa-ONNX VITS CPU execution |
| **TTS Hindi Subsystem** (`Piper VITS HI`) | **60.22 MiB** (63.15 MB) | **~30.13 MiB** | Sherpa-ONNX VITS CPU execution |
| **Total Non-Duplicated Physical Footprint** | **270.94 MiB** (284.11 MB) | **~461.38 MiB** | Combined offline operating memory |
