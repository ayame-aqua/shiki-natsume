const messagesEl = document.getElementById("messages");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send");
const liveBtn = document.getElementById("live");
const statusEl = document.getElementById("status");
const vadMeterEl = document.getElementById("vad-meter");
const nameEl = document.getElementById("character-name");

const ERROR_TEXT = {
  BAD_REQUEST: "消息不完整",
  DUPLICATE: "这条已经处理过了",
  LLM_FAILED: "她这会儿没接上",
  INTERNAL: "内部出错了",
};

const RECORD_MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/mp4",
];

// 开口即采。旧逻辑要连续 500ms 超过 0.07 才开始录音，「晚上好」这种短句过不了门。
const VAD_MIN_SPEECH_MS = 200;
const VAD_SILENCE_MS = 800;
const VAD_MAX_UTTER_MS = 8000;
const VAD_EMPTY_RESTART_MS = 2500;
const VAD_HANGOVER_MS = 240;
const VAD_POLL_MS = 40;
const VAD_TIMESLICE_MS = 200;
const VAD_SPEECH_HZ_LO = 250;
const VAD_SPEECH_HZ_HI = 3800;
const VAD_SPEAK_OVER_FLOOR = 0.02;
const VAD_SPEAK_RATIO = 1.6;
const VAD_SILENCE_RATIO = 1.25;
const VAD_FLOOR_EMA = 0.1;
const VAD_FLOOR_MIN = 0.008;
const VAD_REPORT_MS = 200;
const ANALYSER_FFT_SIZE = 2048;
const LIP_SYNC_FFT_SIZE = 256;

let socket = null;
let busy = false;
let currentAudio = null;
let liveMode = false;
let liveStream = null;
let audioContext = null;
let playbackContext = null;
let analyser = null;
let sourceNode = null;
let tapNode = null;
let vadTimer = null;
let micLabel = "";
let zeroBandSince = 0;
let mediaRecorder = null;
let recordChunks = [];
let sendAfterStop = false;
let silenceStartedAt = 0;
let utteranceStartedAt = 0;
let lastVoiceAt = 0;
let voicedMs = 0;
let noiseFloor = VAD_FLOOR_MIN;
let peakBand = 0;
let lastVadReportAt = 0;

function isSpeaking() {
  if (!currentAudio) {
    return false;
  }
  if (typeof currentAudio.paused === "boolean") {
    return !currentAudio.paused && !currentAudio.ended;
  }
  return true;
}

function stopCurrentAudio() {
  if (!currentAudio) {
    return;
  }
  const handle = currentAudio;
  currentAudio = null;
  if (typeof handle.pause === "function") {
    handle.pause();
    return;
  }
  if (typeof handle.stop === "function") {
    try {
      handle.stop();
    } catch {
      // already stopped
    }
  }
}

function isRecording() {
  return mediaRecorder !== null;
}

function listeningStatus() {
  return liveMode ? "在听…" : "在线";
}

function syncComposer() {
  const socketOpen = Boolean(socket && socket.readyState === WebSocket.OPEN);
  sendBtn.disabled = busy || !socketOpen || isRecording();
  if (liveBtn) {
    liveBtn.disabled = !socketOpen;
    liveBtn.textContent = liveMode ? "结束" : "对话";
    liveBtn.classList.toggle("live-on", liveMode);
  }
}

async function ensurePlaybackContext() {
  const Context = window.AudioContext || window.webkitAudioContext;
  if (!Context) {
    return null;
  }
  if (!playbackContext || playbackContext.state === "closed") {
    playbackContext = new Context();
  }
  if (playbackContext.state === "suspended") {
    await playbackContext.resume();
  }
  return playbackContext;
}

function callLive2d(methodName, ...args) {
  const api = window.live2d;
  if (!api || typeof api[methodName] !== "function") {
    return;
  }
  api[methodName](...args);
}

function playAssistantAudio(url) {
  void playAssistantAudioAsync(url);
}

