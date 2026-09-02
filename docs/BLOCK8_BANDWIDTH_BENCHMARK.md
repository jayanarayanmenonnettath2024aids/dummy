# iTANTRA — BLOCK 8 BANDWIDTH & RADIO EFFICIENCY BENCHMARK

## 1. Frame Wire Footprint Comparison

- **Text Payload Size**: `28` bytes (`"Perimeter clear at sector 4."`)
- **Unauthenticated Binary Frame**: `75` bytes
- **Block 7 Secure Frame (64-byte Hex HMAC)**: `139` bytes
- **Block 8 Secure Frame (32-byte Raw HMAC)**: `107` bytes
- **Wire Bandwidth Reduction**: **`-32 bytes` (`-23.0%`)**

---

## 2. Tactical Radio Airtime Transmission Comparison

Transmission airtime is calculated using `(Frame_Bytes * 8) / Baud_Rate`:

| Tactical Radio Channel | Block 7 Airtime (64B Hex) | Block 8 Airtime (32B Raw) | Airtime Reduction | Airtime Savings % |
|-------------------------|---------------------------|---------------------------|-------------------|-------------------|
| **300 bps** | `3706.7 ms` | `2853.3 ms` | `-853.3 ms` | **-23.0%** |
| **1200 bps** | `926.7 ms` | `713.3 ms` | `-213.3 ms` | **-23.0%** |
| **2400 bps** | `463.3 ms` | `356.7 ms` | `-106.7 ms` | **-23.0%** |
| **9600 bps** | `115.8 ms` | `89.2 ms` | `-26.7 ms` | **-23.0%** |

---

## 3. Findings & Radio Suitability

1. **Constrained HF / VHF Radio (300–1200 bps)**: Over low-bandwidth military tactical radios, saving 32 bytes cuts airtime latency by **853.3 ms** per transmission, reducing RF spectrum exposure and channel congestion.
2. **Standard Mesh / UHF Radio (9600 bps)**: Full secure tactical frames transmit in only **89.2 ms**.
3. **Cryptographic Strength**: Preserved 100% (256-bit HMAC-SHA256 digest integrity).
