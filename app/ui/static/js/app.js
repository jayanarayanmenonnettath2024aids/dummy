/**
 * iTantra Mission Control JavaScript Client
 * Handles WebSockets, Push-To-Talk, Waveform visualizer, and Telemetry updates
 */

let ws = null;
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];
let audioContext = null;
let analyser = null;
let animFrameId = null;
let isSpacePressed = false;

// Cumulative Telemetry Stats
let totalAudioBytes = 0;
let totalTextBytes = 0;
let totalMessages = 0;

document.addEventListener("DOMContentLoaded", () => {
    initWebSocket();
    initStatus();
    initVisualizer();
    initPTTControls();
    initKeyboardShortcuts();
    initSampleButtons();
    initConnectForm();
});

// 1. WebSocket Management
function initWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log("[WS] Connected to iTantra Node Server");
        updateConnectionBadge(true);
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleServerEvent(data);
        } catch (e) {
            console.error("[WS] Error parsing message:", e);
        }
    };

    ws.onclose = () => {
        console.warn("[WS] Disconnected. Retrying in 2s...");
        updateConnectionBadge(false);
        setTimeout(initWebSocket, 2000);
    };
}

function updateConnectionBadge(connected) {
    const badge = document.getElementById("nodeStatusBadge");
    if (badge) {
        if (connected) {
            badge.innerHTML = `<span class="pulse-dot"></span> NODE ACTIVE`;
            badge.className = "badge badge-node";
        } else {
            badge.innerHTML = `DISCONNECTED`;
            badge.className = "badge";
            badge.style.color = "#ff3366";
        }
    }
}

// 2. Fetch Initial Node Info
async function initStatus() {
    try {
        const res = await fetch("/api/status");
        const data = await res.json();
        
        document.getElementById("localNodeName").innerText = data.node_name;
        document.getElementById("localNodeIp").innerText = `${data.local_ip}:${data.tcp_listen_port}`;
        document.getElementById("peerHostInput").value = data.peer_host;
        document.getElementById("peerPortInput").value = data.peer_port;
        document.getElementById("peerBadge").innerText = `${data.peer_host}:${data.peer_port}`;
    } catch (e) {
        console.error("Failed to fetch initial status:", e);
    }
}

// 3. Handle Server Events
function handleServerEvent(event) {
    if (event.type === "MESSAGE_RECEIVED" || event.type === "MESSAGE_SENT") {
        appendMessageCard(event);
        updateTelemetryStats(event);
    } else if (event.type === "RECORDING_STATE") {
        updateRecordingUI(event.recording, event.processing);
    } else if (event.type === "STATUS_UPDATE") {
        document.getElementById("peerBadge").innerText = `${event.peer_host}:${event.peer_port}`;
    }
}

// 4. Push-To-Talk Logic
function initPTTControls() {
    const pttBtn = document.getElementById("pttButton");
    
    // Mouse / Touch events for Click & Hold
    pttBtn.addEventListener("mousedown", startPTT);
    pttBtn.addEventListener("mouseup", stopPTT);
    pttBtn.addEventListener("mouseleave", () => {
        if (isRecording) stopPTT();
    });

    pttBtn.addEventListener("touchstart", (e) => {
        e.preventDefault();
        startPTT();
    });
    pttBtn.addEventListener("touchend", (e) => {
        e.preventDefault();
        stopPTT();
    });
}

function initKeyboardShortcuts() {
    // Spacebar Push-To-Talk
    window.addEventListener("keydown", (e) => {
        if (e.code === "Space" && !isSpacePressed && e.target.tagName !== "INPUT") {
            e.preventDefault();
            isSpacePressed = true;
            startPTT();
        }
    });

    window.addEventListener("keyup", (e) => {
        if (e.code === "Space" && isSpacePressed && e.target.tagName !== "INPUT") {
            e.preventDefault();
            isSpacePressed = false;
            stopPTT();
        }
    });
}

