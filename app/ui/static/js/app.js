/**
 * iTantra Mission Control JavaScript Client
 * Native 16kHz PCM WAV Audio Capture, Push-To-Talk, WebSockets & Alert Priority Queue
 */

let ws = null;
let isRecording = false;
let audioContext = null;
let micStream = null;
let scriptProcessor = null;
let recordedAudioBuffers = [];
let analyser = null;
let animFrameId = null;
let isSpacePressed = false;
let pollingInterval = null;

// Selected Priority and Message Type
let selectedPriority = 0; // 0=NORMAL, 1=ELEVATED, 2=ALERT, 3=DISTRESS
let selectedMessageType = 1; // 1=NORMAL, 2=VOICE_NOTE, 3=ALERT, 4=DISTRESS

// Cumulative Telemetry Stats
let totalAudioBytes = 0;
let totalTextBytes = 0;
let totalMessages = 0;

let currentActivePeer = { host: "127.0.0.1", port: 65432, node_id: null };
let knownDevices = [];
let currentOperatingMode = "walkie_talkie"; // "walkie_talkie" or "voice_mode"
const renderedMessageIds = new Set();

document.addEventListener("DOMContentLoaded", () => {
    initWebSocket();
    initStatus();
    initDiscovery();
    initModeSwitch();
    initPrioritySelector();
    initVisualizer();
    initPTTControls();
    initKeyboardShortcuts();
    initSampleButtons();
    initConnectForm();
    startPollingFallback();
});

// 1. WebSocket Management & Polling Fallback
function initWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    try {
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
            console.warn("[WS] Disconnected. Reconnecting in 2.5s...");
            updateConnectionBadge(false);
            setTimeout(initWebSocket, 2500);
        };

        ws.onerror = (e) => {
            console.warn("[WS] Error connecting, falling back to HTTP sync:", e);
            updateConnectionBadge(false);
        };
    } catch (e) {
        console.warn("[WS] WebSocket initialization failed, using HTTP sync:", e);
    }
}

function startPollingFallback() {
    pollingInterval = setInterval(async () => {
        try {
            await fetchDiscoveredDevices();
        } catch (e) {}

        try {
            const res = await fetch("/api/events");
            if (res.ok) {
                const events = await res.json();
                if (events && Array.isArray(events)) {
                    events.forEach(handleServerEvent);
                }
            }
        } catch (e) {}
    }, 1000);
}

function updateConnectionBadge(connected) {
    const badge = document.getElementById("nodeStatusBadge");
    if (badge) {
        badge.innerHTML = `<span class="pulse-dot"></span> NODE ACTIVE`;
        badge.className = "badge badge-node";
    }
}

// 2. Fetch Initial Node Info & Status
async function initStatus() {
    try {
        const res = await fetch("/api/status");
        const data = await res.json();
        
        document.getElementById("localNodeName").innerText = data.node_name;
        document.getElementById("localNodeIp").innerText = `${data.local_ip}:${data.tcp_listen_port}`;
        currentActivePeer.host = data.peer_host;
        currentActivePeer.port = data.peer_port;
        updateActivePeerDisplay(data.peer_host, data.peer_port, data.node_id);

        if (data.operating_mode) {
            setModeUI(data.operating_mode === "voice_mode" ? "voice" : "ptt");
        }

        // Fetch initial historical events once on page load
        const evRes = await fetch("/api/events");
        if (evRes.ok) {
            const history = await evRes.json();
            if (history && history.length > 0) {
                history.forEach(handleServerEvent);
            }
        }
    } catch (e) {
        console.error("Failed to fetch initial status:", e);
    }
}

function updateActivePeerDisplay(host, port, nodeId) {
    const badge = document.getElementById("peerBadge");
    const nameEl = document.getElementById("peerNodeName");
    if (badge) badge.innerText = `${host}:${port}`;
    if (nameEl) nameEl.innerText = nodeId ? `Target: ${nodeId}` : `Target: DIRECT IP`;
}

// 3. Priority Selector Management
function initPrioritySelector() {
    const priButtons = document.querySelectorAll(".btn-pri");
    priButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            priButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            selectedPriority = parseInt(btn.getAttribute("data-pri") || "0");
            selectedMessageType = parseInt(btn.getAttribute("data-type") || "1");
            console.log(`[Priority Selected] Priority: ${selectedPriority}, Type: ${selectedMessageType}`);
        });
    });
}

