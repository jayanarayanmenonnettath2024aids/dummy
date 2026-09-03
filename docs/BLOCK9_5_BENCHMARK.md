# iTANTRA — BLOCK 9.5 VITS-RASA BENCHMARK REPORT

## 1. Measured Performance Breakdown (x86_64 CPU)

| Language | Test Phrase | Duration | Latency | Real-Time Factor (RTF) | Sample Rate | Max Amplitude | Status |
|----------|-------------|----------|---------|------------------------|-------------|---------------|--------|
| **Tamil (`ta`)** | கட்டளை மையத்திற்கு தகவல் தெரிவிக்கவும் | `2.49 s` | `796.4 ms` | `0.320` | `24,000 Hz` | `0.4901` | **PASS (Clean)** |
| **Kannada (`kn`)** | ಆದೇಶ ಕೇಂದ್ರಕ್ಕೆ ಮಾಹಿತಿ ನೀಡಿರಿ | `1.80 s` | `581.6 ms` | `0.323` | `24,000 Hz` | `0.3700` | **PASS (Clean)** |
| **Marathi (`mr`)** | कमांड केंद्राला माहिती द्या | `1.61 s` | `510.8 ms` | `0.317` | `24,000 Hz` | `0.4483` | **PASS (Clean)** |
| **Bengali (`bn`)** | কমান্ড সেন্টারে তথ্য পাঠান | `1.77 s` | `573.5 ms` | `0.324` | `24,000 Hz` | `0.4331` | **PASS (Clean)** |
| **Telugu (`te`)** | కమాండ్ పోస్ట్‌కు నివేదించండి | `1.79 s` | `578.8 ms` | `0.323` | `24,000 Hz` | `0.5291` | **PASS (Clean)** |
| **Malayalam (`ml`)** | കമാൻഡ് പോസ്റ്റിൽ റിപ്പോർട്ട് ചെയ്യുക | `1.98 s` | `635.5 ms` | `0.320` | `24,000 Hz` | `0.3869` | **PASS (Clean)** |

---

## 2. FP32 vs Dynamic INT8 Quantization Findings

| Metric | FP32 VITS-RASA | Dynamic INT8 VITS-RASA | Engineering Finding |
|--------|----------------|------------------------|---------------------|
| **Model Size** | `117.62 MiB` | `38.77 MiB` (-67.0%) | INT8 achieves substantial disk savings |
| **Synthesis Latency (Tamil)** | **`796.4 ms`** | `10,609.1 ms` (+1232%) | **13.3x slowdown in INT8** |
| **Real-Time Factor (RTF)** | **`0.320` (3.1x realtime)** | `4.605` (4.6x slower than realtime) | Flow spline un-fused ops stall CPU INT8 |
| **Production Decision** | **SELECTED FOR PRODUCTION** | ARCHIVED / BENCHMARK ONLY | **Retain FP32 for sub-second low-latency voice** |
