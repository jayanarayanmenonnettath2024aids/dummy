import os
import sys
import time
import secrets
import struct

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from app.communication.packet_v2 import iTantraPacketV2, MAX_PACKET_SIZE
from app.security.identity import NodeIdentity
from app.security.trust_store import TrustStore
from app.security.authenticator import (
    PacketAuthenticator,
    SecurityError,
    AuthenticationFailedError,
    ReplayAttackError,
    UntrustedPeerError
)

def run_attack_simulations():
    print("=" * 60)
    print("  iTANTRA BLOCK 7 — AUTOMATED ATTACK SIMULATION HARNESS  ")
    print("=" * 60)

    # Setup trusted identities
    node_a_key = secrets.token_bytes(32)
    node_b_key = secrets.token_bytes(32)

    trust_store_b = TrustStore(trust_file=":memory:")
    trust_store_b.pair_device("NODE-A", node_a_key, name="Tactical Unit Alpha")
    
    authenticator = PacketAuthenticator(trust_store=trust_store_b)

    results = []

    # -------------------------------------------------------------
    # ATTACK 1: Modify Packet in Transit (Payload Tampering)
    # -------------------------------------------------------------
    print("\n[*] ATTACK 1: Tampering transcript text in transit...")
    pkt1 = iTantraPacketV2(payload="Move to sector 4.", sender_id="NODE-A", sequence_number=1)
    authenticator.sign_packet(pkt1, node_a_key)
    
    # Tamper with payload without updating auth_tag
    pkt1.payload = "Move to sector 9 [AMBUSH]."
    try:
        authenticator.verify_and_authenticate(pkt1)
        print("[-] FAILED: Tampered packet was accepted!")
        results.append(("ATTACK 1: Payload Tampering", "FAILED"))
    except AuthenticationFailedError:
        print("[+] SUCCESS: Tampered packet rejected by HMAC-SHA256 verification.")
        results.append(("ATTACK 1: Payload Tampering", "PASSED (REJECTED)"))

    # -------------------------------------------------------------
    # ATTACK 2: Replay Valid Packet
    # -------------------------------------------------------------
    print("\n[*] ATTACK 2: Replaying captured valid packet...")
    pkt2 = iTantraPacketV2(payload="Status green.", sender_id="NODE-A", sequence_number=2)
    authenticator.sign_packet(pkt2, node_a_key)
    
    # First delivery: should succeed
    authenticator.verify_and_authenticate(pkt2)
    print("[+] Legitimate packet accepted (seq #2).")

    # Replay attack with same sequence number
    try:
        authenticator.verify_and_authenticate(pkt2)
        print("[-] FAILED: Replayed packet was accepted!")
        results.append(("ATTACK 2: Packet Replay", "FAILED"))
    except ReplayAttackError:
        print("[+] SUCCESS: Replayed packet rejected by sliding replay window.")
        results.append(("ATTACK 2: Packet Replay", "PASSED (REJECTED)"))

    # -------------------------------------------------------------
    # ATTACK 3: Priority Forgery (NORMAL -> DISTRESS)
    # -------------------------------------------------------------
    print("\n[*] ATTACK 3: Forging packet priority from NORMAL to DISTRESS...")
    pkt3 = iTantraPacketV2(
        payload="Routine patrol report.",
        sender_id="NODE-A",
        sequence_number=3,
        priority=iTantraPacketV2.PRIORITY_NORMAL,
        message_type=iTantraPacketV2.MESSAGE_TYPE_NORMAL
    )
    authenticator.sign_packet(pkt3, node_a_key)

    # Maliciously escalate priority in binary/object
    pkt3.priority = iTantraPacketV2.PRIORITY_DISTRESS
    pkt3.message_type = iTantraPacketV2.MESSAGE_TYPE_DISTRESS

    try:
        authenticator.verify_and_authenticate(pkt3)
        print("[-] FAILED: Forged DISTRESS packet was accepted!")
        results.append(("ATTACK 3: Priority Forgery", "FAILED"))
    except AuthenticationFailedError:
        print("[+] SUCCESS: Forged DISTRESS packet rejected before priority queue.")
        results.append(("ATTACK 3: Priority Forgery", "PASSED (REJECTED)"))

    # -------------------------------------------------------------
    # ATTACK 4: Malformed Binary Packet Fuzzing
    # -------------------------------------------------------------
    print("\n[*] ATTACK 4: Injecting malformed garbage bytes...")
    garbage_bytes = b"IT\x02\xFF\xFF\x00\x00" + secrets.token_bytes(40)
    try:
        iTantraPacketV2.from_binary(garbage_bytes)
        print("[-] FAILED: Malformed bytes parsed without error!")
        results.append(("ATTACK 4: Malformed Bytes", "FAILED"))
    except ValueError as ve:
        print(f"[+] SUCCESS: Parser safely rejected malformed frame: {ve}")
        results.append(("ATTACK 4: Malformed Bytes", "PASSED (REJECTED)"))

    # -------------------------------------------------------------
    # ATTACK 5: Oversized Packet Attack (>64 KiB)
    # -------------------------------------------------------------
    print("\n[*] ATTACK 5: Sending oversized 100 KiB packet buffer...")
    huge_bytes = b"IT\x02" + b"\x00" * 102400
    try:
        iTantraPacketV2.from_binary(huge_bytes)
        print("[-] FAILED: Oversized packet accepted!")
        results.append(("ATTACK 5: Oversized Packet", "FAILED"))
    except ValueError as ve:
        print(f"[+] SUCCESS: Oversized frame rejected before memory allocation: {ve}")
        results.append(("ATTACK 5: Oversized Packet", "PASSED (REJECTED)"))

    # -------------------------------------------------------------
    # ATTACK 6: Untrusted Rogue Device Injection
    # -------------------------------------------------------------
    print("\n[*] ATTACK 6: Transmitting from untrusted rogue node (NODE-ROGUE)...")
    rogue_key = secrets.token_bytes(32)
    pkt6 = iTantraPacketV2(payload="Evacuate base now!", sender_id="NODE-ROGUE", sequence_number=1)
    authenticator.sign_packet(pkt6, rogue_key)

    try:
        authenticator.verify_and_authenticate(pkt6)
        print("[-] FAILED: Untrusted node packet accepted!")
        results.append(("ATTACK 6: Untrusted Node", "FAILED"))
    except UntrustedPeerError:
        print("[+] SUCCESS: Untrusted peer rejected by TrustStore.")
        results.append(("ATTACK 6: Untrusted Node", "PASSED (REJECTED)"))

    # -------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------
    print("\n" + "=" * 60)
    print("  ATTACK SIMULATION SUMMARY  ")
    print("=" * 60)
    all_passed = True
    for name, status in results:
        print(f"  {name:<35} : {status}")
        if "FAILED" in status:
            all_passed = False
    print("=" * 60)
    print(f"OVERALL RESULT: {'6/6 PASSED (100%)' if all_passed else 'SOME ATTACKS SUCCEEDED'}")
    return all_passed

if __name__ == "__main__":
    run_attack_simulations()