async function playAssistantAudioAsync(url) {
  stopCurrentAudio();
  callLive2d("stopLipSync");
  const clearIfCurrent = (handle) => {
    if (currentAudio === handle) {
      currentAudio = null;
      callLive2d("stopLipSync");
      callLive2d("releaseEmotion");
    }
    if (!busy) {
      setStatus(listeningStatus());
    }
    syncComposer();
  };
  const playCtx = await ensurePlaybackContext();
  if (playCtx) {
    try {
      const response = await fetch(url);
      const raw = await response.arrayBuffer();
      const decoded = await playCtx.decodeAudioData(raw.slice(0));
      const source = playCtx.createBufferSource();
      const mouthAnalyser = playCtx.createAnalyser();
      mouthAnalyser.fftSize = LIP_SYNC_FFT_SIZE;
      source.buffer = decoded;
      source.connect(mouthAnalyser);
      mouthAnalyser.connect(playCtx.destination);
      source.addEventListener("ended", () => clearIfCurrent(source));
      currentAudio = source;
      source.start();
      callLive2d("startLipSync", mouthAnalyser);
      setStatus("她在说话");
      syncComposer();
      return;
    } catch {
      stopCurrentAudio();
    }
  }
  const audio = new Audio(url);
  currentAudio = audio;
  audio.addEventListener("ended", () => clearIfCurrent(audio));
  try {
    await audio.play();
    setStatus("她在说话");
    syncComposer();
  } catch {
    setStatus("语音播放失败");
    clearIfCurrent(audio);
  }
}

function setStatus(text) {
  if (statusEl) {
    statusEl.textContent = text;
  }
}

function appendMessage(role, text) {
  const row = document.createElement("div");
  row.className = `msg ${role}`;
  const who = document.createElement("div");
  who.className = "who";
  who.textContent = role === "user" ? "你" : nameEl?.textContent || "她";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  row.append(who, bubble);
  messagesEl.append(row);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function newMessageId() {
  return crypto.randomUUID();
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || "");
      const comma = result.indexOf(",");
      resolve(comma >= 0 ? result.slice(comma + 1) : result);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

function pickRecordMime() {
  if (typeof MediaRecorder === "undefined") {
    return "";
  }
  for (const mime of RECORD_MIME_CANDIDATES) {
    if (MediaRecorder.isTypeSupported(mime)) {
      return mime;
    }
  }
  return "";
}

function currentBand() {
  if (!analyser || !audioContext) {
    return 0;
  }
  const freq = new Uint8Array(analyser.frequencyBinCount);
  analyser.getByteFrequencyData(freq);
  const binHz = audioContext.sampleRate / analyser.fftSize;
  const low = Math.max(1, Math.floor(VAD_SPEECH_HZ_LO / binHz));
  const high = Math.min(freq.length - 1, Math.ceil(VAD_SPEECH_HZ_HI / binHz));
  let sum = 0;
  let count = 0;
  for (let index = low; index <= high; index += 1) {
    sum += freq[index];
    count += 1;
  }
  const spectrum = count ? sum / count / 255 : 0;
  const wave = new Uint8Array(analyser.fftSize);
  analyser.getByteTimeDomainData(wave);
  let energy = 0;
  for (let index = 0; index < wave.length; index += 1) {
    const centered = (wave[index] - 128) / 128;
    energy += centered * centered;
  }
  return Math.max(spectrum, Math.sqrt(energy / wave.length));
}

function isVoiceOn(band) {
  const overFloor = Math.max(noiseFloor * VAD_SPEAK_RATIO, noiseFloor + VAD_SPEAK_OVER_FLOOR);
  return band >= overFloor;
}

function isVoiceOff(band) {
  return band <= noiseFloor * VAD_SILENCE_RATIO;
}

function percent(value) {
  return `${Math.round(Math.max(0, value) * 100)}%`;
}

function publishVad(band) {
  const voice = isVoiceOn(band);
  const snapshot = {
    band,
    floor: noiseFloor,
    peak: peakBand,
    recording: isRecording(),
    voice,
    busy,
    speaking: isSpeaking(),
  };
  window.__natsumeVad = snapshot;
  if (vadMeterEl) {
    vadMeterEl.hidden = false;
    const bar = "▮".repeat(Math.min(20, Math.round(band * 20)))
      + "▯".repeat(Math.max(0, 20 - Math.round(band * 20)));
    const state = snapshot.recording ? "采集中" : (voice ? "过线" : "安静");
    const device = micLabel ? ` ${micLabel}` : "";
    vadMeterEl.textContent = `音量 ${percent(band)} ${bar} 底噪 ${percent(noiseFloor)} 峰值 ${percent(peakBand)} ${state}${device}`;
  }
  const now = Date.now();
  if (now - lastVadReportAt < VAD_REPORT_MS) {
    return;
  }
  lastVadReportAt = now;
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    return;
  }
  socket.send(JSON.stringify({
    type: "vad_level",
    band,
    floor: noiseFloor,
    peak: peakBand,
    recording: snapshot.recording,
    voice,
  }));
}

