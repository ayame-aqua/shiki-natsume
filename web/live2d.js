/**
 * Live2D 驱动（P4）
 * 口型吃播放链路里的 AnalyserNode，不自己 new AudioContext，也不碰 <audio>。
 * 包进 IIFE，避免 let analyser 等名字和 app.js 撞车导致整份脚本不执行。
 */
(() => {

const LIVE2D_MODELS_URL = "/live2d/model_dict.json";
const DEFAULT_MODEL_SCALE = 0.4;
const DEFAULT_MODEL_ANCHOR_Y = 0.8;
const DEFAULT_MOUTH_PARAM = "ParamMouthOpenY";
const MOUTH_SMOOTH = 0.35;
const MOUTH_GAIN = 2;
const MOUTH_SILENCE = 0.01;
const BLINK_INTERVAL_MS = 4000;
const BLINK_CLOSED_MS = 150;
const BREATH_PERIOD_MS = 3000;
const EMOTION_RELEASE_MS = 1500;
const EMOTION_MAP = {
  neutral: "idle",
  happy: "smile",
  sad: "sad",
  angry: "angry",
  shy: "blush",
};

let pixiApp = null;
let live2dModel = null;
let modelConfig = null;
let resizeObserver = null;
let originalModelUpdate = null;
let analyser = null;
let mouthSmoothValue = 0;
let currentEmotion = "neutral";
let emotionReleaseTimer = null;
let nextBlinkAt = 0;
let blinkUntil = 0;

function placeholderEl() {
  return document.getElementById("live2d-placeholder");
}

function canvasEl() {
  return document.getElementById("live2d-canvas");
}

function containerEl() {
  return document.getElementById("live2d-container");
}

function showPlaceholder(message) {
  const placeholder = placeholderEl();
  const canvas = canvasEl();
  if (placeholder) {
    placeholder.hidden = false;
    placeholder.textContent = message;
  }
  if (canvas) {
    canvas.hidden = true;
  }
}

function hidePlaceholder() {
  const placeholder = placeholderEl();
  const canvas = canvasEl();
  if (placeholder) {
    placeholder.hidden = true;
  }
  if (canvas) {
    canvas.hidden = false;
  }
}

function mappedEmotionName(emotion) {
  const fallback = EMOTION_MAP[emotion] || EMOTION_MAP.neutral;
  if (modelConfig && modelConfig.emotionMap && modelConfig.emotionMap[emotion]) {
    return modelConfig.emotionMap[emotion];
  }
  return fallback;
}

function mouthParamName() {
  if (modelConfig && typeof modelConfig.mouthParam === "string" && modelConfig.mouthParam) {
    return modelConfig.mouthParam;
  }
  return DEFAULT_MOUTH_PARAM;
}

function setParam(coreModel, name, value) {
  if (!coreModel) {
    return;
  }
  if (typeof coreModel.setParameterValueById === "function") {
    coreModel.setParameterValueById(name, value);
    return;
  }
  if (typeof coreModel.getParamIndex !== "function" || typeof coreModel.setParamFloat !== "function") {
    return;
  }
  const index = coreModel.getParamIndex(name);
  if (index >= 0) {
    coreModel.setParamFloat(index, value);
  }
}

function currentMouthLevel() {
  if (!analyser) {
    return 0;
  }
  const wave = new Uint8Array(analyser.fftSize);
  analyser.getByteTimeDomainData(wave);
  let energy = 0;
  for (let index = 0; index < wave.length; index += 1) {
    const centered = (wave[index] - 128) / 128;
    energy += centered * centered;
  }
  return Math.min(1, Math.sqrt(energy / wave.length) * MOUTH_GAIN);
}

function applyOverlayParameters() {
  if (!live2dModel || !live2dModel.internalModel) {
    return;
  }
  const coreModel = live2dModel.internalModel.coreModel;
  const now = Date.now();
  if (now >= nextBlinkAt) {
    blinkUntil = now + BLINK_CLOSED_MS;
    nextBlinkAt = now + BLINK_INTERVAL_MS;
  }
  const eyeOpen = now < blinkUntil ? 0 : 1;
  setParam(coreModel, "ParamEyeLOpen", eyeOpen);
  setParam(coreModel, "ParamEyeROpen", eyeOpen);
  const breath = Math.sin((now / BREATH_PERIOD_MS) * Math.PI * 2) * 0.5 + 0.5;
  setParam(coreModel, "ParamBreath", breath);
  const target = currentMouthLevel();
  mouthSmoothValue = mouthSmoothValue * (1 - MOUTH_SMOOTH) + target * MOUTH_SMOOTH;
  if (!analyser && mouthSmoothValue < MOUTH_SILENCE) {
    mouthSmoothValue = 0;
  }
  setParam(coreModel, mouthParamName(), mouthSmoothValue);
}

function hookModelUpdate() {
  if (!live2dModel || !live2dModel.internalModel || originalModelUpdate) {
    return;
  }
  const internal = live2dModel.internalModel;
  originalModelUpdate = internal.update.bind(internal);
  internal.update = (deltaSeconds) => {
    originalModelUpdate(deltaSeconds);
    applyOverlayParameters();
  };
}

function unhookModelUpdate() {
  if (live2dModel && live2dModel.internalModel && originalModelUpdate) {
    live2dModel.internalModel.update = originalModelUpdate;
  }
  originalModelUpdate = null;
}

function resizePixi() {
  const container = containerEl();
  if (!pixiApp || !live2dModel || !container) {
    return;
  }
  const width = container.clientWidth || 400;
  const height = container.clientHeight || 600;
  pixiApp.renderer.resize(width, height);
  live2dModel.x = width / 2;
  live2dModel.y = height * DEFAULT_MODEL_ANCHOR_Y;
}

function bindResize(container) {
  unbindResize();
  if (typeof ResizeObserver === "undefined") {
    window.addEventListener("resize", resizePixi);
    return;
  }
  resizeObserver = new ResizeObserver(() => {
    resizePixi();
  });
  resizeObserver.observe(container);
}

function unbindResize() {
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  window.removeEventListener("resize", resizePixi);
}

function hasMotion(name) {
  const definitions = live2dModel?.internalModel?.motionManager?.definitions;
  return Boolean(definitions && definitions[name] && definitions[name].length > 0);
}

function applyNamedLook(name) {
  let applied = false;
  if (typeof live2dModel.expression === "function") {
    try {
      const result = live2dModel.expression(name);
      applied = Boolean(result);
    } catch {
      applied = false;
    }
  }
  if (hasMotion(name)) {
    live2dModel.motion(name);
    applied = true;
  }
  return applied;
}

async function loadLive2DModel(config) {
  if (typeof Live2DCubismCore === "undefined") {
    throw new Error("cubism core missing");
  }
  if (typeof PIXI === "undefined" || typeof PIXI.live2d === "undefined") {
    throw new Error("pixi-live2d-display not loaded");
  }
  const container = containerEl();
  const canvas = canvasEl();
  if (!container || !canvas) {
    throw new Error("live2d canvas missing");
  }
  const width = container.clientWidth || 400;
  const height = container.clientHeight || 600;
  pixiApp = new PIXI.Application({
    view: canvas,
    width,
    height,
    backgroundAlpha: 0,
    autoStart: true,
  });
  live2dModel = await PIXI.live2d.Live2DModel.from(config.url);
  const scale = Number(config.kScale) || DEFAULT_MODEL_SCALE;
  live2dModel.scale.set(scale, scale);
  live2dModel.x = width / 2;
  live2dModel.y = height * DEFAULT_MODEL_ANCHOR_Y;
  pixiApp.stage.addChild(live2dModel);
  hookModelUpdate();
  bindResize(container);
  hidePlaceholder();
  nextBlinkAt = Date.now() + BLINK_INTERVAL_MS;
  console.info("Live2D model loaded:", config.name);
}

async function initLive2D() {
  const container = containerEl();
  if (!container) {
    console.warn("Live2D container not found");
    return false;
  }
  try {
    const response = await fetch(LIVE2D_MODELS_URL);
    const models = await response.json();
    if (!Array.isArray(models) || models.length === 0) {
      showPlaceholder("未配置模型");
      console.info("No Live2D model configured");
      return false;
    }
    modelConfig = models[0];
    await loadLive2DModel(modelConfig);
    return true;
  } catch (error) {
    console.error("Failed to initialize Live2D:", error);
    if (String(error.message || "").includes("cubism core missing")) {
      showPlaceholder("缺少 Cubism Core");
    } else {
      showPlaceholder("模型加载失败");
    }
    return false;
  }
}

function clearEmotionTimer() {
  if (emotionReleaseTimer !== null) {
    clearTimeout(emotionReleaseTimer);
    emotionReleaseTimer = null;
  }
}

function setEmotion(emotion) {
  if (!live2dModel || !modelConfig) {
    return;
  }
  clearEmotionTimer();
  const name = mappedEmotionName(emotion);
  const applied = applyNamedLook(name);
  if (applied) {
    currentEmotion = emotion;
    console.info("Emotion changed to:", emotion, "->", name);
    return;
  }
  console.warn("Emotion mapping missing:", name, "falling back to idle");
  applyNamedLook(EMOTION_MAP.neutral);
  currentEmotion = "neutral";
}

function releaseEmotion() {
  if (!live2dModel || currentEmotion === "neutral") {
    return;
  }
  clearEmotionTimer();
  emotionReleaseTimer = setTimeout(() => {
    emotionReleaseTimer = null;
    if (currentEmotion !== "neutral") {
      setEmotion("neutral");
    }
  }, EMOTION_RELEASE_MS);
}

function startLipSync(analyserNode) {
  if (!live2dModel || !analyserNode) {
    return;
  }
  analyser = analyserNode;
  mouthSmoothValue = 0;
}

function stopLipSync() {
  analyser = null;
  mouthSmoothValue = 0;
  if (live2dModel && live2dModel.internalModel) {
    setParam(live2dModel.internalModel.coreModel, mouthParamName(), 0);
  }
}

function cleanupLive2D() {
  clearEmotionTimer();
  stopLipSync();
  unbindResize();
  unhookModelUpdate();
  if (pixiApp) {
    pixiApp.destroy(true, { children: true });
    pixiApp = null;
  }
  live2dModel = null;
  modelConfig = null;
  currentEmotion = "neutral";
}

window.live2d = {
  init: initLive2D,
  setEmotion,
  releaseEmotion,
  startLipSync,
  stopLipSync,
  cleanup: cleanupLive2D,
};
})();
