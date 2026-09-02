import os
import sys
import secrets

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from app.communication.packet_v2 import iTantraPacketV2
from app.security.authenticator import PacketAuthenticator
from app.security.trust_store import TrustStore

def run_bandwidth_benchmark():
    print("=" * 65)
    print("  iTANTRA BLOCK 8 — PRODUCTION PROTOCOL BANDWIDTH BENCHMARK  ")
    print("=" * 65)

    key = secrets.token_bytes(32)
    trust_store = TrustStore(trust_file=":memory:")
    trust_store.pair_device("NODE-RADIO", key)
    auth = PacketAuthenticator(trust_store=trust_store)

    test_payload = "Perimeter clear at sector 4."
    
    # 1. Unauthenticated Baseline
    pkt_unauth = iTantraPacketV2(payload=test_payload, sender_id="NODE-RADIO", sequence_number=1)
    unauth_bytes = pkt_unauth.to_binary()
    unauth_size = len(unauth_bytes)

    # 2. Block 7 (64-byte Hexadecimal HMAC)
    pkt_b7 = iTantraPacketV2(payload=test_payload, sender_id="NODE-RADIO", sequence_number=2)
    auth.sign_packet(pkt_b7, key, raw_binary=False)
    # Simulate Block 7 hex wire packing (64-byte tag string)
    b7_raw_tag = auth.compute_tag(key, pkt_b7._get_bytes_to_authenticate()).encode("ascii")
    # Pack manually with 64-byte tag
    pkt_b7.auth_tag = b7_raw_tag
    b7_bytes = pkt_b7.to_binary()
    b7_size = len(b7_bytes)

    # 3. Block 8 (32-byte Raw Binary HMAC)
    pkt_b8 = iTantraPacketV2(payload=test_payload, sender_id="NODE-RADIO", sequence_number=3)
    auth.sign_packet(pkt_b8, key, raw_binary=True)
    b8_bytes = pkt_b8.to_binary()
    b8_size = len(b8_bytes)

    # Metrics
    bytes_saved = b7_size - b8_size
    pct_reduction = (bytes_saved / b7_size) * 100.0
    payload_len = len(test_payload.encode("utf-8"))

    print(f"\n[1] EXACT WIRE PACKET SIZES (Payload: '{test_payload}', {payload_len} bytes):")
    print(f"    - Baseline (No Security):        {unauth_size} bytes")
    print(f"    - Block 7 (64-byte Hex HMAC):    {b7_size} bytes")
    print(f"    - Block 8 (32-byte Raw HMAC):    {b8_size} bytes")
    print(f"    - Wire Size Reduction:          -{bytes_saved} bytes (-{pct_reduction:.1f}%)")

    # Radio Baud Rate Transmission Calculations (Time = (Bytes * 8) / Baud)
    baud_rates = [300, 1200, 2400, 9600]
    radio_stats = []

    print(f"\n[2] TACTICAL RADIO TRANSMISSION LATENCY COMPARISON:")
    print(f"    {'Baud Rate':<12} | {'Block 7 (Hex)':<15} | {'Block 8 (Raw)':<15} | {'Time Saved':<12} | {'Savings %'}")
    print("    " + "-" * 65)

    for baud in baud_rates:
        t_b7 = (b7_size * 8) / baud * 1000.0  # ms
        t_b8 = (b8_size * 8) / baud * 1000.0  # ms
        t_saved = t_b7 - t_b8
        t_saved_pct = (t_saved / t_b7) * 100.0
        radio_stats.append((baud, t_b7, t_b8, t_saved, t_saved_pct))
        print(f"    {baud:>4} bps     | {t_b7:>8.1f} ms      | {t_b8:>8.1f} ms      | {t_saved:>7.1f} ms   | {t_saved_pct:>5.1f}%")

    # Generate Markdown Report
    rows = ""
    for baud, t_b7, t_b8, t_saved, t_saved_pct in radio_stats:
        rows += f"| **{baud} bps** | `{t_b7:.1f} ms` | `{t_b8:.1f} ms` | `-{t_saved:.1f} ms` | **-{t_saved_pct:.1f}%** |\n"

    report_content = f"""# iTANTRA — BLOCK 8 BANDWIDTH & RADIO EFFICIENCY BENCHMARK

## 1. Frame Wire Footprint Comparison

- **Text Payload Size**: `{payload_len}` bytes (`"{test_payload}"`)
- **Unauthenticated Binary Frame**: `{unauth_size}` bytes
- **Block 7 Secure Frame (64-byte Hex HMAC)**: `{b7_size}` bytes
- **Block 8 Secure Frame (32-byte Raw HMAC)**: `{b8_size}` bytes
- **Wire Bandwidth Reduction**: **`-{bytes_saved} bytes` (`-{pct_reduction:.1f}%`)**

---

## 2. Tactical Radio Airtime Transmission Comparison

Transmission airtime is calculated using `(Frame_Bytes * 8) / Baud_Rate`:

| Tactical Radio Channel | Block 7 Airtime (64B Hex) | Block 8 Airtime (32B Raw) | Airtime Reduction | Airtime Savings % |
|-------------------------|---------------------------|---------------------------|-------------------|-------------------|
{rows}
---

## 3. Findings & Radio Suitability

1. **Constrained HF / VHF Radio (300–1200 bps)**: Over low-bandwidth military tactical radios, saving 32 bytes cuts airtime latency by **{radio_stats[0][3]:.1f} ms** per transmission, reducing RF spectrum exposure and channel congestion.
2. **Standard Mesh / UHF Radio (9600 bps)**: Full secure tactical frames transmit in only **{radio_stats[3][2]:.1f} ms**.
3. **Cryptographic Strength**: Preserved 100% (256-bit HMAC-SHA256 digest integrity).
"""

    report_path = os.path.join(os.path.dirname(__file__), "../../docs/BLOCK8_BANDWIDTH_BENCHMARK.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"\n[+] Bandwidth benchmark written to {report_path}")

if __name__ == "__main__":
    run_bandwidth_benchmark()
