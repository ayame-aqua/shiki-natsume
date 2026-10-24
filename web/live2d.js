/**
 * Live2D 驱动（P4）
 * 技术栈：pixi-live2d-display
 */

const LIVE2D_MODELS_URL = "/live2d/model_dict.json";
const EMOTION_MAP = {
  neutral: "idle",
  happy: "smile",
  sad: "sad",
  angry: "angry",
  shy: "blush",
};

const IDLE_BLINK_INTERVAL_MS = 4000;
const IDLE_BREATH_INTERVAL_MS = 3000;
const EMOTION_RESET_DELAY_MS = 2000;

let pixiApp = null;
let live2dModel = null;
let currentEmotion = "neutral";
let emotionResetTimer = null;
let idleBlinkTimer = null;
let idleBreathTimer = null;
let audioContext = null;
let analyser = null;
let mouthSmoothValue = 0;
let animationFrameId = null;
let modelConfig = null;

/**
 * 初始化 Live2D 系统
 */
async function initLive2D() {
  const container = document.getElementById("live2d-container");
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
    startIdleAnimations();
    return true;
  } catch (error) {
    console.error("Failed to initialize Live2D:", error);
    showPlaceholder("模型加载失败");
    return false;
  }
}

/**
 * 显示未配置占位符
 */
function showPlaceholder(message) {
  const container = document.getElementById("live2d-container");
  if (!container) {
    return;
  }
  container.innerHTML = `<div class="live2d-placeholder">${message}</div>`;
}

/**
 * 加载 Live2D 模型
 */
async function loadLive2DModel(config) {
  if (typeof PIXI === "undefined" || typeof PIXI.live2d === "undefined") {
    throw new Error("pixi-live2d-display not loaded");
  }

  const container = document.getElementById("live2d-container");
  const width = container.clientWidth || 400;
  const height = container.clientHeight || 600;

  pixiApp = new PIXI.Application({
    view: document.getElementById("live2d-canvas"),
    width,
    height,
    transparent: true,
    autoStart: true,
  });

  live2dModel = await PIXI.live2d.Live2DModel.from(config.url);
  
  const scale = config.kScale || 0.4;
  live2dModel.scale.set(scale, scale);
  live2dModel.x = width / 2;
  live2dModel.y = height * 0.8;

  pixiApp.stage.addChild(live2dModel);
  console.info("Live2D model loaded:", config.name);
}

/**
 * 切换表情
 */
function setEmotion(emotion) {
  if (!live2dModel || !modelConfig) {
    return;
  }

  if (emotionResetTimer !== null) {
    clearTimeout(emotionResetTimer);
    emotionResetTimer = null;
  }

  const motionName = EMOTION_MAP[emotion] || "idle";
  const mappedMotion = (modelConfig.emotionMap && modelConfig.emotionMap[emotion]) || motionName;

  try {
    if (live2dModel.internalModel && live2dModel.internalModel.motionManager) {
      const motionGroup = live2dModel.internalModel.motionManager.definitions[mappedMotion];
      if (motionGroup && motionGroup.length > 0) {
        live2dModel.motion(mappedMotion);
        currentEmotion = emotion;
        console.info("Emotion changed to:", emotion, "->", mappedMotion);
      } else {
        console.warn("Emotion motion not found:", mappedMotion, "falling back to idle");
        live2dModel.motion("idle");
        currentEmotion = "neutral";
      }
    }
  } catch (error) {
    console.error("Failed to set emotion:", error);
  }

  emotionResetTimer = setTimeout(() => {
    if (currentEmotion !== "neutral") {
      setEmotion("neutral");
    }
  }, EMOTION_RESET_DELAY_MS);
}

/**
 * 开始 idle 动画（眨眼和呼吸）
 */
function startIdleAnimations() {
  if (!live2dModel) {
    return;
  }

  idleBlinkTimer = setInterval(() => {
    if (live2dModel && live2dModel.internalModel) {
      try {
        const blinkParam = live2dModel.internalModel.coreModel.getParamIndex("ParamEyeLOpen");
        const blinkParam2 = live2dModel.internalModel.coreModel.getParamIndex("ParamEyeROpen");
        if (blinkParam >= 0) {
          live2dModel.internalModel.coreModel.setParamFloat(blinkParam, 0);
          setTimeout(() => {
            if (live2dModel && live2dModel.internalModel) {
              live2dModel.internalModel.coreModel.setParamFloat(blinkParam, 1);
            }
          }, 150);
        }
        if (blinkParam2 >= 0) {
          live2dModel.internalModel.coreModel.setParamFloat(blinkParam2, 0);
          setTimeout(() => {
            if (live2dModel && live2dModel.internalModel) {
              live2dModel.internalModel.coreModel.setParamFloat(blinkParam2, 1);
            }
          }, 150);
        }
      } catch (error) {
        console.error("Blink animation error:", error);
      }
    }
  }, IDLE_BLINK_INTERVAL_MS);

  idleBreathTimer = setInterval(() => {
    if (live2dModel && live2dModel.internalModel) {
      try {
        const breathParam = live2dModel.internalModel.coreModel.getParamIndex("ParamBreath");
        if (breathParam >= 0) {
          const value = Math.sin(Date.now() / 1000) * 0.5 + 0.5;
          live2dModel.internalModel.coreModel.setParamFloat(breathParam, value);
        }
      } catch (error) {
        console.error("Breath animation error:", error);
      }
    }
  }, IDLE_BREATH_INTERVAL_MS);
}

