# iTANTRA — Clean-Machine Setup & Deployment Guide
**Smart India Hackathon 2026 — Problem Statement SIH26173**  
**Frozen Baseline: Blocks 0–9.5**

---

## 1. Prerequisites

Before setting up on a fresh Windows machine:
1. **Operating System**: Windows 10 or Windows 11 (64-bit).
2. **Python**: Python 3.9 to 3.12 installed from [python.org](https://www.python.org/downloads/).  
   *(Crucial: Check **"Add python.exe to PATH"** during installation).*
3. **Git**: Git for Windows installed from [git-scm.com](https://git-scm.com/).
4. **Microphone & Speakers / Headset**: Working audio hardware.

---

## 2. 1-Click Automated Setup

Open **Command Prompt** (`cmd.exe`) or **PowerShell** and run:

```cmd
git clone https://github.com/jayanarayanmenonnettath2024aids/iTantra.git
cd iTantra
setup.bat
```

### What `setup.bat` does automatically:
1. Detects and validates Python installation.
2. Creates isolated virtual environment in `.venv`.
3. Upgrades `pip` and installs all packages from `requirements.txt`.
4. Executes `scripts/setup_models.py` to verify and pre-cache:
   - Silero VAD ONNX model
   - Whisper-Tiny Multilingual STT model
   - Piper INT8 TTS models (English, Hindi, Telugu, Malayalam)
   - AI4Bharat VITS-RASA Multilingual TTS model (Tamil, Kannada, Marathi, Bengali)
5. Executes `scripts/verify_setup.py` running live inference across all 8 neural languages.

---

## 3. Starting the Application

### Option A: Tactical Mission Control Web Dashboard (Recommended for Live Demo)
```cmd
.venv\Scripts\activate
python run_ui.py
```
> Opens `http://localhost:8000` automatically in your default browser.

### Option B: Interactive CLI Walkie-Talkie Node
```cmd
.venv\Scripts\activate
python run_demo.py
```

---

## 4. Two-Device Live Network Setup (Laptop A & Laptop B)

Connect both laptops to the same Wi-Fi router, local network switch, or mobile hotspot.

### Device A (Tactical Base Station)
```cmd
.venv\Scripts\activate
python run_ui.py --web-port 8000 --tcp-port 65432 --node-name BASE-ALPHA
```

### Device B (Field Unit)
```cmd
.venv\Scripts\activate
python run_ui.py --web-port 8000 --tcp-port 65432 --node-name FIELD-BRAVO
```

### Verification Steps on Live Two-Device Setup:
1. **Automatic Discovery**:
   - Both nodes will automatically detect each other via mDNS zero-configuration discovery (`_itantra._tcp.local.`).
   - The remote node will appear in the **"Discovered Tactical Nodes"** panel. Click **"Connect"** (or connection happens automatically).
2. **Push-To-Talk (PTT) Test**:
   - On Device A: Select language (e.g. English or Hindi), hold down **"PUSH TO TALK"**, speak *"Meet me at checkpoint four"*, and release.
   - On Device B: Within ~500–900 ms, Device B receives the 115-byte packet, verifies HMAC, and speaks the message in local neural audio.
3. **Hands-Free Voice Mode (VAD) Test**:
   - Toggle **"Hands-Free Voice Mode"**.
   - Speak naturally without clicking. Silero VAD detects speech boundaries, triggers STT, and transmits seamlessly.
4. **Priority & Distress Preemption Test**:
   - Send a normal voice note from Device A.
   - While playing, send an **ALERT** or **DISTRESS** message from Device B.
   - Observe immediate preemption of standard audio and activation of the Distress Lock indicator.

---

## 5. Manual Verification Commands

To independently re-verify the full system at any time:

```cmd
.venv\Scripts\activate

:: 1. Run Complete Automated Test Suite (210 tests)
python -m unittest discover -s tests -v

:: 2. Run Clean-Machine Subsystem Diagnostic
python scripts/verify_setup.py

:: 3. Re-download / Repair Missing Models
python scripts/setup_models.py
```

---

## 6. Troubleshooting

| Issue | Root Cause | Solution |
|---|---|---|
| `python is not recognized` | Python not added to system PATH | Reinstall Python and check "Add Python to PATH" |
| Windows Firewall Prompt | First time TCP socket binding | Click "Allow access" on Private Networks |
| mDNS Discovery not finding peer | AP Client Isolation on guest Wi-Fi | Use a mobile hotspot or direct manual IP connect (`/api/connect`) |
| Microphone permission denied | Browser mic access blocked | Click lock icon in browser URL bar $\rightarrow$ Allow Microphone |
