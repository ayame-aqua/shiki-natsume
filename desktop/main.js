/**
 * 四季夏目桌宠主进程
 * P5 切片 2：主动搭话、勿扰模式
 */

const { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage } = require('electron');
const path = require('path');
const Store = require('electron-store');

const store = new Store({
  defaults: {
    windowBounds: {
      x: undefined,
      y: undefined,
      width: 400,
      height: 600
    },
    doNotDisturb: false
  }
});

const FASTAPI_URL = 'http://127.0.0.1:8787';
const PROACTIVE_CHECK_INTERVAL_MS = 60000; // 每 60 秒检查一次

let mainWindow = null;
let tray = null;
let proactiveTimer = null;

function createWindow() {
  const bounds = store.get('windowBounds');
  
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
      webSecurity: true
    }
  });

  mainWindow.setBackgroundColor('#00000000');
  
  mainWindow.loadURL(FASTAPI_URL);

  mainWindow.webContents.on('did-finish-load', () => {
    mainWindow.webContents.insertCSS(`
      @import url('/assets/desktop.css');
    `).catch(err => {
      console.warn('Failed to inject desktop.css:', err);
    });
  });

  mainWindow.on('close', () => {
    const currentBounds = mainWindow.getBounds();
    store.set('windowBounds', currentBounds);
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
    if (proactiveTimer) {
      clearInterval(proactiveTimer);
      proactiveTimer = null;
    }
  });

  mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
    console.error('Failed to load:', errorDescription);
    console.log('确保 FastAPI 已在 127.0.0.1:8787 启动');
  });

  // P5 切片 2：开发时打开 DevTools
  if (process.env.NODE_ENV !== 'production') {
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  }

  // 启动主动搭话定时器
  startProactiveTimer();
}

function createTray() {
  // 创建一个简单的托盘图标（16x16 透明图标）
  const iconData = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAAAdgAAAHYBTnsmCAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAABzSURBVDiNY2AYBaNgFIyCUTAKRgEjAwPDfyYG4gELKRoYGBj+k2EG2S5gYGAgahywDQNsDQwMDKRrYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgGNoaRsEoAAYAAN8gAhHbeqKMAAAAAElFTkSuQmCC',
    'base64'
  );
  const icon = nativeImage.createFromBuffer(iconData);
  
  tray = new Tray(icon);
  updateTrayMenu();
  
  tray.setToolTip('四季夏目');
  tray.on('click', () => {
    if (mainWindow) {
      mainWindow.show();
    }
  });
}

function updateTrayMenu() {
  const dnd = store.get('doNotDisturb', false);
  const contextMenu = Menu.buildFromTemplate([
    {
      label: '显示窗口',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
        }
      }
    },
    { type: 'separator' },
    {
      label: dnd ? '✓ 勿扰模式' : '勿扰模式',
      type: 'checkbox',
      checked: dnd,
      click: () => {
        toggleDoNotDisturb();
      }
    },
    { type: 'separator' },
    {
      label: '退出',
      click: () => {
        app.quit();
      }
    }
  ]);
  
  tray.setContextMenu(contextMenu);
}

async function toggleDoNotDisturb() {
  const current = store.get('doNotDisturb', false);
  const newValue = !current;
  store.set('doNotDisturb', newValue);
  
  // 通知 FastAPI
  try {
    const fetch = require('node-fetch');
    await fetch(`${FASTAPI_URL}/api/proactive/dnd`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: newValue })
    });
  } catch (err) {
    console.error('Failed to sync DND state:', err);
  }
  
  updateTrayMenu();
}

async function checkProactive() {
  if (!mainWindow) {
    return;
  }

  const dnd = store.get('doNotDisturb', false);
  if (dnd) {
    return;
  }

  try {
    const fetch = require('node-fetch');
    const response = await fetch(`${FASTAPI_URL}/api/proactive/trigger`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    
    if (!response.ok) {
      return;
    }

    const result = await response.json();
    if (result.triggered) {
      console.log('Proactive talk triggered:', result.texts);
      
      // 通知渲染进程显示主动消息
      if (mainWindow && mainWindow.webContents) {
        mainWindow.webContents.send('proactive-message', result);
      }
    }
  } catch (err) {
    // 静默失败，避免日志刷屏
  }
}

function startProactiveTimer() {
  if (proactiveTimer) {
    clearInterval(proactiveTimer);
  }
  
  proactiveTimer = setInterval(() => {
    checkProactive();
  }, PROACTIVE_CHECK_INTERVAL_MS);
}

app.whenReady().then(() => {
  createWindow();
  createTray();

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
  if (proactiveTimer) {
    clearInterval(proactiveTimer);
    proactiveTimer = null;
  }
});

ipcMain.handle('get-window-bounds', () => {
  if (mainWindow) {
    return mainWindow.getBounds();
  }
  return null;
});

ipcMain.handle('set-window-bounds', (event, bounds) => {
  if (mainWindow) {
    mainWindow.setBounds(bounds);
    store.set('windowBounds', bounds);
  }
});

ipcMain.handle('get-dnd-status', () => {
  return store.get('doNotDisturb', false);
});

ipcMain.handle('toggle-dnd', async () => {
  await toggleDoNotDisturb();
  return store.get('doNotDisturb', false);
});