async function startPTT() {
    if (isRecording) return;
    isRecording = true;
    updateRecordingUI(true, false);

    // Try Web Audio API microphone capture in browser
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const source = audioContext.createMediaStreamSource(stream);
            analyser = audioContext.createAnalyser();
            analyser.fftSize = 256;
            source.connect(analyser);
            drawWaveform();

            audioChunks = [];
            mediaRecorder = new MediaRecorder(stream);
            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) audioChunks.push(e.data);
            };
            mediaRecorder.start();
            return;
        } catch (err) {
            console.warn("Browser mic access failed, falling back to backend hardware mic:", err);
        }
    }

    // Fallback: Backend hardware microphone
    await fetch("/api/ptt/backend_start", { method: "POST" });
}

async function stopPTT() {
    if (!isRecording) return;
    isRecording = false;
    updateRecordingUI(false, true);

    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: "audio/wav" });
            const formData = new FormData();
            formData.append("file", audioBlob, "ptt_speech.wav");
            
            const lang = document.getElementById("languageSelect").value;
            formData.append("lang", lang);

            try {
                const res = await fetch("/api/send_audio_blob", {
                    method: "POST",
                    body: formData
                });
                const result = await res.json();
                console.log("[PTT Upload Success]", result);
            } catch (e) {
                console.error("Failed to upload PTT audio:", e);
            } finally {
                updateRecordingUI(false, false);
            }
        };
        mediaRecorder.stop();
        if (animFrameId) cancelAnimationFrame(animFrameId);
    } else {
        // Stop backend hardware mic
        const lang = document.getElementById("languageSelect").value;
        const res = await fetch(`/api/ptt/backend_stop?lang=${lang}`, { method: "POST" });
        const result = await res.json();
        console.log("[Backend PTT Success]", result);
        updateRecordingUI(false, false);
    }
}

function updateRecordingUI(recording, processing) {
    const pttBtn = document.getElementById("pttButton");
    const pttHint = document.getElementById("pttHint");
    const pttIcon = document.getElementById("pttIcon");

    if (recording) {
        pttBtn.classList.add("recording");
        pttIcon.innerText = "🔴";
        pttHint.innerText = "TRANSMITTING (SPEAK NOW)...";
    } else if (processing) {
        pttBtn.classList.remove("recording");
        pttIcon.innerText = "⚡";
        pttHint.innerText = "LOCAL STT INFERENCE & TRANSMITTING...";
    } else {
        pttBtn.classList.remove("recording");
        pttIcon.innerText = "🎙️";
        pttHint.innerText = "HOLD SPACEBAR OR CLICK TO TRANSMIT";
    }
}

// 5. Canvas Waveform Visualizer
function initVisualizer() {
    const canvas = document.getElementById("waveformCanvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    
    // Draw initial idle line
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "#00f0ff";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, canvas.height / 2);
    ctx.lineTo(canvas.width, canvas.height / 2);
    ctx.stroke();
}

function drawWaveform() {
    const canvas = document.getElementById("waveformCanvas");
    if (!canvas || !analyser) return;
    const ctx = canvas.getContext("2d");
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    function render() {
        if (!isRecording) {
            initVisualizer();
            return;
        }
        animFrameId = requestAnimationFrame(render);
        analyser.getByteTimeDomainData(dataArray);

        ctx.fillStyle = "rgba(0, 0, 0, 0.3)";
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        ctx.lineWidth = 2;
        ctx.strokeStyle = "#ff3366";
        ctx.beginPath();

        const sliceWidth = canvas.width / bufferLength;
        let x = 0;

        for (let i = 0; i < bufferLength; i++) {
            const v = dataArray[i] / 128.0;
            const y = (v * canvas.height) / 2;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
            x += sliceWidth;
        }
        ctx.lineTo(canvas.width, canvas.height / 2);
        ctx.stroke();
    }
    render();
}

