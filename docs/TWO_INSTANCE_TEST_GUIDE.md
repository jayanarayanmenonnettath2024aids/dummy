# iTANTRA — TWO-INSTANCE LOCAL NETWORK TESTING GUIDE

This document provides exact instructions to run and test two independent iTantra Walkie-Talkie nodes across a local Wi-Fi / Ethernet LAN.

---

## 1. Prerequisites

- Two desktop/laptop instances on the same local subnet (or two terminals on one PC with different ports).
- Python 3.10+ with `requirements.txt` installed.

---

## 2. Launching Node Alpha (Command Terminal 1)

```bash
cd iTantra
python -m app.communication.peer_transceiver --node-name "NODE-ALPHA" --port 65432
```
*Expected Output:*
```
[*] PeerTransceiver node [NODE-ALPHA] listening on port 65432
[mDNS] Registered service: NODE-ALPHA._itantra._tcp.local. on 192.168.1.10:65432
```

---

## 3. Launching Node Bravo (Command Terminal 2)

```bash
cd iTantra
python -m app.communication.peer_transceiver --node-name "NODE-BRAVO" --port 65433
```
*Expected Output:*
```
[*] PeerTransceiver node [NODE-BRAVO] listening on port 65433
[mDNS] Registered service: NODE-BRAVO._itantra._tcp.local. on 192.168.1.15:65433
[mDNS] Discovered peer node: NODE-ALPHA at 192.168.1.10:65432
```

---

## 4. Operational Testing

1. **Automatic Discovery**: Verify Node A logs `Discovered peer node: NODE-BRAVO` and vice versa without typing IP addresses.
2. **PTT Voice Transmission**: Trigger PTT on Node Alpha. Speak a message $\rightarrow$ Node Bravo verifies HMAC $\rightarrow$ Plays Piper neural TTS audio.
3. **Emergency Preemption**: Send an `ALERT` or `DISTRESS` packet $\rightarrow$ verify immediate priority preemption on the receiver.
