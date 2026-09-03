# iTANTRA — BLOCK 9.5 AI4BHARAT VITS-RASA INTEGRATION

## 1. Overview & Architecture

Block 9.5 successfully integrates the **AI4Bharat VITS-RASA** multilingual neural Text-to-Speech (TTS) engine (`NeuralVitsRasaTTSEngine`) as a modular offline backend alongside the existing Piper VITS engine.

This integration expands local offline neural TTS coverage to:
- **Tamil (`ta`)**
- **Kannada (`kn`)**
- **Marathi (`mr`)**
- **Bengali (`bn`)**
- *(Also verifies multi-engine support for **Telugu (`te`)** and **Malayalam (`ml`)**)*

---

## 2. Zero-Regression Architecture

```
                       ┌───────────────────────┐
                       │     ModelManager      │
                       └───────────┬───────────┘
                                   │
              ┌────────────────────┴────────────────────┐
              ▼                                         ▼
   ┌───────────────────────┐               ┌────────────────────────┐
   │ NeuralONNXTTSEngine   │               │ NeuralVitsRasaTTSEngine│
   │      (Piper VITS)     │               │ (AI4Bharat VITS-RASA)  │
   │  en, hi, te, ml (INT8)│               │  ta, kn, mr, bn (FP32) │
   └───────────────────────┘               └────────────────────────┘
```

- **Zero Cloud / Fallback Policy**: SAPI5, pyttsx3, and cloud APIs remain strictly prohibited.
- **Single Source of Truth**: All routing is managed dynamically by `ModelManager` and `DEFAULT_LANGUAGE_REGISTRY`.
- **Grapheme Token Matching**: VITS-RASA uses direct Unicode character token maps in `tokens.txt`, completely eliminating the multi-character lexicon assertion crashes observed in Piper Indic models.