// 4. Mode Switch: Mode A (Walkie-Talkie PTT) vs Mode B (Hands-Free Voice VAD)
function initModeSwitch() {
    const pttBtn = document.getElementById("modePttBtn");
    const voiceBtn = document.getElementById("modeVoiceBtn");

    if (pttBtn) {
        pttBtn.addEventListener("click", () => switchOperatingMode("walkie_talkie"));
    }
    if (voiceBtn) {
        voiceBtn.addEventListener("click", () => switchOperatingMode("voice_mode"));
    }
}

async function switchOperatingMode(mode) {
    try {
        const res = await fetch("/api/mode/switch", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode: mode })
        });
        const data = await res.json();
        setModeUI(mode === "voice_mode" ? "voice" : "ptt");
    } catch (e) {
        console.error("Mode switch failed:", e);
    }
}

function setModeUI(mode) {
    currentOperatingMode = (mode === "voice" || mode === "voice_mode") ? "voice_mode" : "walkie_talkie";
    const pttBtn = document.getElementById("modePttBtn");
    const voiceBtn = document.getElementById("modeVoiceBtn");
    const mainPttButton = document.getElementById("pttButton");
    const pttHint = document.getElementById("pttHint");
    const vadIndicator = document.getElementById("vadStatusIndicator");

    if (currentOperatingMode === "voice_mode") {
        if (pttBtn) pttBtn.classList.remove("active");
        if (voiceBtn) voiceBtn.classList.add("active");
        if (mainPttButton) {
            mainPttButton.classList.add("voice-mode");
            document.getElementById("pttButtonLabel").innerText = "HANDS-FREE VAD ACTIVE";
            document.getElementById("pttIcon").innerText = "⚡";
        }
        if (pttHint) pttHint.innerText = "SPEAK FREELY // AUTOMATIC SPEECH SEGMENTATION ACTIVE";
        if (vadIndicator) vadIndicator.style.display = "flex";
    } else {
        if (voiceBtn) voiceBtn.classList.remove("active");
        if (pttBtn) pttBtn.classList.add("active");
        if (mainPttButton) {
            mainPttButton.classList.remove("voice-mode", "speech-active");
            document.getElementById("pttButtonLabel").innerText = "PUSH TO TALK";
            document.getElementById("pttIcon").innerText = "🎙️";
        }
        if (pttHint) pttHint.innerText = "HOLD SPACEBAR OR CLICK TO TRANSMIT";
        if (vadIndicator) vadIndicator.style.display = "none";
    }
}

// 5. Push-To-Talk Control Handlers
function initPTTControls() {
    const btn = document.getElementById("pttButton");
    if (!btn) return;

    btn.addEventListener("mousedown", (e) => {
        if (e.button === 0 && currentOperatingMode === "walkie_talkie") startPTT();
    });

    btn.addEventListener("mouseup", (e) => {
        if (e.button === 0 && currentOperatingMode === "walkie_talkie") stopPTT();
    });

    btn.addEventListener("touchstart", (e) => {
        e.preventDefault();
        if (currentOperatingMode === "walkie_talkie") startPTT();
    });

    btn.addEventListener("touchend", (e) => {
        e.preventDefault();
        if (currentOperatingMode === "walkie_talkie") stopPTT();
    });
}

function initKeyboardShortcuts() {
    window.addEventListener("keydown", (e) => {
        if (e.code === "Space" && !isSpacePressed && e.target.tagName !== "INPUT" && currentOperatingMode === "walkie_talkie") {
            isSpacePressed = true;
            e.preventDefault();
            startPTT();
        }
    });

    window.addEventListener("keyup", (e) => {
        if (e.code === "Space" && isSpacePressed && currentOperatingMode === "walkie_talkie") {
            isSpacePressed = false;
            e.preventDefault();
            stopPTT();
        }
    });
}

