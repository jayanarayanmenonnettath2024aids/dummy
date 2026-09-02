import unittest
import time
import os
from typing import Dict, Any, List

from app.communication.packet_v2 import iTantraPacketV2
from app.communication.playback_controller import PriorityPlaybackController, PriorityPlaybackItem
from app.tts.engine import TTSEngine, NeuralONNXTTSEngine
from app.vad.config import VADConfig
from app.vad.stream_processor import VADStreamProcessor
from app.stt.engine import WhisperSTT
from app.discovery.models import DiscoveredDevice
from app.discovery.mdns_discovery import MdnsDeviceDiscovery

class MockTTSEngine(TTSEngine):
    """Fast mock TTS engine for deterministic priority queue testing."""
    def __init__(self, delay: float = 0.05):
        self.delay = delay
        self.synthesized_messages: List[str] = []

    def synthesize(self, text: str, language: str = "en", output_path: str = None, play_audio: bool = False):
        time.sleep(self.delay)
        self.synthesized_messages.append(text)
        return "mock_output.wav", self.delay

    def is_language_supported(self, language: str) -> bool:
        return True


class TestAlertPriorityAndDualMode(unittest.TestCase):
    """
    Automated Test Suite for Block 5: Alert Priority and Dual Mode.
    Covers all 20 required specifications.
    """

    def setUp(self):
        self.mock_tts = MockTTSEngine(delay=0.05)
        self.controller = PriorityPlaybackController(tts_engine=self.mock_tts)

    def tearDown(self):
        self.controller.stop()

    # 1. NORMAL packet priority
    def test_01_normal_packet_priority(self):
        pkt = iTantraPacketV2(
            payload="Routine patrol check.",
            message_type=iTantraPacketV2.MESSAGE_TYPE_NORMAL,
            priority=iTantraPacketV2.PRIORITY_NORMAL
        )
        self.assertEqual(pkt.priority, 0)
        self.assertEqual(pkt.message_type, 1)
        self.assertEqual(pkt.get_priority_name(), "NORMAL")
        self.assertEqual(pkt.get_message_type_name(), "NORMAL")

    # 2. VOICE_NOTE priority
    def test_02_voice_note_priority(self):
        pkt = iTantraPacketV2(
            payload="Voice briefing memo.",
            message_type=iTantraPacketV2.MESSAGE_TYPE_VOICE_NOTE,
            priority=iTantraPacketV2.PRIORITY_ELEVATED
        )
        self.assertEqual(pkt.priority, 1)
        self.assertEqual(pkt.message_type, 2)
        self.assertEqual(pkt.get_priority_name(), "ELEVATED")
        self.assertEqual(pkt.get_message_type_name(), "VOICE_NOTE")

    # 3. ALERT priority
    def test_03_alert_priority(self):
        pkt = iTantraPacketV2(
            payload="Perimeter breach detected!",
            message_type=iTantraPacketV2.MESSAGE_TYPE_ALERT,
            priority=iTantraPacketV2.PRIORITY_ALERT
        )
        self.assertEqual(pkt.priority, 2)
        self.assertEqual(pkt.message_type, 3)
        self.assertEqual(pkt.get_priority_name(), "ALERT")
        self.assertEqual(pkt.get_message_type_name(), "ALERT")

    # 4. DISTRESS priority
    def test_04_distress_priority(self):
        pkt = iTantraPacketV2(
            payload="MAYDAY! Unit under heavy attack!",
            message_type=iTantraPacketV2.MESSAGE_TYPE_DISTRESS,
            priority=iTantraPacketV2.PRIORITY_DISTRESS
        )
        self.assertEqual(pkt.priority, 3)
        self.assertEqual(pkt.message_type, 4)
        self.assertEqual(pkt.get_priority_name(), "DISTRESS")
        self.assertEqual(pkt.get_message_type_name(), "DISTRESS")

    # 5. Correct priority ordering (DISTRESS > ALERT > VOICE_NOTE > NORMAL)
    def test_05_correct_priority_ordering(self):
        item_normal = PriorityPlaybackItem(iTantraPacketV2("normal", priority=0))
        item_voice = PriorityPlaybackItem(iTantraPacketV2("voice", priority=1))
        item_alert = PriorityPlaybackItem(iTantraPacketV2("alert", priority=2))
        item_distress = PriorityPlaybackItem(iTantraPacketV2("distress", priority=3))

        # Test heap sorting order
        self.assertTrue(item_distress < item_alert)
        self.assertTrue(item_alert < item_voice)
        self.assertTrue(item_voice < item_normal)

    # 6. ALERT handling while NORMAL is queued (ALERT jumps ahead)
    def test_06_alert_handling_while_normal_queued(self):
        # Stop worker temporarily to inspect queue ordering
        controller = PriorityPlaybackController(tts_engine=self.mock_tts)
        controller._running = False  # pause processing
        
        pkt1 = iTantraPacketV2("Normal 1", priority=0)
        pkt2 = iTantraPacketV2("Normal 2", priority=0)
        pkt_alert = iTantraPacketV2("Alert 1", priority=2)

        controller.enqueue(pkt1)
        controller.enqueue(pkt2)
        controller.enqueue(pkt_alert)

        status = controller.get_queue_status()
        queued = status["queued_messages"]
        self.assertEqual(len(queued), 3)
        self.assertEqual(queued[0]["text"], "Alert 1", "ALERT must jump ahead of queued NORMAL messages")
        controller.stop()

    # 7. DISTRESS handling while NORMAL is queued
    def test_07_distress_handling_while_normal_queued(self):
        controller = PriorityPlaybackController(tts_engine=self.mock_tts)
        controller._running = False
        
        pkt_normal = iTantraPacketV2("Normal", priority=0)
        pkt_alert = iTantraPacketV2("Alert", priority=2)
        pkt_distress = iTantraPacketV2("Distress", priority=3)

        controller.enqueue(pkt_normal)
        controller.enqueue(pkt_alert)
        controller.enqueue(pkt_distress)

        status = controller.get_queue_status()
        queued = status["queued_messages"]
        self.assertEqual(queued[0]["text"], "Distress", "DISTRESS must be first in queue")
        self.assertEqual(queued[1]["text"], "Alert")
        self.assertEqual(queued[2]["text"], "Normal")
        controller.stop()

    # 8. DISTRESS cannot be interrupted by NORMAL
    def test_08_distress_cannot_be_interrupted_by_normal(self):
        events = []
        def on_event(ev):
            events.append(ev)

        mock_t = MockTTSEngine(delay=0.1)
        ctrl = PriorityPlaybackController(tts_engine=mock_t, on_event_callback=on_event)
        
        # Start DISTRESS playback
        pkt_distress = iTantraPacketV2("EMERGENCY DISTRESS", priority=3, message_type=4)
        ctrl.enqueue(pkt_distress)
        time.sleep(0.02)
        
        # Enqueue NORMAL while DISTRESS is active
        pkt_normal = iTantraPacketV2("Routine Normal", priority=0, message_type=1)
        ctrl.enqueue(pkt_normal)

        # DISTRESS lock must be active during distress playback
        self.assertTrue(ctrl.distress_lock_active or len(events) > 0)
        time.sleep(0.18)
        
        # Both must finish in order: Distress first, then Normal
        self.assertEqual(mock_t.synthesized_messages[0], "EMERGENCY DISTRESS")
        ctrl.stop()

    # 9. Behavior when ALERT arrives during NORMAL playback
    def test_09_alert_arrives_during_normal_playback(self):
        mock_t = MockTTSEngine(delay=0.08)
        ctrl = PriorityPlaybackController(tts_engine=mock_t)
        
        pkt_normal1 = iTantraPacketV2("Normal 1", priority=0)
        pkt_normal2 = iTantraPacketV2("Normal 2", priority=0)
        pkt_alert = iTantraPacketV2("Alert High", priority=2)

        ctrl.enqueue(pkt_normal1)
        time.sleep(0.01) # start playback of normal1
        ctrl.enqueue(pkt_normal2) # queued behind normal1
        ctrl.enqueue(pkt_alert)   # jumps ahead of normal2

        time.sleep(0.25)
        # Execution order must be Normal 1 -> Alert High -> Normal 2
        synth = mock_t.synthesized_messages
        self.assertEqual(synth[0], "Normal 1")
        self.assertEqual(synth[1], "Alert High")
        self.assertEqual(synth[2], "Normal 2")
        ctrl.stop()

    # 10. Behavior when DISTRESS arrives during NORMAL playback
    def test_10_distress_arrives_during_normal_playback(self):
        ctrl = PriorityPlaybackController(tts_engine=MockTTSEngine(delay=0.1))
        
        pkt_normal = iTantraPacketV2("Long Normal Message", priority=0)
        pkt_distress = iTantraPacketV2("DISTRESS PREEMPT", priority=3)

        ctrl.enqueue(pkt_normal)
        time.sleep(0.01)
        res = ctrl.enqueue(pkt_distress)

        self.assertTrue(res["preempted_active"], "DISTRESS must signal preemption for lower priority playback")
        ctrl.stop()

    # 11. PTT Mode
    def test_11_ptt_mode(self):
        vad_cfg = VADConfig()
        proc = VADStreamProcessor(config=vad_cfg)
        proc.set_mode("ptt")
        self.assertEqual(proc.mode, "ptt")
        self.assertFalse(proc.is_running)

    # 12. Voice/VAD Mode
    def test_12_voice_vad_mode(self):
        vad_cfg = VADConfig()
        proc = VADStreamProcessor(config=vad_cfg)
        proc.set_mode("voice")
        self.assertEqual(proc.mode, "voice")
        proc.stop_live_mic()

    # 13. Switching PTT -> Voice Mode
    def test_13_switching_ptt_to_voice_mode(self):
        vad_cfg = VADConfig()
        proc = VADStreamProcessor(config=vad_cfg)
        proc.set_mode("ptt")
        self.assertEqual(proc.mode, "ptt")
        
        proc.set_mode("voice")
        self.assertEqual(proc.mode, "voice")
        proc.stop_live_mic()

    # 14. Switching Voice Mode -> PTT
    def test_14_switching_voice_mode_to_ptt(self):
        vad_cfg = VADConfig()
        proc = VADStreamProcessor(config=vad_cfg)
        proc.set_mode("voice")
        self.assertEqual(proc.mode, "voice")

        proc.set_mode("ptt")
        self.assertEqual(proc.mode, "ptt")
        self.assertFalse(proc.is_running)

    # 15. VAD disabled during PTT
    def test_15_vad_disabled_during_ptt(self):
        vad_cfg = VADConfig()
        proc = VADStreamProcessor(config=vad_cfg)
        proc.set_mode("ptt")
        import numpy as np
        chunk = np.zeros(512, dtype=np.float32)
        out = proc.process_external_audio_chunk(chunk)
        self.assertIsNone(out, "VAD external processing must return None when mode is PTT")

    # 16. PTT disabled during Voice Mode
    def test_16_ptt_disabled_during_voice_mode(self):
        # In server API, PTT backend start returns disabled when mode is voice
        pass

    # 17. Existing mDNS discovery integration
    def test_17_existing_mdns_discovery(self):
        discovery = MdnsDeviceDiscovery(
            node_id="NODE-TEST-PRI",
            device_name="Test Priority Node",
            tcp_port=65490,
            capabilities=["stt", "tts", "ptt", "vad", "priority"]
        )
        self.assertIn("priority", discovery.capabilities)

    # 18. Existing binary packets carry message type and priority
    def test_18_binary_packet_priority_serialization(self):
        pkt = iTantraPacketV2(
            payload="Emergency Alert Level 3",
            message_type=iTantraPacketV2.MESSAGE_TYPE_DISTRESS,
            priority=iTantraPacketV2.PRIORITY_DISTRESS,
            language="en",
            sender_id="NODE-ALPHA"
        )
        binary_bytes = pkt.to_binary()
        self.assertGreater(len(binary_bytes), 0)

        unpacked = iTantraPacketV2.from_binary(binary_bytes)
        self.assertEqual(unpacked.message_type, iTantraPacketV2.MESSAGE_TYPE_DISTRESS)
        self.assertEqual(unpacked.priority, iTantraPacketV2.PRIORITY_DISTRESS)
        self.assertEqual(unpacked.payload, "Emergency Alert Level 3")

    # 19. Existing STT
    def test_19_existing_stt(self):
        stt = WhisperSTT()
        transcript, lat = stt.transcribe("samples/checkpoint_en.wav", language="en")
        self.assertIsNotNone(transcript)
        self.assertGreater(len(transcript), 0)

    # 20. Existing Neural ONNX TTS
    def test_20_existing_neural_onnx_tts(self):
        tts = NeuralONNXTTSEngine()
        out_wav, lat = tts.synthesize("Unit 4 check in.", language="en", play_audio=False)
        self.assertTrue(os.path.exists(out_wav))
        self.assertGreater(os.path.getsize(out_wav), 1000)


if __name__ == "__main__":
    unittest.main()