function updateNoiseFloor(band) {
  if (band >= noiseFloor * VAD_SILENCE_RATIO) {
    return;
  }
  noiseFloor = noiseFloor * (1 - VAD_FLOOR_EMA) + band * VAD_FLOOR_EMA;
  if (noiseFloor < VAD_FLOOR_MIN) {
    noiseFloor = VAD_FLOOR_MIN;
  }
}

function stopTracks() {
  if (!liveStream) {
    return;
  }
  for (const track of liveStream.getTracks()) {
    track.stop();
  }
  liveStream = null;
}

function closeAudioGraph() {
  if (vadTimer !== null) {
    window.clearInterval(vadTimer);
    vadTimer = null;
  }
  if (sourceNode) {
    sourceNode.disconnect();
    sourceNode = null;
  }
  if (tapNode) {
    tapNode.disconnect();
    tapNode = null;
  }
  analyser = null;
  if (audioContext) {
    void audioContext.close();
    audioContext = null;
  }
}

function resetVadClock() {
  silenceStartedAt = 0;
  utteranceStartedAt = 0;
  lastVoiceAt = 0;
  voicedMs = 0;
  peakBand = 0;
}

function cancelUtterance() {
  sendAfterStop = false;
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
    return;
  }
  recordChunks = [];
  resetVadClock();
}

function stopUtterance() {
  if (!mediaRecorder || mediaRecorder.state === "inactive") {
    return;
  }
  sendAfterStop = true;
  mediaRecorder.stop();
}

function beginUtterance() {
  if (!liveStream || isRecording() || busy || isSpeaking()) {
    return;
  }
  const mime = pickRecordMime();
  recordChunks = [];
  sendAfterStop = true;
  mediaRecorder = mime
    ? new MediaRecorder(liveStream, { mimeType: mime })
    : new MediaRecorder(liveStream);
  const usedMime = mediaRecorder.mimeType || mime || "audio/webm";
  mediaRecorder.addEventListener("dataavailable", (event) => {
    if (event.data && event.data.size > 0) {
      recordChunks.push(event.data);
    }
  });
  mediaRecorder.addEventListener("stop", () => {
    mediaRecorder = null;
    const shouldSend = sendAfterStop;
    sendAfterStop = false;
    resetVadClock();
    if (shouldSend) {
      void sendRecording(usedMime);
    } else {
      recordChunks = [];
      syncComposer();
    }
  }, { once: true });
  utteranceStartedAt = Date.now();
  silenceStartedAt = 0;
  peakBand = 0;
  mediaRecorder.start(VAD_TIMESLICE_MS);
  setStatus("在听你说…");
  syncComposer();
}

function hasUtterance() {
  return voicedMs >= VAD_MIN_SPEECH_MS || isVoiceOn(peakBand);
}

