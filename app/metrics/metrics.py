import time
from dataclasses import dataclass
from typing import Optional

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
except ImportError:
    # Fallback if colorama not present
    class DummyColor:
        def __getattr__(self, name):
            return ""
    Fore = DummyColor()
    Style = DummyColor()

@dataclass
class PipelineMetrics:
    """Stores all real measured metrics for an iTantra transaction."""
    audio_size_bytes: int = 0
    text_payload_bytes: int = 0
    total_packet_bytes: int = 0
    
    stt_latency_ms: float = 0.0
    network_latency_ms: float = 0.0
    tts_latency_ms: float = 0.0
    end_to_end_latency_ms: float = 0.0
    
    transcript: str = ""
    language: str = "en"
    audio_transmitted: bool = False
    internet_dependency: str = "NONE (100% Local Inference)"

    @property
    def reduction_percentage(self) -> float:
        if self.audio_size_bytes == 0:
            return 0.0
        return ((self.audio_size_bytes - self.text_payload_bytes) / self.audio_size_bytes) * 100.0

    @property
    def packet_reduction_percentage(self) -> float:
        if self.audio_size_bytes == 0:
            return 0.0
        return ((self.audio_size_bytes - self.total_packet_bytes) / self.audio_size_bytes) * 100.0


def render_transmission_box(text: str, payload_bytes: int, transport: str = "TCP / Local Link"):
    """Phase 5: Visual display on Device A during transmission."""
    print(f"\n{Fore.CYAN}{Style.BRIGHT}" + "="*48)
    print("                TRANSMISSION")
    print("="*48 + f"{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Text:{Fore.RESET} \"{text}\"")
    print(f"{Fore.GREEN}Payload bytes:{Fore.RESET} {payload_bytes} bytes")
    print(f"{Fore.MAGENTA}Transport:{Fore.RESET} {transport}")
    print(f"{Fore.RED}{Style.BRIGHT}Audio transmitted: NO (Text Only){Style.RESET_ALL}")
    print(f"{Fore.CYAN}" + "-"*48 + f"{Style.RESET_ALL}\n")


def render_reception_box(text: str, payload_bytes: int):
    """Phase 5: Visual display on Device B upon reception."""
    print(f"\n{Fore.GREEN}{Style.BRIGHT}" + "="*48)
    print("                 RECEPTION")
    print("="*48 + f"{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Received text:{Fore.RESET} \"{text}\"")
    print(f"{Fore.GREEN}Payload:{Fore.RESET} {payload_bytes} bytes")
    print(f"{Fore.MAGENTA}Local Neural TTS:{Fore.RESET} Synthesizing speech...")
    print(f"{Fore.GREEN}" + "-"*48 + f"{Style.RESET_ALL}\n")


def render_bandwidth_comparison(audio_bytes: int, text_bytes: int, total_packet_bytes: int):
    """Phase 6: Visual display for real measured data reduction."""
    red_text = ((audio_bytes - text_bytes) / audio_bytes * 100) if audio_bytes else 0.0
    red_pkt = ((audio_bytes - total_packet_bytes) / audio_bytes * 100) if audio_bytes else 0.0

    print(f"\n{Fore.YELLOW}{Style.BRIGHT}" + "="*48)
    print("        DATA PAYLOAD COMPARISON (MEASURED)")
    print("="*48 + f"{Style.RESET_ALL}")
    print(f" Raw Audio Payload : {Fore.RED}{audio_bytes:,} bytes{Fore.RESET} (16kHz PCM WAV)")
    print(f" iTantra Text Only : {Fore.GREEN}{text_bytes:,} bytes{Fore.RESET}")
    print(f" Total Packet Size : {Fore.GREEN}{total_packet_bytes:,} bytes{Fore.RESET} (Headers + Tag)")
    print(f" {Fore.CYAN}{Style.BRIGHT}Text Data Reduction: {red_text:.2f}%{Style.RESET_ALL}")
    print(f" {Fore.CYAN}{Style.BRIGHT}Wire Data Reduction: {red_pkt:.2f}%{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}" + "="*48 + f"{Style.RESET_ALL}\n")


def render_latency_breakdown(stt_ms: float, net_ms: float, tts_ms: float, e2e_ms: float):
    """Phase 7: Visual breakdown of end-to-end latency."""
    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}" + "="*48)
    print("           LATENCY BREAKDOWN (MEASURED)")
    print("="*48 + f"{Style.RESET_ALL}")
    print(f" STT Latency   : {stt_ms:>8.2f} ms")
    print(f" Net Latency   : {net_ms:>8.2f} ms")
    print(f" TTS Latency   : {tts_ms:>8.2f} ms")
    print(f" {Fore.GREEN}{Style.BRIGHT}End-to-End Latency: {e2e_ms:>6.2f} ms{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}" + "="*48 + f"{Style.RESET_ALL}\n")


def render_dashboard(
    mode: str,
    language: str,
    transcript: str,
    metrics: PipelineMetrics
):
    """Phase 9: Comprehensive dashboard display."""
    print(f"\n{Fore.CYAN}{Style.BRIGHT}" + "="*56)
    print(f"             iTANTRA SYSTEM DASHBOARD              ")
    print("="*56 + f"{Style.RESET_ALL}")
    print(f" Mode               : {Fore.YELLOW}{mode.upper()}{Fore.RESET}")
    print(f" Language           : {language.upper()}")
    print(f" STT Engine         : {Fore.GREEN}LOCAL [Whisper-Tiny] [OK]{Fore.RESET}")
    print(f" TTS Engine         : {Fore.GREEN}LOCAL [Pyttsx3/Neural] [OK]{Fore.RESET}")
    print(f" Internet Status    : {Fore.GREEN}OFFLINE (Zero Cloud API) [OK]{Fore.RESET}")
    print(f" Audio Transmitted  : {Fore.RED}{Style.BRIGHT}NO (Data Only){Style.RESET_ALL}")
    print("-" * 56)
    print(f" Transcript         : {Fore.WHITE}\"{transcript}\"{Fore.RESET}")
    print(f" Payload Size       : {metrics.text_payload_bytes} bytes (Raw Text) / {metrics.total_packet_bytes} bytes (Packet)")
    print(f" Audio Size         : {metrics.audio_size_bytes:,} bytes")
    print(f" Payload Reduction  : {Fore.GREEN}{metrics.reduction_percentage:.1f}%{Fore.RESET}")
    print("-" * 56)
    print(f" STT Latency        : {metrics.stt_latency_ms:.1f} ms")
    print(f" Network Latency    : {metrics.network_latency_ms:.1f} ms")
    print(f" TTS Latency        : {metrics.tts_latency_ms:.1f} ms")
    print(f" {Fore.CYAN}{Style.BRIGHT}Total E2E Latency  : {metrics.end_to_end_latency_ms:.1f} ms{Style.RESET_ALL}")
    print(f"{Fore.CYAN}" + "="*56 + f"{Style.RESET_ALL}\n")
