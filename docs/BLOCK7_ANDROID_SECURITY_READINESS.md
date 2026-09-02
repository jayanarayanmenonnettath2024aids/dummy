# iTANTRA — BLOCK 7 ANDROID SECURITY READINESS REPORT

## Android Readiness Status per Security Primitive

| Security Primitive | Desktop Implementation | Android Implementation Path | Key Storage Approach | Android Readiness |
|--------------------|------------------------|-----------------------------|----------------------|-------------------|
| **HMAC-SHA256** | Python standard library `hmac` + `hashlib` | Android Java `javax.crypto.Mac.getInstance("HmacSHA256")` / Google Tink | Hardware-backed Android Keystore (`AndroidKeyStore`) | **READY** |
| **Random Key Gen** | `secrets.token_bytes(32)` | `java.security.SecureRandom` | Android Keystore `KeyGenerator` | **READY** |
| **Trust Store** | JSON file `trust_store.json` | Android `EncryptedSharedPreferences` / SQLite Room DB | Android Jetpack Security (`MasterKey`) | **READY** |
| **Replay Window** | 64-bit bitmask + sliding sequence tracker | Standard Java `long` bitmask (`AtomicLong` or bitwise shift) | In-Memory Session State Map | **READY** |
| **Binary Protocol** | Big-endian `struct.pack/unpack` | `java.nio.ByteBuffer.order(ByteOrder.BIG_ENDIAN)` | Direct buffer memory parsing | **READY** |

---

## Overall Android Security Readiness: **READY**

- Zero external proprietary cryptographic C/C++ dependencies needed.
- Direct hardware security module (HSM) / Android Keystore compatibility.
- Zero cloud or central server requirement.