function warnIfSilent(band) {
  const now = Date.now();
  if (band > 0.001) {
    zeroBandSince = 0;
    return;
  }
  if (!zeroBandSince) {
    zeroBandSince = now;
  }
  if (now - zeroBandSince >= 4000) {
    setStatus("麦克风音量一直是 0，换输入设备或检查浏览器权限");
  }
}

function vadTick() {
  if (!liveMode || !analyser) {
    return;
  }
  if (audioContext && audioContext.state === "suspended") {
    void audioContext.resume();
  }
  const band = currentBand();
  publishVad(band);
  warnIfSilent(band);
  if (busy || isSpeaking()) {
    if (isRecording()) {
      cancelUtterance();
    }
    resetVadClock();
    return;
  }
  if (!isRecording()) {
    updateNoiseFloor(band);
    beginUtterance();
    return;
  }
  const now = Date.now();
  if (band > peakBand) {
    peakBand = band;
  }
  if (isVoiceOn(band)) {
    lastVoiceAt = now;
    voicedMs += VAD_POLL_MS;
    silenceStartedAt = 0;
  } else if (lastVoiceAt && now - lastVoiceAt < VAD_HANGOVER_MS) {
    silenceStartedAt = 0;
  } else {
    updateNoiseFloor(band);
    if (!silenceStartedAt) {
      silenceStartedAt = now;
    }
    const silentFor = now - silenceStartedAt;
    if (hasUtterance() && silentFor >= VAD_SILENCE_MS) {
      stopUtterance();
      return;
    }
    if (!hasUtterance() && silentFor >= VAD_EMPTY_RESTART_MS) {
      cancelUtterance();
      return;
    }
  }
  if (now - utteranceStartedAt >= VAD_MAX_UTTER_MS) {
    if (hasUtterance()) {
      stopUtterance();
    } else {
      cancelUtterance();
    }
  }
}

async function startLive() {
  if (liveMode || !socket || socket.readyState !== WebSocket.OPEN) {
    return;
  }
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    setStatus("这个浏览器不能录音");
    return;
  }
  try {
    liveStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: true,
        channelCount: 1,
      },
    });
  } catch {
    setStatus("没有麦克风权限");
    return;
  }
  const Context = window.AudioContext || window.webkitAudioContext;
  if (!Context) {
    stopTracks();
    setStatus("这个浏览器不能实时听");
    return;
  }
  const track = liveStream.getAudioTracks()[0];
  micLabel = (track && track.label) || "麦克风";
  const rate = track && track.getSettings ? track.getSettings().sampleRate : 0;
  audioContext = typeof rate === "number" && rate > 0
    ? new Context({ sampleRate: rate })
    : new Context();
  if (audioContext.state === "suspended") {
    await audioContext.resume();
  }
  await ensurePlaybackContext();
  sourceNode = audioContext.createMediaStreamSource(liveStream);
  analyser = audioContext.createAnalyser();
  analyser.fftSize = ANALYSER_FFT_SIZE;
  analyser.smoothingTimeConstant = 0.2;
  analyser.minDecibels = -90;
  analyser.maxDecibels = -25;
  // 接到隐藏的 MediaStreamDestination，不要回灌扬声器。
  // 回灌 + echoCancellation 会把输入整段抵消，音量条就会一直是 0。
  tapNode = audioContext.createMediaStreamDestination();
  sourceNode.connect(analyser);
  analyser.connect(tapNode);
  liveMode = true;
  noiseFloor = VAD_FLOOR_MIN;
  zeroBandSince = 0;
  resetVadClock();
  vadTimer = window.setInterval(vadTick, VAD_POLL_MS);
  beginUtterance();
  setStatus("在听…");
  syncComposer();
}

function stopLive() {
  liveMode = false;
  if (isRecording()) {
    cancelUtterance();
  }
  closeAudioGraph();
  stopTracks();
  micLabel = "";
  zeroBandSince = 0;
  resetVadClock();
  if (vadMeterEl) {
    vadMeterEl.hidden = true;
  }
  if (!busy && !isSpeaking()) {
    setStatus("在线");
  }
  syncComposer();
}

