# iTANTRA — BLOCK 7 SECURITY ARCHITECTURE

## 1. Cryptographic Specifications

- **Integrity & Authentication Primitive**: `HMAC-SHA256` (FIPS 198-1 / RFC 2104).
- **Key Length**: 256 bits (32 bytes cryptographically secure random bytes via `secrets.token_bytes(32)`).
- **Authentication Tag**: 64 hex characters (32 bytes binary digest), transported inside the length-delimited `iTantraPacketV2` header.
- **No Custom Cryptography**: Uses standard standard-library cryptographic primitives compatible across Python, Linux, and Android Java (`javax.crypto.Mac`).

---

## 2. Canonical Signature Format

The HMAC-SHA256 digest covers the exact binary representation of all packet fields:
```
HMAC_SHA256(
    Key,
    [Magic (2B)] + [Version (1B)] + [MsgType (1B)] + [Priority (1B)] +
    [Lang (2B)]  + [SeqNum (4B)]  + [Timestamp (8B)]+ [AudioBytes (4B)] +
    [SenderLen (1B)] + [SenderID] +
    [SessionLen (1B)]+ [SessionID]+
    [PayloadLen (2B)]+ [PayloadBytes]
)
```
Any modification to payload text, priority, message type, sender ID, timestamp, sequence number, or language invalidates the digest and causes immediate packet rejection.

---

## 3. Sliding Replay Window Algorithm

To defend against packet replay, duplication, and re-ordering across tactical Wi-Fi mesh networks:
1. **Timestamp Freshness**: $t_{\text{now}} - t_{\text{packet}} \le 30.0\text{ s}$ (rejects expired messages).
2. **Clock Skew Bound**: $t_{\text{packet}} - t_{\text{now}} \le 5.0\text{ s}$ (rejects timestamps set in future).
3. **64-bit Sliding Bitmask**:
   - If $\text{Seq} > \text{MaxSeq}$: Advance window by $\Delta = \text{Seq} - \text{MaxSeq}$. Set bit 0. Update $\text{MaxSeq} = \text{Seq}$.
   - If $\text{Seq} \le \text{MaxSeq}$:
     - If $\text{MaxSeq} - \text{Seq} \ge 64$: **REJECT** (packet outside replay window).
     - If bit $(\text{MaxSeq} - \text{Seq})$ is already set: **REJECT** (duplicate / replayed packet).
     - Otherwise: Mark bit $(\text{MaxSeq} - \text{Seq})$ as received and **ACCEPT**.

---

## 4. Zero Cloud / Local Trust Architecture

- Each node stores its identity in `app/security/node_identity.json`.
- Discovered devices are matched against `app/security/trust_store.json`.
- Discovered mDNS nodes without matching trusted keys are labeled `UNPAIRED` / `UNTRUSTED` and cannot transmit audio or trigger alert notifications on the receiving node.