// 6. Append Message Cards
function appendMessageCard(msg) {
    const feed = document.getElementById("conversationFeed");
    const emptyNotice = document.getElementById("emptyFeedNotice");
    if (emptyNotice) emptyNotice.remove();

    const isOutgoing = msg.direction === "outgoing";
    const card = document.createElement("div");
    card.className = `msg-card ${isOutgoing ? "outgoing" : "incoming"}`;

    card.innerHTML = `
        <div class="msg-meta">
            <div class="msg-sender">
                ${isOutgoing ? "↗ OUTGOING [TRANSMIT]" : "↙ INCOMING [RECEIVED]"} · ${msg.sender}
            </div>
            <div>${msg.timestamp} (${msg.language ? msg.language.toUpperCase() : "EN"})</div>
        </div>
        <div class="msg-text">"${escapeHtml(msg.text)}"</div>
        <div class="msg-telemetry">
            <div class="telemetry-item">Payload: <span>${msg.text_bytes} B</span> (vs ${msg.audio_bytes ? msg.audio_bytes.toLocaleString() : "0"} B audio)</div>
            <div class="telemetry-item">Reduction: <span>${msg.reduction_percent || ">99.7%"}</span></div>
            <div class="telemetry-item">STT: <span>${msg.latencies.stt_ms}ms</span></div>
            <div class="telemetry-item">Net: <span>${msg.latencies.net_ms}ms</span></div>
            <div class="telemetry-item">TTS: <span>${msg.latencies.tts_ms}ms</span></div>
            <div class="telemetry-item">E2E: <span>${msg.latencies.e2e_ms}ms</span></div>
        </div>
        <div class="msg-actions">
            <button class="btn-replay" onclick="replayTTS('${escapeHtml(msg.text)}')">🔊 Replay Speech</button>
        </div>
    `;

    feed.appendChild(card);
    feed.scrollTop = feed.scrollHeight;
}

// 7. Update Telemetry Dashboard Gauges
function updateTelemetryStats(msg) {
    totalMessages++;
    if (msg.audio_bytes) totalAudioBytes += msg.audio_bytes;
    if (msg.text_bytes) totalTextBytes += msg.text_bytes;

    document.getElementById("totalMessagesCount").innerText = totalMessages;
    document.getElementById("savedAudioBytes").innerText = `${(totalAudioBytes / 1024).toFixed(1)} KB`;
    document.getElementById("transmittedTextBytes").innerText = `${totalTextBytes} Bytes`;

    if (totalAudioBytes > 0) {
        const overallRed = (((totalAudioBytes - totalTextBytes) / totalAudioBytes) * 100).toFixed(2);
        document.getElementById("overallReduction").innerText = `${overallRed}%`;
    }

    if (msg.latencies) {
        document.getElementById("lastSttLatency").innerText = `${msg.latencies.stt_ms} ms`;
        document.getElementById("lastNetLatency").innerText = `${msg.latencies.net_ms} ms`;
        document.getElementById("lastTtsLatency").innerText = `${msg.latencies.tts_ms} ms`;
        document.getElementById("lastE2eLatency").innerText = `${msg.latencies.e2e_ms} ms`;
    }
}

// 8. Replay Audio Locally
async function replayTTS(text) {
    const lang = document.getElementById("languageSelect").value;
    await fetch("/api/replay_tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, language: lang })
    });
}

// 9. Quick Demo Fallback Samples
function initSampleButtons() {
    const buttons = document.querySelectorAll(".btn-sample");
    buttons.forEach((btn) => {
        btn.addEventListener("click", async () => {
            const sampleKey = btn.getAttribute("data-sample");
            const lang = document.getElementById("languageSelect").value;
            btn.disabled = true;
            btn.style.opacity = "0.5";
            try {
                await fetch("/api/send_sample", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ sample: sampleKey, language: lang })
                });
            } catch (e) {
                console.error("Failed to send sample:", e);
            } finally {
                btn.disabled = false;
                btn.style.opacity = "1";
            }
        });
    });
}

// 10. Peer Connect Form
function initConnectForm() {
    const btn = document.getElementById("updatePeerBtn");
    btn.addEventListener("click", async () => {
        const host = document.getElementById("peerHostInput").value.trim();
        const port = document.getElementById("peerPortInput").value.trim();
        if (!host || !port) return;

        btn.innerText = "CONNECTING...";
        try {
            await fetch("/api/connect", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ peer_host: host, peer_port: parseInt(port) })
            });
            btn.innerText = "CONNECTED";
            setTimeout(() => { btn.innerText = "UPDATE PEER"; }, 1500);
        } catch (e) {
            btn.innerText = "ERROR";
        }
    });
}

function escapeHtml(text) {
    if (!text) return "";
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