async function startPTT() {
    if (isRecording) return;
    isRecording = true;
    updateRecordingUI(true, false);
    recordedAudioBuffers = [];

    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        try {
            micStream = await navigator.mediaDevices.getUserMedia({
                audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true, noiseSuppression: true }
            });

            audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
            const source = audioContext.createMediaStreamSource(micStream);
            
            const trueSampleRate = audioContext.sampleRate || 16000;
            console.log(`[AudioContext Initialized] Sample Rate: ${trueSampleRate} Hz`);
            
            analyser = audioContext.createAnalyser();
            analyser.fftSize = 256;
            source.connect(analyser);
            drawWaveform();

            scriptProcessor = audioContext.createScriptProcessor(4096, 1, 1);
            scriptProcessor.onaudioprocess = (e) => {
                if (!isRecording) return;
                const channelData = e.inputBuffer.getChannelData(0);
                recordedAudioBuffers.push(new Float32Array(channelData));
            };

            source.connect(scriptProcessor);
            scriptProcessor.connect(audioContext.destination);
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

    if (scriptProcessor && micStream) {
        let sampleRate = 16000;
        try {
            if (audioContext && audioContext.sampleRate) {
                sampleRate = audioContext.sampleRate;
            }
            scriptProcessor.disconnect();
            micStream.getTracks().forEach(track => track.stop());
            if (audioContext && audioContext.state !== "closed") {
                audioContext.close();
            }
        } catch (e) {
            console.warn("Cleanup audio error:", e);
        }

        if (animFrameId) cancelAnimationFrame(animFrameId);
        initVisualizer();

        let totalLen = recordedAudioBuffers.reduce((acc, curr) => acc + curr.length, 0);
        if (totalLen === 0 || totalLen < sampleRate * 0.2) {
            // Less than 200ms of audio, ignore micro-clicks
            updateRecordingUI(false, false);
            return;
        }

        let flatAudio = new Float32Array(totalLen);
        let offset = 0;
        for (let chunk of recordedAudioBuffers) {
            flatAudio.set(chunk, offset);
            offset += chunk.length;
        }

        const wavBlob = encodePCM16WAV(flatAudio, sampleRate);
        const formData = new FormData();
        formData.append("file", wavBlob, "ptt_speech.wav");
        
        const lang = document.getElementById("languageSelect").value;
        formData.append("lang", lang);
        formData.append("priority", selectedPriority);
        formData.append("message_type", selectedMessageType);

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
    } else {
        const lang = document.getElementById("languageSelect").value;
        try {
            await fetch(`/api/ptt/backend_stop?lang=${lang}&priority=${selectedPriority}&message_type=${selectedMessageType}`, {
                method: "POST"
            });
        } catch (e) {
            console.error("Failed to stop backend mic:", e);
        } finally {
            updateRecordingUI(false, false);
        }
    }
}

function updateRecordingUI(recording, processing) {
    const btn = document.getElementById("pttButton");
    const label = document.getElementById("pttButtonLabel");
    const icon = document.getElementById("pttIcon");
    if (!btn) return;

    if (recording) {
        btn.classList.add("recording");
        if (label) label.innerText = "RECORDING AUDIO...";
        if (icon) icon.innerText = "🔴";
    } else if (processing) {
        btn.classList.remove("recording");
        if (label) label.innerText = "NEURAL INFERENCE...";
        if (icon) icon.innerText = "⚡";
    } else {
        btn.classList.remove("recording");
        if (label) label.innerText = currentOperatingMode === "voice_mode" ? "HANDS-FREE VAD ACTIVE" : "PUSH TO TALK";
        if (icon) icon.innerText = currentOperatingMode === "voice_mode" ? "⚡" : "🎙️";
    }
}

// 6. Encode Raw Float32 Array to 16kHz PCM WAV
function encodePCM16WAV(samples, sampleRate) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);

    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + samples.length * 2, true);
    writeString(view, 8, 'WAVE');
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true); // PCM
    view.setUint16(22, 1, true); // Mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeString(view, 36, 'data');
    view.setUint32(40, samples.length * 2, true);

    let offset = 44;
    for (let i = 0; i < samples.length; i++, offset += 2) {
        let s = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }

    return new Blob([view], { type: 'audio/wav' });
}

function writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
    }
}

