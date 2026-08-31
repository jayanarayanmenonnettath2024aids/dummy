import os
import time
import json
import socket
import asyncio
from typing import List, Dict, Any, Optional
import io
import soundfile as sf
import numpy as np

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.stt.engine import WhisperSTTEngine, BaseSTTEngine
from app.tts.engine import LocalTTSEngine, BaseTTSEngine
from app.communication.interface import iTantraPacket
from app.communication.peer_transceiver import PeerTransceiver
from app.metrics.metrics import PipelineMetrics

class WebSocketManager:
    """Manages connected browser UI clients."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


def create_app(
    tcp_listen_port: int = 65432,
    peer_host: str = "127.0.0.1",
    peer_port: int = 65432,
    language: str = "en",
    node_name: Optional[str] = None
) -> FastAPI:
    app = FastAPI(title="iTantra Mission Control")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    ws_manager = WebSocketManager()
    _event_history: List[Dict[str, Any]] = []
    
    # State
    _stt_engine: Optional[WhisperSTTEngine] = None
    _tts_engine = LocalTTSEngine()
    _node_name = node_name or socket.gethostname()
    _current_lang = language
    _is_recording_backend = False
    _t1_record_start = 0.0

    loop = asyncio.get_event_loop()

    def get_stt() -> WhisperSTTEngine:
        nonlocal _stt_engine
        if _stt_engine is None:
            _stt_engine = WhisperSTTEngine()
        return _stt_engine

    def on_rx_callback(packet: iTantraPacket, metrics: PipelineMetrics):
        """Called when background transceiver receives a message from peer."""
        event_data = {
            "type": "MESSAGE_RECEIVED",
            "direction": "incoming",
            "sender": packet.sender_id,
            "text": packet.payload,
            "language": packet.language,
            "timestamp": time.strftime("%H:%M:%S", time.localtime(packet.t4_rx_finish or time.time())),
            "audio_bytes": packet.audio_size_bytes,
            "text_bytes": packet.get_text_payload_bytes(),
            "packet_bytes": packet.get_total_packet_bytes(),
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

    def on_tx_callback(packet: iTantraPacket, metrics: PipelineMetrics):
        """Called when this node successfully transmits a message."""
        event_data = {
            "type": "MESSAGE_SENT",
            "direction": "outgoing",
            "sender": _node_name,
            "text": packet.payload,
            "language": packet.language,
            "timestamp": time.strftime("%H:%M:%S", time.localtime(packet.t3_tx_start or time.time())),
            "audio_bytes": packet.audio_size_bytes,
            "text_bytes": packet.get_text_payload_bytes(),
            "packet_bytes": packet.get_total_packet_bytes(),
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

    # Initialize Transceiver
    transceiver = PeerTransceiver(
        listen_host="0.0.0.0",
        listen_port=tcp_listen_port,
        peer_host=peer_host,
        peer_port=peer_port,
        node_name=_node_name,
        tts_engine=_tts_engine,
        on_message_received=on_rx_callback,
        on_message_sent=on_tx_callback
    )
    transceiver.start()

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
        # Get local LAN IP
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
            "internet": "OFFLINE [OK]",
            "audio_transmitted": "NO [Text Only]"
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
        """Trigger start of backend hardware microphone recording."""
        nonlocal _is_recording_backend, _t1_record_start
        _is_recording_backend = True
        _t1_record_start = time.time()
        stt = get_stt()
        stt.start_dynamic_recording()
        await ws_manager.broadcast({"type": "RECORDING_STATE", "recording": True})
        return {"status": "recording_started"}

    @app.post("/api/ptt/backend_stop")
    async def ptt_backend_stop(lang: Optional[str] = None):
        """Trigger stop of backend microphone, transcribe, and transmit."""
        nonlocal _is_recording_backend
        if not _is_recording_backend:
            return {"status": "not_recording"}
        
        _is_recording_backend = False
        stt = get_stt()
        audio_array = stt.stop_dynamic_recording()
        await ws_manager.broadcast({"type": "RECORDING_STATE", "recording": False, "processing": True})

        if len(audio_array) == 0:
            return {"status": "empty_audio"}

        # STT Inference
        target_lang = lang or _current_lang
        audio_bytes_len = len(audio_array) * 2  # 16-bit PCM byte count
        t2_stt_start = time.time()
        transcript, stt_latency = stt.transcribe(audio_array, language=target_lang)
        t2_stt_finish = time.time()

        if not transcript.strip():
            transcript = "[Unclear Audio / Background Noise]"

        # Transmit to Peer
        success, packet, metrics = transceiver.transmit(
            transcript=transcript,
            language=target_lang,
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
    async def send_audio_blob(file: UploadFile = File(...), lang: Optional[str] = Form(None)):
        """Handles audio recorded from the web browser microphone."""
        import scipy.io.wavfile as wavfile
        target_lang = lang or _current_lang
        content = await file.read()
        audio_size_bytes = len(content)
        t1_start = time.time() - 2.0  # estimate
        
        # Read audio file into numpy array using soundfile or scipy
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
        """Trigger sending a pre-recorded demo sample."""
        sample_key = data.get("sample", "checkpoint")
        target_lang = data.get("language", _current_lang)
        
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
        """Replays speech locally for a given text."""
        text = data.get("text", "")
        lang = data.get("language", "en")
        _tts_engine.synthesize(text, language=lang, play_audio=True)
        return {"status": "replayed"}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await ws_manager.connect(websocket)
        try:
            while True:
                # Keep connection alive
                data = await websocket.receive_text()
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)

    @app.on_event("shutdown")
    def shutdown_event():
        transceiver.stop()

    return app
