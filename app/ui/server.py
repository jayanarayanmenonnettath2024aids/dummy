import os
import io
import time
import socket
import asyncio
import numpy as np
import soundfile as sf
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.communication.interface import iTantraPacket
from app.communication.packet_v2 import iTantraPacketV2
from app.communication.peer_transceiver import PeerTransceiver
from app.communication.playback_controller import PriorityPlaybackController
from app.discovery.mdns_discovery import MdnsDeviceDiscovery
from app.discovery.models import DiscoveredDevice
from app.vad.config import VADConfig
from app.vad.stream_processor import VADStreamProcessor
from app.stt.engine import WhisperSTT
from app.tts.engine import NeuralONNXTTSEngine, BaseTTSEngine, UnifiedTTSEngine
from app.metrics.metrics import PipelineMetrics


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


def create_app(
    tcp_listen_port: int = 65432,
    peer_host: str = "127.0.0.1",
    peer_port: int = 65432,
    node_name: Optional[str] = "NODE-ALPHA",
    language: str = "en",
    auto_start_vad: bool = False
) -> FastAPI:
    app = FastAPI(title="iTantra Mission Control", version="2.0.0")

    ws_manager = ConnectionManager()
    _event_history: List[Dict[str, Any]] = []
    _current_lang = language
    _node_name = node_name or socket.gethostname() or "NODE-ALPHA"

    # Operating Mode State: "walkie_talkie" (PTT) vs "voice_mode" (Hands-Free VAD)
    _operating_mode = "voice_mode" if auto_start_vad else "walkie_talkie"
    _mode_lock = asyncio.Lock()

    # Dynamic Recording State
    _is_recording_backend = False
    _t1_record_start = 0.0

    # STT & Neural ONNX TTS Singletons
    _stt_engine: Optional[WhisperSTT] = None
    _tts_engine: BaseTTSEngine = UnifiedTTSEngine()

    def get_stt() -> WhisperSTT:
        nonlocal _stt_engine
        if _stt_engine is None:
            _stt_engine = WhisperSTT()
        return _stt_engine

    # Event Loop handle for async broadcasts from thread callbacks
    loop = asyncio.get_event_loop()

    def _async_exception_handler(ev_loop, context):
        exception = context.get("exception")
        # Suppress benign zeroconf background cache expiration notices from external LAN devices
        msg = str(context.get("message", "")) + str(context.get("handle", ""))
        if isinstance(exception, KeyError) or "zeroconf" in msg.lower():
            return
        ev_loop.default_exception_handler(context)

    try:
        loop.set_exception_handler(_async_exception_handler)
    except Exception:
        pass

    # Background model pre-warming to eliminate first-speech cold-start latency
    import threading
    def _warmup_stt_async():
        try:
            stt = get_stt()
            dummy_pcm = np.zeros(8000, dtype=np.float32)
            stt.transcribe(dummy_pcm, sample_rate=16000, language="en")
        except Exception:
            pass
    threading.Thread(target=_warmup_stt_async, daemon=True, name="STTWarmup").start()

    # Initialize Priority Playback Controller
    def on_playback_event(event_dict: Dict[str, Any]):
        asyncio.run_coroutine_threadsafe(
            ws_manager.broadcast({
                "type": "PLAYBACK_EVENT",
                "data": event_dict
            }),
            loop
        )

    playback_controller = PriorityPlaybackController(
        tts_engine=_tts_engine,
        on_event_callback=on_playback_event
    )

    def on_rx_callback(packet: iTantraPacketV2, metrics: PipelineMetrics):
        """Called when a packet is received from the network."""
        is_distress = (packet.priority == iTantraPacketV2.PRIORITY_DISTRESS or packet.message_type == iTantraPacketV2.MESSAGE_TYPE_DISTRESS)
        is_alert = (packet.priority == iTantraPacketV2.PRIORITY_ALERT or packet.message_type == iTantraPacketV2.MESSAGE_TYPE_ALERT)

        event_data = {
            "id": f"{packet.sender_id}_{packet.session_id}_{packet.sequence_number}_rx_{packet.timestamp}",
            "type": "MESSAGE_RECEIVED",
            "direction": "incoming",
            "sender": packet.sender_id,
            "text": packet.payload,
            "language": packet.language,
            "priority": packet.get_priority_name(),
            "message_type": packet.get_message_type_name(),
            "is_distress": is_distress,
            "is_alert": is_alert,
            "timestamp": time.strftime("%H:%M:%S", time.localtime(packet.t4_rx_finish or time.time())),
            "audio_bytes": packet.audio_size_bytes,
            "text_bytes": packet.get_text_payload_bytes(),
            "packet_bytes": metrics.total_packet_bytes,
            "reduction_percent": f"{metrics.packet_reduction_percentage:.2f}%",
            "latencies": {
                "stt_ms": round(metrics.stt_latency_ms, 1),
                "net_ms": round(metrics.network_latency_ms, 1),
                "tts_ms": round(metrics.tts_latency_ms, 1),
                "e2e_ms": round(metrics.end_to_end_latency_ms, 1)
            }
        }
        _event_history.append(event_data)
        if len(_event_history) > 100:
            _event_history.pop(0)
        asyncio.run_coroutine_threadsafe(ws_manager.broadcast(event_data), loop)

    def on_tx_callback(packet: iTantraPacketV2, metrics: PipelineMetrics):
        """Called when this node successfully transmits a message."""
        is_distress = (packet.priority == iTantraPacketV2.PRIORITY_DISTRESS or packet.message_type == iTantraPacketV2.MESSAGE_TYPE_DISTRESS)
        is_alert = (packet.priority == iTantraPacketV2.PRIORITY_ALERT or packet.message_type == iTantraPacketV2.MESSAGE_TYPE_ALERT)

        event_data = {
            "id": f"{_node_name}_{packet.session_id}_{packet.sequence_number}_tx_{packet.timestamp}",
            "type": "MESSAGE_SENT",
            "direction": "outgoing",
            "sender": _node_name,
            "text": packet.payload,
            "language": packet.language,
            "priority": packet.get_priority_name(),
            "message_type": packet.get_message_type_name(),
            "is_distress": is_distress,
            "is_alert": is_alert,
            "timestamp": time.strftime("%H:%M:%S", time.localtime(packet.t3_tx_start or time.time())),
            "audio_bytes": packet.audio_size_bytes,
            "text_bytes": packet.get_text_payload_bytes(),
            "packet_bytes": metrics.total_packet_bytes,
            "reduction_percent": f"{metrics.packet_reduction_percentage:.2f}%",
            "latencies": {
                "stt_ms": round(metrics.stt_latency_ms, 1),
                "net_ms": round(metrics.network_latency_ms, 1),
                "tts_ms": 0.0,
                "e2e_ms": round(metrics.end_to_end_latency_ms, 1)
            }
        }
        _event_history.append(event_data)
        if len(_event_history) > 100:
            _event_history.pop(0)
        asyncio.run_coroutine_threadsafe(ws_manager.broadcast(event_data), loop)

    # Initialize Transceiver with Priority Playback Controller
    transceiver = PeerTransceiver(
        listen_host="0.0.0.0",
        listen_port=tcp_listen_port,
        peer_host=peer_host,
        peer_port=peer_port,
        node_name=_node_name,
        tts_engine=_tts_engine,
        playback_controller=playback_controller,
        on_message_received=on_rx_callback,
        on_message_sent=on_tx_callback
    )
    transceiver.start()

    # Initialize mDNS Automatic Local Device Discovery
    discovery = MdnsDeviceDiscovery(
        node_id=_node_name,
        device_name=_node_name,
        tcp_port=tcp_listen_port,
        device_type="desktop",
        languages=["en", "hi", "te", "ml", "ta", "kn", "mr", "bn", "gu"],
        capabilities=["stt", "tts", "ptt", "vad", "priority"],
        protocol_version="2.0",
        stale_timeout=120.0
    )

    def on_discovery_event(device: DiscoveredDevice):
        event_data = {
            "type": "DEVICE_DISCOVERY_UPDATE",
            "devices": [d.to_dict() for d in discovery.get_devices()]
        }
        asyncio.run_coroutine_threadsafe(ws_manager.broadcast(event_data), loop)

    discovery.on_device_added(on_discovery_event)
    discovery.on_device_removed(on_discovery_event)
    discovery.on_device_updated(on_discovery_event)
    discovery.start()

    # Initialize Streaming Voice Activity Detector (VAD)
    vad_config = VADConfig(
        speech_start_threshold=0.5,
        silence_duration_ms=700.0,
        minimum_speech_ms=250.0,
        maximum_utterance_ms=15000.0,
        pre_speech_buffer_ms=300.0,
        post_speech_buffer_ms=200.0
    )

    def on_vad_utterance_ready(utterance: np.ndarray, duration_ms: float):
        """Called when VAD detects completed speech in hands-free voice mode."""
        if _operating_mode != "voice_mode" or len(utterance) == 0:
            return

        target_lang = _current_lang
        audio_bytes_len = len(utterance) * 2
        t1_start = time.time() - (duration_ms / 1000.0)

        asyncio.run_coroutine_threadsafe(
            ws_manager.broadcast({"type": "RECORDING_STATE", "recording": False, "processing": True}),
            loop
        )

        stt = get_stt()
        transcript, stt_latency = stt.transcribe(utterance, language=target_lang)
        t2_finish = time.time()

        if transcript and transcript.strip():
            transceiver.transmit(
                transcript=transcript,
                language=target_lang,
                message_type=iTantraPacketV2.MESSAGE_TYPE_NORMAL,
                priority=iTantraPacketV2.PRIORITY_NORMAL,
                audio_size_bytes=audio_bytes_len,
                t1_start=t1_start,
                t2_stt=t2_finish
            )

        asyncio.run_coroutine_threadsafe(
            ws_manager.broadcast({"type": "RECORDING_STATE", "recording": False, "processing": False}),
            loop
        )

    def on_vad_state_change(state_name: str, payload: Dict[str, Any]):
        """Broadcast VAD speech start/end events to UI."""
        if _operating_mode != "voice_mode":
            return
        is_speech = (state_name == "SPEECH_STARTED")
        asyncio.run_coroutine_threadsafe(
            ws_manager.broadcast({
                "type": "VAD_STATE",
                "state": state_name,
                "data": payload
            }),
            loop
        )
        if is_speech:
            asyncio.run_coroutine_threadsafe(
                ws_manager.broadcast({"type": "RECORDING_STATE", "recording": True, "processing": False}),
                loop
            )

    vad_processor = VADStreamProcessor(
        config=vad_config,
        on_utterance_ready=on_vad_utterance_ready,
        on_vad_state_change=on_vad_state_change
    )

    # Mount static assets
    current_dir = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(current_dir, "static")
    templates_dir = os.path.join(current_dir, "templates")
    
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def serve_index():
        index_file = os.path.join(templates_dir, "index.html")
        if os.path.exists(index_file):
            with open(index_file, "r", encoding="utf-8") as f:
                return f.read()
        return "<h1>iTantra UI index.html not found</h1>"

    @app.get("/api/status")
    async def get_status():
        local_ip = "127.0.0.1"
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            pass

        return {
            "node_name": _node_name,
            "local_ip": local_ip,
            "tcp_listen_port": transceiver.listen_port,
            "peer_host": transceiver.peer_host,
            "peer_port": transceiver.peer_port,
            "language": _current_lang,
            "is_listening": transceiver.is_running,
            "operating_mode": _operating_mode,
            "vad_mode": vad_processor.mode,
            "queue_depth": len(playback_controller._heap),
            "distress_lock": playback_controller.distress_lock_active,
            "internet": "OFFLINE [OK]",
            "audio_transmitted": "NO [Text Only]"
        }

    @app.post("/api/mode/switch")
    async def switch_operating_mode(data: Dict[str, Any]):
        """
        Switch between Mode A (Walkie-Talkie PTT) and Mode B (Hands-Free Voice Mode).
        Guarantees strict mode safety: stops previous stream, avoids duplicate capture.
        """
        nonlocal _operating_mode, _is_recording_backend
        new_mode = data.get("mode", "walkie_talkie")
        if new_mode not in ["walkie_talkie", "voice_mode"]:
            raise HTTPException(status_code=400, detail="Invalid mode (expected 'walkie_talkie' or 'voice_mode')")

        async with _mode_lock:
            if new_mode == "walkie_talkie":
                # Cleanly stop VAD
                vad_processor.stop_live_mic()
                vad_processor.set_mode("ptt")
                _operating_mode = "walkie_talkie"
            else:
                # Cleanly stop any PTT backend recording
                if _is_recording_backend:
                    stt = get_stt()
                    stt.stop_dynamic_recording()
                    _is_recording_backend = False
                vad_processor.set_mode("voice")
                vad_processor.start_live_mic()
                _operating_mode = "voice_mode"

        await ws_manager.broadcast({
            "type": "MODE_SWITCH",
            "operating_mode": _operating_mode
        })
        return {"status": "success", "operating_mode": _operating_mode}

    @app.get("/api/priority/queue")
    async def get_priority_queue():
        """Inspect the receiver priority playback queue status."""
        return playback_controller.get_queue_status()

    @app.post("/api/send_priority_message")
    async def send_priority_message(data: Dict[str, Any]):
        """Directly send a message with specified priority and message type."""
        text = data.get("text", "")
        lang = data.get("language", _current_lang)
        msg_type_str = data.get("message_type", "NORMAL").upper()
        pri_str = data.get("priority", "NORMAL").upper()

        type_map = {
            "NORMAL": iTantraPacketV2.MESSAGE_TYPE_NORMAL,
            "VOICE_NOTE": iTantraPacketV2.MESSAGE_TYPE_VOICE_NOTE,
            "ALERT": iTantraPacketV2.MESSAGE_TYPE_ALERT,
            "DISTRESS": iTantraPacketV2.MESSAGE_TYPE_DISTRESS
        }
        pri_map = {
            "NORMAL": iTantraPacketV2.PRIORITY_NORMAL,
            "ELEVATED": iTantraPacketV2.PRIORITY_ELEVATED,
            "ALERT": iTantraPacketV2.PRIORITY_ALERT,
            "DISTRESS": iTantraPacketV2.PRIORITY_DISTRESS
        }

        m_type = type_map.get(msg_type_str, iTantraPacketV2.MESSAGE_TYPE_NORMAL)
        pri = pri_map.get(pri_str, iTantraPacketV2.PRIORITY_NORMAL)

        success, packet, metrics = transceiver.transmit(
            transcript=text,
            language=lang,
            message_type=m_type,
            priority=pri,
            t1_start=time.time(),
            t2_stt=time.time()
        )

        return {
            "status": "success" if success else "failed",
            "text": text,
            "message_type": msg_type_str,
            "priority": pri_str
        }

    @app.get("/api/vad/config")
    async def get_vad_config():
        return {
            "mode": vad_processor.mode,
            "config": vad_processor.config.to_dict()
        }

    @app.post("/api/vad/mode")
    async def set_vad_mode(data: Dict[str, Any]):
        new_mode = data.get("mode", "ptt")
        current_mode = vad_processor.set_mode(new_mode)
        await ws_manager.broadcast({
            "type": "VAD_MODE_UPDATE",
            "mode": current_mode
        })
        return {"status": "success", "mode": current_mode}

    @app.post("/api/vad/config")
    async def update_vad_config(data: Dict[str, Any]):
        cfg = VADConfig.from_dict(data)
        vad_processor.update_config(cfg)
        return {"status": "success", "config": vad_processor.config.to_dict()}

    @app.post("/api/vad/process_audio_chunk")
    async def process_vad_audio_chunk(file: UploadFile = File(...)):
        if _operating_mode != "voice_mode":
            return {"status": "vad_disabled_in_ptt_mode"}
        content = await file.read()
        if not content:
            return {"status": "empty"}

        try:
            audio_data, sr = sf.read(io.BytesIO(content))
            if audio_data is not None and len(audio_data) > 0:
                stt = get_stt()
                processed = stt.preprocess_audio(audio_data, sr, target_sr=16000)
                completed_utterance = vad_processor.process_external_audio_chunk(processed)
                if completed_utterance is not None and len(completed_utterance) > 0:
                    on_vad_utterance_ready(completed_utterance, len(completed_utterance) / 16.0)
                    return {"status": "utterance_detected", "samples": len(completed_utterance)}
        except Exception as e:
            print(f"[!] VAD chunk decode error: {e}")

        return {"status": "chunk_processed"}

    @app.get("/api/devices")
    async def get_devices():
        return [d.to_dict() for d in discovery.get_devices()]

    @app.get("/api/models/languages")
    async def get_model_languages():
        from app.models.manager import ModelManager
        mm = ModelManager()
        return {
            "shared_stt_model": {
                "name": "openai/whisper-tiny",
                "type": "Multilingual Seq2Seq Transformer (37.76M params)",
                "disk_size_mib": 148.23,
                "runtime_ram_mib": 416.25,
                "is_shared": True
            },
            "total_disk_footprint_mib": mm.get_total_disk_footprint_mib(),
            "unique_models": mm.get_unique_models(),
            "all_languages": [p.to_dict() for p in mm.get_available_models()],
            "installed_languages": [p.to_dict() for p in mm.get_installed_models()]
        }

    @app.post("/api/connect_device")
    async def connect_device(data: Dict[str, Any]):
        node_id = data.get("node_id")
        target_host = data.get("ip") or data.get("peer_host")
        target_port = data.get("port") or data.get("peer_port")

        if node_id:
            dev = discovery.get_device(node_id)
            if dev:
                target_host = dev.ip
                target_port = dev.port

        if not target_host or not target_port:
            raise HTTPException(status_code=400, detail="Missing target IP or port")

        target_port = int(target_port)
        transceiver.set_peer(target_host, target_port)
        await ws_manager.broadcast({
            "type": "STATUS_UPDATE",
            "peer_host": target_host,
            "peer_port": target_port,
            "node_id": node_id
        })
        return {
            "status": "connected",
            "node_id": node_id,
            "peer_host": target_host,
            "peer_port": target_port
        }

    @app.post("/api/connect")
    async def update_peer(data: Dict[str, Any]):
        new_host = data.get("peer_host", transceiver.peer_host)
        new_port = int(data.get("peer_port", transceiver.peer_port))
        transceiver.set_peer(new_host, new_port)
        await ws_manager.broadcast({
            "type": "STATUS_UPDATE",
            "peer_host": new_host,
            "peer_port": new_port
        })
        return {"status": "success", "peer_host": new_host, "peer_port": new_port}

    @app.post("/api/ptt/backend_start")
    async def ptt_backend_start():
        if _operating_mode != "walkie_talkie":
            return {"status": "ptt_disabled_in_voice_mode"}
        nonlocal _is_recording_backend, _t1_record_start
        _is_recording_backend = True
        _t1_record_start = time.time()
        stt = get_stt()
        stt.start_dynamic_recording()
        await ws_manager.broadcast({"type": "RECORDING_STATE", "recording": True})
        return {"status": "recording_started"}

    @app.post("/api/ptt/backend_stop")
    async def ptt_backend_stop(
        lang: Optional[str] = None,
        priority: int = iTantraPacketV2.PRIORITY_NORMAL,
        message_type: int = iTantraPacketV2.MESSAGE_TYPE_NORMAL
    ):
        if _operating_mode != "walkie_talkie":
            return {"status": "ptt_disabled_in_voice_mode"}
        nonlocal _is_recording_backend
        if not _is_recording_backend:
            return {"status": "not_recording"}
        
        _is_recording_backend = False
        stt = get_stt()
        audio_array = stt.stop_dynamic_recording()
        await ws_manager.broadcast({"type": "RECORDING_STATE", "recording": False, "processing": True})

        if len(audio_array) == 0:
            return {"status": "empty_audio"}

        target_lang = lang or _current_lang
        audio_bytes_len = len(audio_array) * 2
        transcript, stt_latency = stt.transcribe(audio_array, language=target_lang)
        t2_stt_finish = time.time()

        if not transcript.strip():
            transcript = "[Unclear Audio / Background Noise]"

        success, packet, metrics = transceiver.transmit(
            transcript=transcript,
            language=target_lang,
            message_type=message_type,
            priority=priority,
            audio_size_bytes=audio_bytes_len,
            t1_start=_t1_record_start,
            t2_stt=t2_stt_finish
        )

        return {
            "status": "success" if success else "failed",
            "transcript": transcript,
            "stt_latency_ms": round(stt_latency * 1000, 1),
            "audio_bytes": audio_bytes_len
        }

    @app.get("/api/events")
    async def get_events():
        return _event_history

    @app.post("/api/send_audio_blob")
    async def send_audio_blob(
        file: UploadFile = File(...),
        lang: Optional[str] = Form(None),
        priority: int = Form(0),
        message_type: int = Form(1)
    ):
        import scipy.io.wavfile as wavfile
        target_lang = lang or _current_lang
        content = await file.read()
        audio_size_bytes = len(content)
        t1_start = time.time() - 2.0
        
        audio_data = None
        sr = 16000
        try:
            audio_data, sr = sf.read(io.BytesIO(content))
        except Exception:
            try:
                sr, audio_data = wavfile.read(io.BytesIO(content))
            except Exception as e:
                print(f"[!] Audio decode error: {e}")
                raise HTTPException(status_code=400, detail="Invalid audio format")

        if audio_data is None or len(audio_data) == 0:
            return {"status": "empty_audio"}

        stt = get_stt()
        transcript, stt_latency = stt.transcribe(audio_data, sample_rate=sr, language=target_lang)
        t2_stt_finish = time.time()

        if not transcript.strip():
            return {"status": "no_speech", "transcript": "", "audio_bytes": audio_size_bytes}

        success, packet, metrics = transceiver.transmit(
            transcript=transcript,
            language=target_lang,
            message_type=message_type,
            priority=priority,
            audio_size_bytes=audio_size_bytes,
            t1_start=t1_start,
            t2_stt=t2_stt_finish
        )

        return {
            "status": "success" if success else "failed",
            "transcript": transcript,
            "stt_latency_ms": round(stt_latency * 1000, 1),
            "audio_bytes": audio_size_bytes
        }

    @app.post("/api/send_sample")
    async def send_sample(data: Dict[str, Any]):
        sample_key = data.get("sample", "checkpoint")
        target_lang = data.get("language", _current_lang)
        msg_type = data.get("message_type", iTantraPacketV2.MESSAGE_TYPE_NORMAL)
        priority = data.get("priority", iTantraPacketV2.PRIORITY_NORMAL)
        
        sample_map = {
            "checkpoint": "samples/checkpoint_en.wav",
            "emergency": "samples/emergency_en.wav",
            "rescue": "samples/rescue_en.wav"
        }
        sample_path = sample_map.get(sample_key, "samples/checkpoint_en.wav")
        if not os.path.exists(sample_path):
            raise HTTPException(status_code=404, detail="Sample file not found")

        audio_bytes = os.path.getsize(sample_path)
        t1_start = time.time()
        stt = get_stt()
        transcript, stt_latency = stt.transcribe(sample_path, language=target_lang)
        t2_stt_finish = time.time()

        success, packet, metrics = transceiver.transmit(
            transcript=transcript,
            language=target_lang,
            message_type=msg_type,
            priority=priority,
            audio_size_bytes=audio_bytes,
            t1_start=t1_start,
            t2_stt=t2_stt_finish
        )

        return {
            "status": "success" if success else "failed",
            "sample": sample_key,
            "transcript": transcript,
            "audio_bytes": audio_bytes
        }

    @app.post("/api/replay_tts")
    async def replay_tts(data: Dict[str, Any]):
        text = data.get("text", "")
        lang = data.get("language", "en")
        _tts_engine.synthesize(text, language=lang, play_audio=True)
        return {"status": "replayed"}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await ws_manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_text()
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)

    @app.on_event("shutdown")
    def shutdown_event():
        vad_processor.stop_live_mic()
        discovery.stop()
        playback_controller.stop()
        transceiver.stop()

    return app
