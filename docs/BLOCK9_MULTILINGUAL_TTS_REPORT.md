# iTANTRA — BLOCK 9 MULTILINGUAL TTS EXPANSION REPORT

## 1. Ecosystem Audit for Missing Indic Languages

We audited the open-source offline neural TTS ecosystem (Sherpa-ONNX, Piper VITS, MMS-TTS, AI4Bharat) for the 5 STT-capable but TTS-missing languages: **Tamil (`ta`)**, **Gujarati (`gu`)**, **Marathi (`mr`)**, **Kannada (`kn`)**, and **Bengali (`bn`)**.

| Language | Candidate Model / Source | Architecture | Evaluation Outcome | Status |
|----------|--------------------------|--------------|--------------------|--------|
| **Tamil (`ta`)** | Piper Indic Community | Piper VITS | No official released ONNX weights in Sherpa-ONNX repository. | **STT ONLY** |
| **Gujarati (`gu`)** | Piper Indic Community | Piper VITS | No official released ONNX weights in Sherpa-ONNX repository. | **STT ONLY** |
| **Marathi (`mr`)** | `mr_IN-google-medium` | Piper VITS ONNX | C++ multi-character IPA parsing crash in `piper-phonemize-lexicon.cc:ReadTokens:117` due to unsegmented diphthongs. | **STT ONLY** |
| **Kannada (`kn`)** | Piper Indic Community | Piper VITS | No official released ONNX weights in Sherpa-ONNX repository. | **STT ONLY** |
| **Bengali (`bn`)** | `bn_BD-google-medium` | Piper VITS ONNX | C++ multi-character IPA parsing crash in `piper-phonemize-lexicon.cc:ReadTokens:117`. | **STT ONLY** |
| **Odia (`or`)** | IndicWhisper / MMS | Whisper / VITS | Absent from `whisper-tiny` vocabulary; alternative models exceed 1 GB edge footprint. | **DEFERRED** |

---

## 2. Final Frozen 10-Language Capability Matrix

| Language | Code | STT Engine | STT Status | TTS Engine | TTS Status | Explicit Classification |
|----------|------|------------|------------|------------|------------|-------------------------|
| **English** | `en` | `whisper-tiny` | **VERIFIED** | `vits-piper-en_US-lessac` | **VERIFIED (INT8)** | **SUPPORTED + VERIFIED** |
| **Hindi** | `hi` | `whisper-tiny` | **VERIFIED** | `vits-piper-hi_IN-pratham` | **VERIFIED (INT8)** | **SUPPORTED + VERIFIED** |
| **Telugu** | `te` | `whisper-tiny` | **VERIFIED** | `vits-piper-te_IN-maya` | **VERIFIED (INT8)** | **SUPPORTED + VERIFIED** |
| **Malayalam** | `ml` | `whisper-tiny` | **VERIFIED** | `vits-piper-ml_IN-meera` | **VERIFIED (INT8)** | **SUPPORTED + VERIFIED** |
| **Tamil** | `ta` | `whisper-tiny` | **VERIFIED** | None | UNAVAILABLE | **STT ONLY** |
| **Gujarati** | `gu` | `whisper-tiny` | **VERIFIED** | None | UNAVAILABLE | **STT ONLY** |
| **Marathi** | `mr` | `whisper-tiny` | **VERIFIED** | None | UNAVAILABLE | **STT ONLY** |
| **Kannada** | `kn` | `whisper-tiny` | **VERIFIED** | None | UNAVAILABLE | **STT ONLY** |
| **Bengali** | `bn` | `whisper-tiny` | **VERIFIED** | None | UNAVAILABLE | **STT ONLY** |
| **Odia** | `or` | None | UNAVAILABLE | None | UNAVAILABLE | **DEFERRED** |

---

## 3. Strict Compliance Policy

- **Zero Cloud / Fallback Policy**: Windows SAPI5, `pyttsx3`, and cloud APIs are strictly disabled in production.
- Languages with `STT ONLY` transcribe incoming voice messages into accurate UTF-8 text; TTS synthesis gracefully raises `ModelNotInstalledError` rather than fabricating speech.