// 7. Live Waveform Canvas Visualizer
function initVisualizer() {
    const canvas = document.getElementById("waveformCanvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#0c121e";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "rgba(0, 240, 255, 0.2)";
    ctx.lineWidth = 1;
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
        if (!isRecording) return;
        animFrameId = requestAnimationFrame(render);
        analyser.getByteTimeDomainData(dataArray);

        ctx.fillStyle = "#0c121e";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.lineWidth = 2;
        ctx.strokeStyle = "#00f0ff";
        ctx.beginPath();

        const sliceWidth = canvas.width * 1.0 / bufferLength;
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

// 8. Append Message Cards with Priority Badges
function appendMessageCard(msg) {
    if (!msg) return;

    // Deduplicate identical messages to prevent feed looping
    const msgId = msg.id || `${msg.direction}_${msg.sender}_${msg.timestamp}_${msg.text}_${msg.audio_bytes || 0}_${msg.text_bytes || 0}`;
    if (renderedMessageIds.has(msgId)) {
        return;
    }
    renderedMessageIds.add(msgId);

    const feed = document.getElementById("conversationFeed");
    const emptyNotice = document.getElementById("emptyFeedNotice");
    if (emptyNotice) emptyNotice.remove();

    const isOutgoing = msg.direction === "outgoing";
    const priName = (msg.priority || "NORMAL").toUpperCase();
    const typeName = (msg.message_type || "NORMAL").toUpperCase();
    
    const isDistress = msg.is_distress || priName === "DISTRESS" || typeName === "DISTRESS";
    const isAlert = msg.is_alert || priName === "ALERT" || typeName === "ALERT";

    const card = document.createElement("div");
    card.className = `msg-card ${isOutgoing ? "outgoing" : "incoming"} ${isDistress ? "distress" : (isAlert ? "alert" : "")}`;

    card.innerHTML = `
        <div class="msg-meta">
            <div class="msg-sender">
                ${isOutgoing ? "↗ OUTGOING [TRANSMIT]" : "↙ INCOMING [RECEIVED]"} · ${escapeHtml(msg.sender)}
                <span class="msg-pri-badge ${priName}">${isDistress ? "🚨 DISTRESS" : (isAlert ? "⚠ ALERT" : (typeName === "VOICE_NOTE" ? "VOICE NOTE" : "NORMAL"))}</span>
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

    // Update Live Telemetry for this new message
    updateTelemetryStats(msg);

    // Trigger visual emergency banner if Distress or Alert
    if (isDistress) {
        showEmergencyBanner("DISTRESS SIGNAL ACTIVE", `Priority Playback Lock Active: "${msg.text}"`, false);
    } else if (isAlert) {
        showEmergencyBanner("ALERT MESSAGE", `Priority Notice from ${msg.sender}: "${msg.text}"`, true);
    }
}

function showEmergencyBanner(title, body, isAlertOnly) {
    const banner = document.getElementById("emergencyBanner");
    const titleEl = document.getElementById("emergencyTitle");
    const bodyEl = document.getElementById("emergencyBody");
    const iconEl = document.getElementById("emergencyIcon");

    if (banner) {
        banner.style.display = "flex";
        if (isAlertOnly) {
            banner.className = "emergency-banner alert-mode";
            if (iconEl) iconEl.innerText = "⚠";
        } else {
            banner.className = "emergency-banner";
            if (iconEl) iconEl.innerText = "🚨";
        }
        if (titleEl) titleEl.innerText = title;
        if (bodyEl) bodyEl.innerText = body;

        // Auto-clear banner after 8 seconds
        setTimeout(() => {
            banner.style.display = "none";
        }, 8000);
    }
}

// 9. Update Telemetry Dashboard Gauges for Each New Message
function updateTelemetryStats(msg) {
    if (!msg) return;

    totalMessages++;
    if (msg.audio_bytes) totalAudioBytes += msg.audio_bytes;
    if (msg.text_bytes) totalTextBytes += msg.text_bytes;

    const countEl = document.getElementById("totalMessagesCount");
    const savedAudioEl = document.getElementById("savedAudioBytes");
    const textBytesEl = document.getElementById("transmittedTextBytes");
    const redValEl = document.getElementById("overallReduction");
    const redBarEl = document.getElementById("reductionProgressBar");
    const senderTagEl = document.getElementById("lastMsgSender");

    if (countEl) countEl.innerText = totalMessages;
    if (savedAudioEl) savedAudioEl.innerText = `${(totalAudioBytes / 1024).toFixed(1)} KB`;
    if (textBytesEl) textBytesEl.innerText = `${totalTextBytes} Bytes`;

    let reductionPct = msg.reduction_percent || "99.8%";
    if (totalAudioBytes > 0) {
        const overallRed = (((totalAudioBytes - totalTextBytes) / totalAudioBytes) * 100).toFixed(2);
        reductionPct = `${overallRed}%`;
    }
    if (redValEl) redValEl.innerText = reductionPct;
    if (redBarEl) redBarEl.style.width = reductionPct;

    if (senderTagEl) {
        const dir = msg.direction === "outgoing" ? "TX: " : "RX: ";
        senderTagEl.innerText = `(${dir}${msg.sender || "NODE"})`;
    }

    if (msg.latencies) {
        const stt = Number(msg.latencies.stt_ms) || 0;
        const net = Number(msg.latencies.net_ms) || 0;
        const tts = Number(msg.latencies.tts_ms) || 0;
        const e2e = Number(msg.latencies.e2e_ms) || (stt + net + tts) || 1;

        const sttEl = document.getElementById("lastSttLatency");
        const netEl = document.getElementById("lastNetLatency");
        const ttsEl = document.getElementById("lastTtsLatency");
        const e2eEl = document.getElementById("lastE2eLatency");

        const sttBar = document.getElementById("sttLatencyBar");
        const netBar = document.getElementById("netLatencyBar");
        const ttsBar = document.getElementById("ttsLatencyBar");

        if (sttEl) sttEl.innerText = `${stt.toFixed(1)} ms`;
        if (netEl) netEl.innerText = `${net.toFixed(1)} ms`;
        if (ttsEl) ttsEl.innerText = `${tts.toFixed(1)} ms`;
        if (e2eEl) e2eEl.innerText = `${e2e.toFixed(1)} ms`;

        // Dynamically compute proportional bar widths
        const sttPct = Math.min(100, Math.max(stt > 0 ? 10 : 0, Math.round((stt / e2e) * 100)));
        const netPct = Math.min(100, Math.max(net > 0 ? 10 : 0, Math.round((net / e2e) * 100)));
        const ttsPct = Math.min(100, Math.max(tts > 0 ? 10 : 0, Math.round((tts / e2e) * 100)));

        if (sttBar) sttBar.style.width = `${sttPct}%`;
        if (netBar) netBar.style.width = `${netPct}%`;
        if (ttsBar) ttsBar.style.width = `${ttsPct}%`;

        // Visual pulse highlight on update
        const card = document.getElementById("telemetryLatencyCard");
        if (card) {
            card.style.borderColor = "var(--accent-cyan)";
            card.style.boxShadow = "0 0 16px rgba(0, 240, 255, 0.25)";
            setTimeout(() => {
                card.style.borderColor = "";
                card.style.boxShadow = "";
            }, 600);
        }
    }
}

// 10. Replay Audio Locally
async function replayTTS(text) {
    const lang = document.getElementById("languageSelect").value;
    await fetch("/api/replay_tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, language: lang })
    });
}

// 11. Quick Demo Fallback Samples
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
                    body: JSON.stringify({
                        sample: sampleKey,
                        language: lang,
                        priority: selectedPriority,
                        message_type: selectedMessageType
                    })
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

// 12. Peer Connect Form
function initConnectForm() {
    const btn = document.getElementById("updatePeerBtn");
    if (!btn) return;
    btn.addEventListener("click", async () => {
        const host = document.getElementById("peerHostInput").value.trim();
        const port = document.getElementById("peerPortInput").value.trim();
        if (!host || !port) return;

        btn.innerText = "CONNECTING...";
        try {
            const res = await fetch("/api/connect_device", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ip: host, port: parseInt(port) })
            });
            const data = await res.json();
            updateActivePeerDisplay(host, port, data.node_id);
            btn.innerText = "CONNECTED";
            setTimeout(() => { btn.innerText = "CONNECT TO IP"; }, 1500);
        } catch (e) {
            btn.innerText = "ERROR";
        }
    });
}

// 13. Automatic Device Discovery Management
function initDiscovery() {
    const refreshBtn = document.getElementById("refreshDevicesBtn");
    if (refreshBtn) {
        refreshBtn.addEventListener("click", async () => {
            refreshBtn.classList.add("rotating");
            await fetchDiscoveredDevices();
            setTimeout(() => { refreshBtn.classList.remove("rotating"); }, 500);
        });
    }
    fetchDiscoveredDevices();
}

async function fetchDiscoveredDevices() {
    try {
        const res = await fetch("/api/devices");
        if (res.ok) {
            const devices = await res.json();
            knownDevices = devices || [];
            renderDiscoveredDevices(knownDevices);
        }
    } catch (e) {
        console.warn("Failed to fetch discovered devices:", e);
    }
}

function renderDiscoveredDevices(devices) {
    const container = document.getElementById("discoveredDevicesList");
    if (!container) return;

    if (!devices || devices.length === 0) {
        container.innerHTML = `
            <div class="scanning-notice">
              <span class="radar-sweep">📡</span>
              <span>Scanning for nearby iTantra nodes (_itantra._tcp)...</span>
            </div>
        `;
        return;
    }

    container.innerHTML = "";

    devices.forEach((dev) => {
        const isActive = (dev.ip === currentActivePeer.host && dev.port === currentActivePeer.port) ||
                         (currentActivePeer.node_id && dev.node_id === currentActivePeer.node_id);
        const isOnline = dev.online !== false;

        const card = document.createElement("div");
        card.className = `device-card ${isActive ? "active-device" : ""} ${isOnline ? "" : "offline-device"}`;

        const langBadges = (dev.languages || ["en"])
            .map(l => `<span class="tag-badge lang">${escapeHtml(l.toUpperCase())}</span>`).join(" ");

        const capBadges = (dev.capabilities || ["stt", "tts"])
            .map(c => `<span class="tag-badge cap">${escapeHtml(c.toUpperCase())}</span>`).join(" ");

        card.innerHTML = `
            <div class="device-card-header">
                <div class="device-name-group">
                    <span class="status-dot ${isOnline ? "online" : "offline"}" title="${isOnline ? "ONLINE" : "OFFLINE"}"></span>
                    <span class="device-title">${escapeHtml(dev.device_name || dev.node_id)}</span>
                </div>
                <span class="device-ip">${escapeHtml(dev.ip)}:${dev.port}</span>
            </div>
            
            <div class="device-tags">
                ${langBadges}
                ${capBadges}
                <span class="tag-badge" style="font-size: 0.6rem;">${escapeHtml(dev.device_type || "node")}</span>
            </div>

            <button class="btn-device-connect ${isActive ? "active" : ""}" 
                    ${isActive ? "disabled" : ""} 
                    onclick="connectToDiscoveredDevice('${escapeHtml(dev.node_id)}', '${escapeHtml(dev.ip)}', ${dev.port})">
                ${isActive ? "✓ ACTIVE PEER LINK" : "⚡ CONNECT"}
            </button>
        `;

        container.appendChild(card);
    });
}

async function connectToDiscoveredDevice(nodeId, ip, port) {
    try {
        const res = await fetch("/api/connect_device", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ node_id: nodeId, ip: ip, port: port })
        });
        const data = await res.json();
        updateActivePeerDisplay(ip, port, nodeId);
    } catch (e) {
        console.error("Failed to connect to discovered device:", e);
    }
}

// 14. Server Event Dispatcher
function handleServerEvent(data) {
    if (data.type === "MESSAGE_RECEIVED" || data.type === "MESSAGE_SENT") {
        appendMessageCard(data);
    } else if (data.type === "PLAYBACK_EVENT") {
        if (data.data && data.data.event === "playback_finished") {
            const banner = document.getElementById("emergencyBanner");
            if (banner) banner.style.display = "none";
        }
    } else if (data.type === "RECORDING_STATE") {
        updateRecordingUI(data.recording, data.processing);
    } else if (data.type === "MODE_SWITCH") {
        setModeUI(data.operating_mode === "voice_mode" ? "voice" : "ptt");
    } else if (data.type === "DEVICE_DISCOVERY_UPDATE") {
        knownDevices = data.devices || [];
        renderDiscoveredDevices(knownDevices);
    }
}

function escapeHtml(text) {
    if (!text) return "";
    return text.toString().replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
