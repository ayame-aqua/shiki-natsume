/**
 * 桌宠窗位置校正。不依赖 Electron，方便单测。
 * 旧配置若把窗拖出工作区（例如 x 为负），下次启动必须回到看得见的地方。
 */

const DEFAULT_WINDOW_WIDTH = 920;
const DEFAULT_WINDOW_HEIGHT = 640;

function isFiniteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function clampSize(value, fallback, maxSize) {
  const size = isFiniteNumber(value) && value > 0 ? value : fallback;
  return Math.min(Math.max(Math.round(size), 1), Math.max(1, maxSize));
}

function pointInArea(x, y, area) {
  return x >= area.x && y >= area.y && x < area.x + area.width && y < area.y + area.height;
}

function pickWorkArea(stored, workAreas, widthHint, heightHint) {
  if (workAreas.length === 0) {
    return { x: 0, y: 0, width: 1920, height: 1080 };
  }
  if (!isFiniteNumber(stored.x) || !isFiniteNumber(stored.y)) {
    return workAreas[0];
  }
  const centerX = stored.x + widthHint / 2;
  const centerY = stored.y + heightHint / 2;
  const hit = workAreas.find((area) => pointInArea(centerX, centerY, area));
  if (hit) {
    return hit;
  }
  let nearest = workAreas[0];
  let bestDist = Number.POSITIVE_INFINITY;
  for (const area of workAreas) {
    const midX = area.x + area.width / 2;
    const midY = area.y + area.height / 2;
    const dist = (centerX - midX) ** 2 + (centerY - midY) ** 2;
    if (dist < bestDist) {
      bestDist = dist;
      nearest = area;
    }
  }
  return nearest;
}

function clampWindowBounds(stored, workAreas, defaults = {}) {
  const defaultWidth = defaults.width || DEFAULT_WINDOW_WIDTH;
  const defaultHeight = defaults.height || DEFAULT_WINDOW_HEIGHT;
  const raw = stored && typeof stored === "object" ? stored : {};
  const widthHint = isFiniteNumber(raw.width) ? raw.width : defaultWidth;
  const heightHint = isFiniteNumber(raw.height) ? raw.height : defaultHeight;
  const area = pickWorkArea(raw, workAreas, widthHint, heightHint);
  const width = clampSize(raw.width, defaultWidth, area.width);
  const height = clampSize(raw.height, defaultHeight, area.height);

  let x;
  let y;
  if (isFiniteNumber(raw.x) && isFiniteNumber(raw.y)) {
    x = raw.x;
    y = raw.y;
  } else {
    x = area.x + Math.max(0, Math.floor((area.width - width) / 2));
    y = area.y + Math.max(0, Math.floor((area.height - height) / 2));
  }

  const minX = area.x;
  const minY = area.y;
  const maxX = area.x + area.width - width;
  const maxY = area.y + area.height - height;
  x = Math.min(Math.max(Math.round(x), minX), Math.max(minX, maxX));
  y = Math.min(Math.max(Math.round(y), minY), Math.max(minY, maxY));
  return { x, y, width, height };
}

module.exports = {
  DEFAULT_WINDOW_WIDTH,
  DEFAULT_WINDOW_HEIGHT,
  clampWindowBounds,
};
