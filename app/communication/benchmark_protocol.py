import sys
import time
from typing import Dict, Any, List
from app.communication.packet_v2 import iTantraPacketV2

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def benchmark_message(
    text: str,
    language: str = "en",
    sender_id: str = "ALPHA-NODE",
    session_id: str = "s1234567",
    sequence_number: int = 1,
    audio_size_bytes: int = 64000
) -> Dict[str, Any]:
    """
    Computes precise byte footprint for raw UTF-8 text, JSON packet, and Binary packet.
    """
    packet = iTantraPacketV2(
        payload=text,
        language=language,
        sender_id=sender_id,
        session_id=session_id,
        sequence_number=sequence_number,
        audio_size_bytes=audio_size_bytes,
        timestamp=time.time()
    )

    text_bytes = packet.get_text_payload_bytes()
    json_bytes = packet.get_total_packet_bytes(format_type="json")
    binary_bytes = packet.get_total_packet_bytes(format_type="binary")

    json_overhead = json_bytes - text_bytes
    binary_overhead = binary_bytes - text_bytes
    overhead_reduction_pct = ((json_bytes - binary_bytes) / json_bytes) * 100.0

    return {
        "text": text,
        "language": language,
        "text_bytes": text_bytes,
        "json_bytes": json_bytes,
        "binary_bytes": binary_bytes,
        "json_overhead_bytes": json_overhead,
        "binary_overhead_bytes": binary_overhead,
        "reduction_pct": round(overhead_reduction_pct, 2)
    }

def run_benchmarks():
    test_cases = [
        ("Meet me at checkpoint 4.", "en", "Standard Tactical Command"),
        ("Emergency team report to sector 4.", "en", "Urgent Alert"),
        ("அவசரக் குழு பிரிவு நான்கிற்கு வரவும்.", "ta", "Tamil Unicode Emergency"),
        ("அடுத்த சோதனைச் சாவடிக்குச் செல்லவும்.", "ta", "Tamil Unicode Command"),
        ("OK.", "en", "Minimal Ack/Response"),
        ("Hostile drone detected at 200m north-east quadrant moving rapidly towards communications relay Alpha.", "en", "Extended Tactical Sitrep")
    ]

    print("=" * 80)
    print("iTANTRA PROTOCOL BENCHMARK: JSON vs COMPACT BINARY (iTantraPacketV2)")
    print("=" * 80)

    for text, lang, label in test_cases:
        res = benchmark_message(text, language=lang)
        print(f"\n[Case] {label} ({lang.upper()}): '{text}'")
        print("-" * 60)
        print(f"TEXT:   {res['text_bytes']} bytes")
        print(f"JSON:   {res['json_bytes']} bytes (Overhead: +{res['json_overhead_bytes']} bytes)")
        print(f"BINARY: {res['binary_bytes']} bytes (Overhead: +{res['binary_overhead_bytes']} bytes)")
        print(f"-> Wire Savings vs JSON: -{res['json_bytes'] - res['binary_bytes']} bytes ({res['reduction_pct']}% reduction)")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    run_benchmarks()