/**
 * 停止 idle 动画
 */
function stopIdleAnimations() {
  if (idleBlinkTimer !== null) {
    clearInterval(idleBlinkTimer);
    idleBlinkTimer = null;
  }
  if (idleBreathTimer !== null) {
    clearInterval(idleBreathTimer);
    idleBreathTimer = null;
  }
}

/**
 * 开始口型同步
 */
function startLipSync(audioElement) {
  if (!live2dModel || !audioElement) {
    return;
  }

  if (!audioContext) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
      console.warn("AudioContext not supported");
      return;
    }
    audioContext = new AudioContextClass();
  }

  if (audioContext.state === "suspended") {
    audioContext.resume();
  }

  try {
    const source = audioContext.createMediaElementSource(audioElement);
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);
    analyser.connect(audioContext.destination);

    mouthSmoothValue = 0;
    startMouthAnimation();

    audioElement.addEventListener("ended", () => {
      stopLipSync();
    }, { once: true });

    audioElement.addEventListener("pause", () => {
      stopLipSync();
    }, { once: true });
  } catch (error) {
    console.error("Failed to start lip sync:", error);
    try {
      const source = audioContext.createMediaElementSource(audioElement);
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyser.connect(audioContext.destination);
      
      mouthSmoothValue = 0;
      startMouthAnimation();

      audioElement.addEventListener("ended", () => {
        stopLipSync();
      }, { once: true });
    } catch (retryError) {
      console.error("Retry failed:", retryError);
    }
  }
}

/**
 * 停止口型同步
 */
function stopLipSync() {
  if (animationFrameId !== null) {
    cancelAnimationFrame(animationFrameId);
    animationFrameId = null;
  }

  if (live2dModel && live2dModel.internalModel) {
    try {
      const mouthParam = live2dModel.internalModel.coreModel.getParamIndex("ParamMouthOpenY");
      if (mouthParam >= 0) {
        live2dModel.internalModel.coreModel.setParamFloat(mouthParam, 0);
      }
    } catch (error) {
      console.error("Failed to close mouth:", error);
    }
  }

  analyser = null;
  mouthSmoothValue = 0;
}

/**
 * 口型动画循环
 */
function startMouthAnimation() {
  if (!live2dModel || !analyser) {
    return;
  }

  const updateMouth = () => {
    if (!analyser || !live2dModel || !live2dModel.internalModel) {
      return;
    }

    try {
      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      analyser.getByteFrequencyData(dataArray);

      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
      }
      const average = sum / dataArray.length / 255;

      const smoothFactor = 0.35;
      mouthSmoothValue = mouthSmoothValue * (1 - smoothFactor) + average * smoothFactor;

      const mouthParam = live2dModel.internalModel.coreModel.getParamIndex("ParamMouthOpenY");
      if (mouthParam >= 0) {
        const mouthValue = Math.min(1, mouthSmoothValue * 2);
        live2dModel.internalModel.coreModel.setParamFloat(mouthParam, mouthValue);
      }
    } catch (error) {
      console.error("Mouth animation error:", error);
    }

    animationFrameId = requestAnimationFrame(updateMouth);
  };

  updateMouth();
}

/**
 * 清理资源
 */
function cleanupLive2D() {
  stopIdleAnimations();
  stopLipSync();
  
  if (emotionResetTimer !== null) {
    clearTimeout(emotionResetTimer);
    emotionResetTimer = null;
  }

  if (pixiApp) {
    pixiApp.destroy(true, true);
    pixiApp = null;
  }

  live2dModel = null;
  audioContext = null;
  analyser = null;
  modelConfig = null;
}

window.live2d = {
  init: initLive2D,
  setEmotion,
  startLipSync,
  stopLipSync,
  cleanup: cleanupLive2D,
};
