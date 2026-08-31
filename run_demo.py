#!/usr/bin/env python3
"""
iTantra: Offline Low-Data-Rate Speech-to-Speech Communication Prototype
Smart India Hackathon 2026 — Problem Statement SIH26173

Architecture:
Speech -> Local STT -> Text Payload -> Network Transmission -> Text Payload -> Local TTS -> Speech
"""

import sys
import os
import argparse
from typing import Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
except ImportError:
    class DummyColor:
        def __getattr__(self, name):
            return ""
    Fore = DummyColor()
    Style = DummyColor()

from app.stt.engine import WhisperSTTEngine
from app.tts.engine import LocalTTSEngine
from app.demo.demo import iTantraDemo

def print_banner():
    banner = f"""
{Fore.CYAN}{Style.BRIGHT}========================================================================
   _ _____             _             
  (_)  ___|           | |            
   _| |_ __ _ _ __  __| |__  _ __ __ _ 
  | |  _/ _` | '_ \\/ _` | '_ \\| '__/ _` |
  | | || (_| | | | | (_| | |_) | | | (_| |
  |_|\\_|\\__,_|_| |_|\\__,_|_.__/|_|  \\__,_|
  
  Offline Speech-to-Speech over Low-Bandwidth Transport Links
  Smart India Hackathon 2026 -- SIH26173
========================================================================{Style.RESET_ALL}
{Fore.GREEN}[OK] 100% Local Inference  |  [OK] Zero Cloud API  |  [OK] Internet-Independent
[OK] Audio NOT Transmitted  |  [OK] Text-Only Transport Payload{Fore.RESET}
========================================================================
"""
    print(banner)


def interactive_menu():
    print_banner()
    print(f"{Fore.YELLOW}Select Operation Mode:{Style.RESET_ALL}")
    print("  [1] Single Node Local Loop  (Mic/Sample -> Local STT -> Local TTS -> Speaker)")
    print("  [2] Transmitter Node (Device A)  (Mic/Sample -> Local STT -> TCP Text Packet)")
    print("  [3] Receiver Node (Device B)     (TCP Text Packet -> Local TTS -> Speaker)")
    print("  [4] Run Unit & Integration Test Suite")
    print("  [5] Exit\n")

    choice = input(f"{Fore.CYAN}Enter selection [1-5] (default: 1): {Style.RESET_ALL}").strip() or "1"
    
    if choice == "5":
        print("[*] Exiting iTantra.")
        sys.exit(0)
    elif choice == "4":
        import unittest
        loader = unittest.TestLoader()
        suite = loader.discover("tests")
        runner = unittest.TextTestRunner(verbosity=2)
        runner.run(suite)
        return

    # Language selection
    print(f"\n{Fore.YELLOW}Select Language:{Style.RESET_ALL}")
    print("  [1] English (en) - Default")
    print("  [2] Tamil (ta)")
    lang_choice = input(f"{Fore.CYAN}Enter language [1-2] (default: 1): {Style.RESET_ALL}").strip() or "1"
    language = "ta" if lang_choice == "2" else "en"

    # For Receiver node, no audio source selection needed
    if choice == "3":
        port_input = input(f"{Fore.CYAN}Enter listening port (default: 65432): {Style.RESET_ALL}").strip() or "65432"
        demo = iTantraDemo()
        demo.run_receiver(host="0.0.0.0", port=int(port_input))
        return

    # Audio source selection for Transmitter and Local Loop
    print(f"\n{Fore.YELLOW}Select Audio Input Mode:{Style.RESET_ALL}")
    print("  [1] LIVE Microphone Input (Speak for 4 seconds)")
    print("  [2] FALLBACK Pre-recorded Demo Sample (Checkpoint sample)")
    print("  [3] FALLBACK Pre-recorded Demo Sample (Emergency team sample)")
    print("  [4] FALLBACK Pre-recorded Demo Sample (Rescue base sample)")
    
    src_choice = input(f"{Fore.CYAN}Enter audio mode [1-4] (default: 2): {Style.RESET_ALL}").strip() or "2"
    
    sample_path = None
    if src_choice == "1":
        audio_source = "LIVE"
    elif src_choice == "3":
        audio_source = "FALLBACK"
        sample_path = "samples/emergency_en.wav"
    elif src_choice == "4":
        audio_source = "FALLBACK"
        sample_path = "samples/rescue_en.wav"
    else:
        audio_source = "FALLBACK"
        sample_path = "samples/checkpoint_en.wav"

    demo = iTantraDemo()

    if choice == "1":
        demo.run_local_loop(audio_source=audio_source, sample_path=sample_path, language=language)
    elif choice == "2":
        host_input = input(f"{Fore.CYAN}Enter Receiver IP (default: 127.0.0.1): {Style.RESET_ALL}").strip() or "127.0.0.1"
        port_input = input(f"{Fore.CYAN}Enter Receiver Port (default: 65432): {Style.RESET_ALL}").strip() or "65432"
        demo.run_transmitter(host=host_input, port=int(port_input), audio_source=audio_source, sample_path=sample_path, language=language)


def main():
    parser = argparse.ArgumentParser(description="iTantra: Offline Low-Data-Rate Speech-to-Speech Communication Prototype")
    parser.add_argument("--mode", choices=["local", "tx", "rx"], help="Execution mode (local loop, transmitter, receiver)")
    parser.add_argument("--source", choices=["live", "fallback"], default="fallback", help="Audio source: live microphone or fallback sample WAV")
    parser.add_argument("--sample", type=str, default="samples/checkpoint_en.wav", help="Path to fallback sample WAV file")
    parser.add_argument("--lang", type=str, default="en", help="Language code ('en' or 'ta')")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Target host / bind address for network")
    parser.add_argument("--port", type=int, default=65432, help="Network port (default: 65432)")

    args = parser.parse_args()

    if args.mode is None:
        interactive_menu()
    else:
        print_banner()
        demo = iTantraDemo()
        if args.mode == "local":
            demo.run_local_loop(
                audio_source="LIVE" if args.source == "live" else "FALLBACK",
                sample_path=args.sample,
                language=args.lang
            )
        elif args.mode == "tx":
            demo.run_transmitter(
                host=args.host,
                port=args.port,
                audio_source="LIVE" if args.source == "live" else "FALLBACK",
                sample_path=args.sample,
                language=args.lang
            )
        elif args.mode == "rx":
            demo.run_receiver(
                host=args.host if args.host != "127.0.0.1" else "0.0.0.0",
                port=args.port
            )

if __name__ == "__main__":
    main()
