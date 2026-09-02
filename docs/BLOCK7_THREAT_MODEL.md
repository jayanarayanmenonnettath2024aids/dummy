# iTANTRA — BLOCK 7 THREAT MODEL & SECURITY ANALYSIS

## 1. Tactical Network Communication Model
```
Node A (Tactical Unit)
   ↓  [Local mDNS Discovery + TCP Binary Transport]
Local Ad-Hoc / Wi-Fi Mesh Network (Untrusted Environment)
   ↓  [HMAC-SHA256 Integrity + Sliding Replay Window Verification]
Node B (Command / Peer Unit)
```

---

## 2. Core Security Distinction

| Security Domain | Scope & Definition | Implementation in iTantra |
|-----------------|---------------------|---------------------------|
| **DISCOVERY** | Detects physical presence on local subnet: *"This node is online and broadcasting."* | Zeroconf mDNS (`_itantra._tcp.local.`) |
| **AUTHENTICATION** | Establishes cryptographic peer identity: *"This node is an authorized unit."* | Local `TrustStore` + 256-bit Node Key Pairing |
| **PACKET INTEGRITY** | Detects any bitwise tampering in transit: *"No fields or payloads were modified."* | Standard `HMAC-SHA256` canonical signature tag |
| **REPLAY PROTECTION** | Prevents repeated playback of intercepted frames: *"This packet is fresh."* | 64-bit Sliding Replay Window + 30s Freshness check |
| **RESILIENCE & AVAILABILITY**| Prevents crashes/hangs from bad packets or network dropouts. | Hardened bounds parser + Clean TCP connection recovery |

---

## 3. Analysis of 20 Tactical Threat Scenarios

| # | Threat Scenario | Attack Vector | Security Domain | Defense Mechanism & Mitigation | Result |
|---|-----------------|---------------|-----------------|--------------------------------|--------|
| 1 | Unauthorized device joining network | Attacker connects rogue laptop to Wi-Fi | Authentication | Rejected: Peer ID not found in local `TrustStore`. | **BLOCKED** |
| 2 | Rogue device impersonation | Attacker spoofs sender ID `NODE-A` | Authentication | Rejected: Attacker lacks Node A's secret key; HMAC fails. | **BLOCKED** |
| 3 | Packet modification | Attacker alters tactical transcript text | Packet Integrity | Rejected: Any bit alteration causes HMAC-SHA256 mismatch. | **BLOCKED** |
| 4 | Packet injection | Attacker injects forged binary frames | Packet Integrity | Rejected: Missing or invalid HMAC authentication tag. | **BLOCKED** |
| 5 | Packet replay | Attacker sniffs and resends valid message | Replay Protection | Rejected: Sequence number duplicate caught by sliding window. | **BLOCKED** |
| 6 | Duplicate packet transmission | Network loop delivers duplicate packet | Replay Protection | Rejected: Bitmask marks sequence number as already processed. | **BLOCKED** |
| 7 | Malformed packet attack | Attacker sends invalid/fuzzed binary data | Availability | Rejected: Safe validation of magic, version, and length headers. | **BLOCKED** |
| 8 | Oversized packet attack | Attacker sends >64 KiB buffer overflow attempt | Availability | Rejected: Strict bounds check (`MAX_PACKET_SIZE = 64 KiB`). | **BLOCKED** |
| 9 | Invalid message type | Attacker sends undefined `msg_type = 99` | Availability | Rejected: Validated against `MESSAGE_TYPE_NAMES` whitelist. | **BLOCKED** |
| 10| Invalid priority level | Attacker sends undefined `priority = 255` | Availability | Rejected: Validated against `PRIORITY_NAMES` whitelist. | **BLOCKED** |
| 11| Invalid language code | Attacker sends malformed language header | Availability | Sanitized: Clamped to 2-character ASCII ISO code. | **BLOCKED** |
| 12| Sequence number manipulation | Attacker decrements/increments sequence number | Packet Integrity | Rejected: Sequence number is bound inside signed HMAC digest. | **BLOCKED** |
| 13| Session ID manipulation | Attacker alters UUID session prefix | Packet Integrity | Rejected: Session ID is bound inside signed HMAC digest. | **BLOCKED** |
| 14| Connection flooding | Rapid SYN/connect attempts on TCP port | Availability | Short socket timeout (1.0s) + thread isolation. | **MITIGATED** |
| 15| Discovery spoofing | Attacker announces fake mDNS node | Discovery/Trust | Discovered as `UNPAIRED` / `UNTRUSTED`; blocked from comms. | **MITIGATED** |
| 16| Device disappearance | Peer walks out of Wi-Fi range or battery dies | Resilience | Clean socket close, peer marked `OFFLINE`, no thread crash. | **HANDLED** |
| 17| Connection interruption | TCP socket reset during transfer | Resilience | `ConnectionResetError` caught; transport closes cleanly. | **HANDLED** |
| 18| Partial packet transmission | Broken socket delivers partial frame | Resilience | Exact length check (`_recv_exact`) aborts gracefully. | **HANDLED** |
| 19| TCP timeout | Silent drop or unreachable target IP | Resilience | Timeout aborts send/receive without hanging main loop. | **HANDLED** |
| 20| Resource exhaustion | Continuous junk audio allocation attempt | Availability | Safe bounds reject frames before allocating STT/TTS buffers. | **BLOCKED** |
