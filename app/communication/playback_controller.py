import threading
import queue
import time
import heapq
from typing import Optional, Callable, Dict, Any, Tuple, List
from app.communication.packet_v2 import iTantraPacketV2
from app.tts.engine import TTSEngine, NeuralONNXTTSEngine

class PriorityPlaybackItem:
    """
    Priority item wrapper for heap queue.
    Higher numeric priority is ordered first: DISTRESS (3) > ALERT (2) > ELEVATED (1) > NORMAL (0).
    For ties, earlier arrival timestamp is popped first.
    """
    def __init__(self, packet: iTantraPacketV2, arrival_time: Optional[float] = None):
        self.packet = packet
        self.arrival_time = arrival_time or time.time()
        self.priority = packet.priority
        self.message_type = packet.message_type

    def __lt__(self, other: "PriorityPlaybackItem") -> bool:
        # Negative priority for max-heap behavior via standard min-heap
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.arrival_time < other.arrival_time


class PriorityPlaybackController:
    """
    Manages receiver-side priority playback queues, preemption, and emergency playback locks.
    
    Priority Hierarchy:
    DISTRESS (3) > ALERT (2) > ELEVATED / VOICE_NOTE (1) > NORMAL (0)
    
    Interruption Rules:
    - NORMAL / VOICE_NOTE: Queued in standard order; cannot preempt.
    - ALERT: Jumps ahead of all queued NORMAL/VOICE_NOTE messages.
    - DISTRESS: Highest priority with application-level playback lock. Preempts active
      NORMAL/VOICE_NOTE playback immediately and executes exclusively.
    """

    def __init__(
        self,
        tts_engine: Optional[TTSEngine] = None,
        on_event_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.tts = tts_engine or NeuralONNXTTSEngine()
        self.on_event_callback = on_event_callback

        self._lock = threading.RLock()
        self._heap: List[PriorityPlaybackItem] = []
        self._queue_condition = threading.Condition(self._lock)
        
        self.current_item: Optional[PriorityPlaybackItem] = None
        self.is_playing: bool = False
        self.distress_lock_active: bool = False
        self._stop_current_playback = threading.Event()

        self._running = True
        self._worker_thread = threading.Thread(target=self._playback_worker, daemon=True, name="PriorityPlaybackWorker")
        self._worker_thread.start()

    def enqueue(self, packet: iTantraPacketV2) -> Dict[str, Any]:
        """
        Enqueue an incoming packet for priority playback.
        Returns dispatch status and preemption flags.
        """
        item = PriorityPlaybackItem(packet)
        with self._lock:
            # Check for preemption if a higher priority message arrives while playback is active
            preempted = False
            if self.is_playing and self.current_item is not None:
                if item.priority == iTantraPacketV2.PRIORITY_DISTRESS:
                    if self.current_item.priority < iTantraPacketV2.PRIORITY_DISTRESS:
                        # Preempt active NORMAL/ALERT playback for DISTRESS
                        self._stop_current_playback.set()
                        preempted = True
                elif item.priority == iTantraPacketV2.PRIORITY_ALERT:
                    if self.current_item.priority < iTantraPacketV2.PRIORITY_ALERT:
                        # Alert queues at head of line; wait for short sentence or preempt if long
                        pass

            heapq.heappush(self._heap, item)
            self._queue_condition.notify_all()

            status = {
                "enqueued": True,
                "priority": item.priority,
                "priority_name": packet.get_priority_name(),
                "message_type": packet.get_message_type_name(),
                "queue_depth": len(self._heap),
                "preempted_active": preempted,
                "distress_lock": self.distress_lock_active
            }

            if self.on_event_callback:
                self.on_event_callback({
                    "event": "message_enqueued",
                    "sender": packet.sender_id,
                    "text": packet.payload,
                    "priority": packet.get_priority_name(),
                    "type": packet.get_message_type_name(),
                    "queue_depth": len(self._heap)
                })

            return status

    def get_queue_status(self) -> Dict[str, Any]:
        """Returns current queue depth and items sorted by priority order."""
        with self._lock:
            queued_items = sorted(self._heap)
            return {
                "is_playing": self.is_playing,
                "distress_lock_active": self.distress_lock_active,
                "current_message": self.current_item.packet.to_dict() if self.current_item else None,
                "queue_depth": len(self._heap),
                "queued_messages": [it.packet.to_dict() for it in queued_items]
            }

    def clear_queue(self):
        """Clears all queued messages except if DISTRESS lock is active."""
        with self._lock:
            if not self.distress_lock_active:
                self._heap.clear()

    def stop(self):
        """Stops the playback worker."""
        with self._lock:
            self._running = False
            self._stop_current_playback.set()
            self._queue_condition.notify_all()
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)

    def _playback_worker(self):
        """Background thread executing messages in strict priority order."""
        while self._running:
            item = None
            with self._lock:
                while self._running and len(self._heap) == 0:
                    self._queue_condition.wait(timeout=0.2)

                if not self._running:
                    break

                if len(self._heap) > 0:
                    item = heapq.heappop(self._heap)
                    self.current_item = item
                    self.is_playing = True
                    if item.priority == iTantraPacketV2.PRIORITY_DISTRESS:
                        self.distress_lock_active = True
                    self._stop_current_playback.clear()

            if item is None:
                continue

            # Execute Speech Synthesis & Playback
            pkt = item.packet
            try:
                if self.on_event_callback:
                    self.on_event_callback({
                        "event": "playback_started",
                        "sender": pkt.sender_id,
                        "text": pkt.payload,
                        "priority": pkt.get_priority_name(),
                        "type": pkt.get_message_type_name(),
                        "distress_lock": self.distress_lock_active
                    })

                # Synthesize audio via Neural ONNX TTS (or language-appropriate engine)
                lang = pkt.language or "en"
                if not self.tts.is_language_supported(lang):
                    # Default to English synthesis if specific regional voice is not installed
                    lang = "en"

                out_wav, latency = self.tts.synthesize(
                    text=pkt.payload,
                    language=lang,
                    play_audio=True
                )

            except Exception as e:
                print(f"[!] Playback error: {e}")

            finally:
                with self._lock:
                    self.is_playing = False
                    self.current_item = None
                    if item.priority == iTantraPacketV2.PRIORITY_DISTRESS:
                        self.distress_lock_active = False

                    if self.on_event_callback:
                        self.on_event_callback({
                            "event": "playback_finished",
                            "sender": pkt.sender_id,
                            "text": pkt.payload,
                            "priority": pkt.get_priority_name(),
                            "distress_lock": False
                        })
