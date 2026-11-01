/**
 * 四季夏目桌宠主进程。
 * 窗口只加载本地 FastAPI；主动搭话走 HTTP，气泡和语音仍由网页 WebSocket 收。
 */

const { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage, screen } = require('electron');
const path = require('path');
const Store = require('electron-store');
const { DEFAULT_WINDOW_HEIGHT, DEFAULT_WINDOW_WIDTH, clampWindowBounds } = require('./window_bounds');

const FASTAPI_URL = 'http://127.0.0.1:8787';
const PROACTIVE_CHECK_INTERVAL_MS = 60000;
const TRAY_PNG_BASE64 =
  'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAAAdgAAAHYBTnsmCAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAABzSURBVDiNY2AYBaNgFIyCUTAKRgEjAwPDfyYG4gELKRoYGBj+k2EG2S5gYGAgahywDQNsDQwMDKRrYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgGNoaRsEoAAYAAN8gAhHbeqKMAAAAAElFTkSuQmCC';

const store = new Store({
  defaults: {
    windowBounds: {
      width: DEFAULT_WINDOW_WIDTH,
      height: DEFAULT_WINDOW_HEIGHT,
    },
    doNotDisturb: false,
  },
});

let mainWindow = null;
let tray = null;
let proactiveTimer = null;

function listWorkAreas() {
  return screen.getAllDisplays().map((display) => display.workArea);
}

function resolveWindowBounds(stored) {
  const bounds = clampWindowBounds(stored, listWorkAreas(), {
    width: DEFAULT_WINDOW_WIDTH,
    height: DEFAULT_WINDOW_HEIGHT,
  });
  store.set('windowBounds', bounds);
  return bounds;
}

function createWindow() {
  const bounds = resolveWindowBounds(store.get('windowBounds'));
  mainWindow = new BrowserWindow({
    x: bounds.x,
    y: bounds.y,
    width: bounds.width,
    height: bounds.height,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: false,
    resizable: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true,
    },
  });

  mainWindow.setBackgroundColor('#00000000');
  mainWindow.loadURL(FASTAPI_URL);

  mainWindow.on('close', () => {
    if (mainWindow) {
      resolveWindowBounds(mainWindow.getBounds());
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
    stopProactiveTimer();
  });

  mainWindow.webContents.on('did-fail-load', (_event, _errorCode, errorDescription) => {
    console.error('Failed to load FastAPI:', errorDescription);
    console.error('先启动 python -m src.main，确认 http://127.0.0.1:8787 可访问');
  });

  if (process.env.NODE_ENV !== 'production') {
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  }

  startProactiveTimer();
}

function createTray() {
  const icon = nativeImage.createFromBuffer(Buffer.from(TRAY_PNG_BASE64, 'base64'));
  tray = new Tray(icon);
  tray.setToolTip('四季夏目');
  tray.on('click', showMainWindow);
  updateTrayMenu();
}

function showMainWindow() {
  if (mainWindow) {
    mainWindow.show();
  }
}

function updateTrayMenu() {
  if (!tray) {
    return;
  }
  const dnd = Boolean(store.get('doNotDisturb', false));
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: '显示窗口', click: showMainWindow },
      { type: 'separator' },
      {
        label: '勿扰模式',
        type: 'checkbox',
        checked: dnd,
        click: () => {
          void toggleDoNotDisturb();
        },
      },
      { type: 'separator' },
      { label: '退出', click: () => app.quit() },
    ]),
  );
}

async function postJson(pathname, body) {
  const response = await fetch(`${FASTAPI_URL}${pathname}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`${pathname} HTTP ${response.status}`);
  }
  return response.json();
}

async function syncDndToBackend() {
  const enabled = Boolean(store.get('doNotDisturb', false));
  try {
    await postJson('/api/proactive/dnd', { enabled });
  } catch (error) {
    console.error('Failed to sync DND state:', error);
  }
}

async function toggleDoNotDisturb() {
  store.set('doNotDisturb', !store.get('doNotDisturb', false));
  updateTrayMenu();
  await syncDndToBackend();
}

async function checkProactive() {
  if (!mainWindow || store.get('doNotDisturb', false)) {
    return;
  }
  try {
    const result = await postJson('/api/proactive/trigger', {});
    if (result.triggered) {
      console.log('Proactive talk triggered:', result.texts);
    }
  } catch (error) {
    console.error('Proactive check failed:', error);
  }
}

function startProactiveTimer() {
  stopProactiveTimer();
  proactiveTimer = setInterval(() => {
    void checkProactive();
  }, PROACTIVE_CHECK_INTERVAL_MS);
}

function stopProactiveTimer() {
  if (proactiveTimer) {
    clearInterval(proactiveTimer);
    proactiveTimer = null;
  }
}

app.whenReady().then(() => {
  createWindow();
  createTray();
  void syncDndToBackend();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  stopProactiveTimer();
});

ipcMain.handle('get-window-bounds', () => (mainWindow ? mainWindow.getBounds() : null));

ipcMain.handle('set-window-bounds', (_event, bounds) => {
  if (!mainWindow) {
    return;
  }
  const next = resolveWindowBounds(bounds);
  mainWindow.setBounds(next);
});

ipcMain.handle('get-dnd-status', () => Boolean(store.get('doNotDisturb', false)));

ipcMain.handle('toggle-dnd', async () => {
  await toggleDoNotDisturb();
  return Boolean(store.get('doNotDisturb', false));
});
