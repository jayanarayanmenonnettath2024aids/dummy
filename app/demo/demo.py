import os
import time
import socket
from typing import Optional
import soundfile as sf

from app.stt.engine import BaseSTTEngine, WhisperSTTEngine
from app.tts.engine import BaseTTSEngine, LocalTTSEngine
from app.communication.interface import iTantraPacket
from app.communication.tcp_transport import TCPTransport
from app.metrics.metrics import (
    Fore,
    Style,
    PipelineMetrics,
    render_transmission_box,
    render_reception_box,
    render_bandwidth_comparison,
    render_latency_breakdown,
    render_dashboard
)

class iTantraDemo:
    """
    Demo coordinator supporting:
    1. Single-node local loop (Mic -> STT -> TTS -> Speaker)
    2. Distributed Transmitter node (Mic -> STT -> TCP Text Packet)
    3. Distributed Receiver node (TCP Text Packet -> TTS -> Speaker)
    """
    def __init__(self, stt_engine: Optional[BaseSTTEngine] = None, tts_engine: Optional[BaseTTSEngine] = None):
        self._stt = stt_engine
        self._tts = tts_engine

    @property
    def stt(self) -> BaseSTTEngine:
        if self._stt is None:
            self._stt = WhisperSTTEngine()
        return self._stt

    @property
    def tts(self) -> BaseTTSEngine:
        if self._tts is None:
            self._tts = LocalTTSEngine()
        return self._tts

    def run_local_loop(self, audio_source: str = "LIVE", sample_path: Optional[str] = None, language: str = "en"):
        """
        Phase 3: Complete single-machine neural voice loop.
        """
        print("\n" + "="*56)
        print("          STARTING LOCAL NEURAL VOICE LOOP")
        print("="*56)
        
        t1 = time.time()
        audio_bytes_len = 0
        
        if audio_source == "LIVE":
            print("[*] Recording 4.0 seconds of audio from microphone...")
            audio_data = self.stt.record_microphone(duration_seconds=4.0)
            # Calculate raw uncompressed 16-bit 16kHz PCM audio bytes
            audio_bytes_len = len(audio_data) * 2  # 2 bytes per 16-bit sample
            transcript, stt_latency = self.stt.transcribe(audio_data, language=language)
        else:
            if not sample_path or not os.path.exists(sample_path):
                raise FileNotFoundError(f"Sample WAV not found: {sample_path}")
            print(f"[*] Loading demo sample: {sample_path}")
            audio_bytes_len = os.path.getsize(sample_path)
            transcript, stt_latency = self.stt.transcribe(sample_path, language=language)

        t2 = time.time()
        print(f"[+] STT Transcript : \"{transcript}\" (Latency: {stt_latency*1000:.1f}ms)")
        
        # Local TTS synthesis
        print("[*] Synthesizing speech locally via TTS...")
        t_tts_start = time.perf_counter()
        out_wav, tts_latency = self.tts.synthesize(transcript, language=language, play_audio=True)
        t5 = time.time()

        # Metrics collection
        text_bytes = len(transcript.encode('utf-8'))
        total_e2e_latency = (stt_latency + tts_latency) * 1000.0

        metrics = PipelineMetrics(
            audio_size_bytes=audio_bytes_len,
            text_payload_bytes=text_bytes,
            total_packet_bytes=text_bytes,
            stt_latency_ms=stt_latency * 1000.0,
            network_latency_ms=0.0,
            tts_latency_ms=tts_latency * 1000.0,
            end_to_end_latency_ms=total_e2e_latency,
            transcript=transcript,
            language=language,
            audio_transmitted=False
        )

        render_bandwidth_comparison(audio_bytes_len, text_bytes, text_bytes)
        render_latency_breakdown(metrics.stt_latency_ms, 0.0, metrics.tts_latency_ms, metrics.end_to_end_latency_ms)
        render_dashboard("LOCAL_LOOP", language, transcript, metrics)

    def run_transmitter(self, host: str, port: int, audio_source: str = "LIVE", sample_path: Optional[str] = None, language: str = "en"):
        """
        Phase 4 & 5: Device A (Transmitter) pipeline.
        Microphone / WAV -> Local STT -> Text Packet -> TCP Transmission.
        """
        print("\n" + "="*56)
        print(f"       iTANTRA TRANSMITTER NODE -> {host}:{port}")
        print("="*56)

        t1 = time.time()
        audio_bytes_len = 0
        
        if audio_source == "LIVE":
            print("[*] Recording 4.0 seconds of audio from microphone...")
            audio_data = self.stt.record_microphone(duration_seconds=4.0)
            audio_bytes_len = len(audio_data) * 2
            transcript, stt_latency = self.stt.transcribe(audio_data, language=language)
        else:
            if not sample_path or not os.path.exists(sample_path):
                raise FileNotFoundError(f"Sample WAV not found: {sample_path}")
            print(f"[*] Loading demo sample: {sample_path}")
            audio_bytes_len = os.path.getsize(sample_path)
            transcript, stt_latency = self.stt.transcribe(sample_path, language=language)

        t2 = time.time()

        # Create structured packet
        packet = iTantraPacket(
            payload=transcript,
            language=language,
            sender_id=socket.gethostname(),
            audio_size_bytes=audio_bytes_len,
            t1_capture_start=t1,
            t2_stt_finish=t2
        )

        text_bytes = packet.get_text_payload_bytes()
        packet_bytes = packet.get_total_packet_bytes()

        render_transmission_box(transcript, packet_bytes, transport=f"TCP ({host}:{port})")
        render_bandwidth_comparison(audio_bytes_len, text_bytes, packet_bytes)

        # Transmit over network
        transport = TCPTransport(host=host, port=port, is_server=False)
        print(f"[*] Transmitting data payload to Receiver at {host}:{port}...")
        success, net_latency, bytes_sent = transport.send(packet)
        
        if success:
            print(f"{Fore.GREEN}[OK] Transmission successful! (Network RTT: {net_latency*1000:.1f}ms, Sent: {bytes_sent} bytes){Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}[FAIL] Transmission failed. Check if Receiver node is running at {host}:{port}.{Style.RESET_ALL}")

    def run_receiver(self, host: str = "0.0.0.0", port: int = 65432):
        """
        Phase 4 & 5: Device B (Receiver) pipeline.
        TCP Packet -> Text Extraction -> Local TTS -> Speaker.
        """
        print("\n" + "="*56)
        print(f"       iTANTRA RECEIVER NODE (Listening on port {port})")
        print("="*56)
        print("[*] Ready. Waiting for incoming transmission from Transmitter...")

        transport = TCPTransport(host=host, port=port, is_server=True, timeout=120.0)
        try:
            packet, rx_latency, bytes_recv = transport.receive()
            if not packet:
                print("[!] Timeout or error waiting for incoming packet.")
                return

            render_reception_box(packet.payload, bytes_recv)

            # Local TTS synthesis
            print(f"[*] Synthesizing speech locally for received message ({packet.language})...")
            out_wav, tts_latency = self.tts.synthesize(packet.payload, language=packet.language, play_audio=True)
            t5 = time.time()

            # Latency calculations
            stt_latency_ms = (packet.t2_stt_finish - packet.t1_capture_start) * 1000.0 if packet.t1_capture_start else 0.0
            net_latency_ms = (packet.t4_rx_finish - packet.t3_tx_start) * 1000.0 if packet.t3_tx_start else rx_latency * 1000.0
            if net_latency_ms < 0:
                net_latency_ms = rx_latency * 1000.0
            tts_latency_ms = tts_latency * 1000.0
            total_e2e_ms = stt_latency_ms + net_latency_ms + tts_latency_ms

            metrics = PipelineMetrics(
                audio_size_bytes=packet.audio_size_bytes,
                text_payload_bytes=packet.get_text_payload_bytes(),
                total_packet_bytes=bytes_recv,
                stt_latency_ms=stt_latency_ms,
                network_latency_ms=net_latency_ms,
                tts_latency_ms=tts_latency_ms,
                end_to_end_latency_ms=total_e2e_ms,
                transcript=packet.payload,
                language=packet.language,
                audio_transmitted=False
            )

            render_bandwidth_comparison(packet.audio_size_bytes, packet.get_text_payload_bytes(), bytes_recv)
            render_latency_breakdown(stt_latency_ms, net_latency_ms, tts_latency_ms, total_e2e_ms)
            render_dashboard("RECEIVER", packet.language, packet.payload, metrics)

        finally:
            transport.close()
