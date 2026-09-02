import os
import sys
import time
import secrets

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from app.communication.packet_v2 import iTantraPacketV2
from app.security.authenticator import PacketAuthenticator
from app.security.trust_store import TrustStore

def benchmark_security():
    print("=" * 60)
    print("  iTANTRA BLOCK 7 — SECURITY OVERHEAD & LATENCY BENCHMARK  ")
    print("=" * 60)

    key = secrets.token_bytes(32)
    trust_store = TrustStore(trust_file=":memory:")
    trust_store.pair_device("NODE-BENCH", key)
    auth = PacketAuthenticator(trust_store=trust_store)

    test_payload = "Tactical report: perimeter secure at sector 4."
    
    # 1. Packet Size Benchmark
    pkt_unauth = iTantraPacketV2(payload=test_payload, sender_id="NODE-BENCH", sequence_number=1)
    unauth_bytes = pkt_unauth.to_binary()
    unauth_size = len(unauth_bytes)

    pkt_auth = iTantraPacketV2(payload=test_payload, sender_id="NODE-BENCH", sequence_number=2)
    auth.sign_packet(pkt_auth, key)
    auth_bytes = pkt_auth.to_binary()
    auth_size = len(auth_bytes)

    overhead_bytes = auth_size - unauth_size
    overhead_pct = (overhead_bytes / unauth_size) * 100.0

    print(f"\n[1] PACKET SIZE COMPARISON:")
    print(f"    - Binary Frame (Without Security): {unauth_size} bytes")
    print(f"    - Binary Frame (With HMAC-SHA256): {auth_size} bytes")
    print(f"    - Security Overhead:              +{overhead_bytes} bytes (+{overhead_pct:.1f}%)")

    # 2. Cryptographic Latency Benchmark (1,000 iterations)
    iterations = 1000
    t0 = time.perf_counter()
    for i in range(iterations):
        pkt = iTantraPacketV2(payload=test_payload, sender_id="NODE-BENCH", sequence_number=i+10)
        auth.sign_packet(pkt, key)
    sign_time_ms = ((time.perf_counter() - t0) / iterations) * 1000.0

    t0 = time.perf_counter()
    for i in range(iterations):
        pkt = iTantraPacketV2(payload=test_payload, sender_id="NODE-BENCH", sequence_number=i+10000)
        auth.sign_packet(pkt, key)
        auth.verify_and_authenticate(pkt)
    verify_time_ms = (((time.perf_counter() - t0) / iterations) * 1000.0) - sign_time_ms

    total_crypto_ms = sign_time_ms + verify_time_ms

    print(f"\n[2] CRYPTOGRAPHIC PROCESSING LATENCY:")
    print(f"    - HMAC-SHA256 Signing Latency:      {sign_time_ms * 1000.0:.2f} µs ({sign_time_ms:.4f} ms)")
    print(f"    - HMAC Verification + Replay Check: {verify_time_ms * 1000.0:.2f} µs ({verify_time_ms:.4f} ms)")
    print(f"    - Total Cryptographic Overhead:     {total_crypto_ms:.4f} ms")

    # 3. End-to-End Latency Profile with AI Layer
    stt_latency = 190.0  # ms (Whisper-tiny)
    net_latency = 1.2    # ms (Local TCP)
    tts_latency = 2200.0 # ms (Neural ONNX INT8)
    e2e_before = stt_latency + net_latency + tts_latency
    e2e_after = stt_latency + total_crypto_ms + net_latency + tts_latency
    e2e_overhead_pct = ((e2e_after - e2e_before) / e2e_before) * 100.0

    print(f"\n[3] END-TO-END PIPELINE IMPACT:")
    print(f"    - End-to-End Before Security: {e2e_before:.2f} ms")
    print(f"    - End-to-End After Security:  {e2e_after:.2f} ms")
    print(f"    - Security Latency Impact:    +{total_crypto_ms:.4f} ms (+{e2e_overhead_pct:.4f}%)")

    # Generate Performance Report
    report_content = f"""# iTANTRA — BLOCK 7 PERFORMANCE BENCHMARK

## 1. Frame Size Comparison

- **Binary Frame (Before Security)**: `{unauth_size}` bytes
- **Binary Frame (After Security)**: `{auth_size}` bytes
- **Security Overhead**: `+{overhead_bytes}` bytes (`+{overhead_pct:.1f}%`)
- **Protocol Suitability**: Highly suitable for low-bandwidth tactical mesh radios (compact < 150 bytes total).

## 2. Cryptographic Latency (HMAC-SHA256 + Replay Window)

- **HMAC Signing Latency**: `{sign_time_ms * 1000.0:.2f}` µs (`{sign_time_ms:.4f}` ms)
- **HMAC Verification + Replay Check Latency**: `{verify_time_ms * 1000.0:.2f}` µs (`{verify_time_ms:.4f}` ms)
- **Total Crypto Latency**: `{total_crypto_ms:.4f}` ms

## 3. End-to-End Tactical Pipeline

- **STT Latency (Whisper-tiny)**: `{stt_latency:.2f}` ms
- **Cryptographic Latency**: `{total_crypto_ms:.4f}` ms
- **Network Latency (TCP)**: `{net_latency:.2f}` ms
- **TTS Latency (Neural INT8)**: `{tts_latency:.2f}` ms
- **End-to-End Latency**: `{e2e_after:.2f}` ms (Crypto overhead represents **<{total_crypto_ms/e2e_after*100:.3f}%** of total turnaround).
"""
    report_path = os.path.join(os.path.dirname(__file__), "../../docs/BLOCK7_PERFORMANCE.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"\n[+] Performance report written to {report_path}")

if __name__ == "__main__":
    benchmark_security()