function toggleLive() {
  if (liveMode) {
    stopLive();
    return;
  }
  void startLive();
}

async function sendRecording(mime) {
  const blob = new Blob(recordChunks, { type: mime });
  recordChunks = [];
  if (!blob.size || !socket || socket.readyState !== WebSocket.OPEN) {
    if (liveMode) {
      setStatus("在听…");
    } else {
      setStatus("没听清");
    }
    busy = false;
    syncComposer();
    return;
  }
  busy = true;
  syncComposer();
  setStatus("正在听…");
  try {
    const data = await blobToBase64(blob);
    socket.send(JSON.stringify({
      type: "user_audio",
      message_id: newMessageId(),
      mime,
      data_base64: data,
    }));
  } catch {
    setStatus(liveMode ? "在听…" : "录音发送失败");
    busy = false;
    syncComposer();
  }
}

function sendText() {
  const text = (inputEl.value || "").trim();
  if (!text || busy || isRecording() || !socket || socket.readyState !== WebSocket.OPEN) {
    return;
  }
  const messageId = newMessageId();
  busy = true;
  syncComposer();
  appendMessage("user", text);
  inputEl.value = "";
  socket.send(JSON.stringify({ type: "user_text", message_id: messageId, text }));
}

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${proto}://${location.host}/ws/chat`);
  socket.addEventListener("open", () => {
    setStatus(listeningStatus());
    syncComposer();
  });
  socket.addEventListener("close", () => {
    if (liveMode) {
      stopLive();
    }
    setStatus("掉线了，刷新页面");
    busy = false;
    syncComposer();
  });
  socket.addEventListener("message", (event) => {
    let frame;
    try {
      frame = JSON.parse(event.data);
    } catch {
      setStatus("收到无法解析的消息");
      return;
    }
    if (frame.type === "status") {
      if (frame.state === "thinking") {
        setStatus("她在想…");
      } else if (frame.state === "tts_failed") {
        setStatus("语音合成失败，文字还在");
      } else if (frame.state === "unclear") {
        setStatus(liveMode ? "在听…" : (frame.message || "没听清"));
      } else if (frame.state === "idle") {
        busy = false;
        if (!isSpeaking()) {
          setStatus(listeningStatus());
          callLive2d("releaseEmotion");
        }
        syncComposer();
      }
      return;
    }
    if (frame.type === "user_transcript") {
      if (frame.unclear) {
        return;
      }
      const text = typeof frame.text === "string" ? frame.text.trim() : "";
      if (text) {
        appendMessage("user", text);
      }
      return;
    }
    if (frame.type === "assistant_text") {
      const text = Array.isArray(frame.texts) ? frame.texts.join("\n") : "";
      if (text) {
        appendMessage("assistant", text);
      }
      if (frame.emotion) {
        callLive2d("setEmotion", frame.emotion);
      }
      return;
    }
    if (frame.type === "assistant_audio") {
      if (typeof frame.url === "string" && frame.url) {
        playAssistantAudio(frame.url);
      }
      return;
    }
    if (frame.type === "error") {
      const mapped = ERROR_TEXT[frame.code] || frame.message || "出错了";
      setStatus(mapped);
      appendMessage("assistant", mapped);
      busy = false;
      syncComposer();
    }
  });
}

sendBtn.addEventListener("click", sendText);
if (liveBtn) {
  liveBtn.addEventListener("click", toggleLive);
}
inputEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendText();
  }
});

fetch("/api/character")
  .then((res) => res.json())
  .then((data) => {
    if (data.name) {
      nameEl.textContent = data.name;
      document.title = data.name;
    }
  })
  .catch(() => {});

function bootDesktopShell() {
  if (!window.electronAPI) {
    return;
  }
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = "/assets/desktop.css";
  document.head.appendChild(link);
}

connect();
syncComposer();
bootDesktopShell();

if (window.live2d && typeof window.live2d.init === "function") {
  window.live2d.init().catch((error) => {
    console.error("Live2D init failed:", error);
  });
}
