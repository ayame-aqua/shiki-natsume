/**
 * 四季夏目桌宠主进程
 * P5 第一切片：透明、置顶、可拖拽窗口，加载现有 web UI
 */

const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const Store = require('electron-store');

const store = new Store({
  defaults: {
    windowBounds: {
      x: undefined,
      y: undefined,
      width: 400,
      height: 600
    }
  }
});

const FASTAPI_URL = 'http://127.0.0.1:8787';

let mainWindow = null;

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
  });

  mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
    console.error('Failed to load:', errorDescription);
    console.log('确保 FastAPI 已在 127.0.0.1:8787 启动');
  });

  mainWindow.webContents.openDevTools({ mode: 'detach' });
}

app.whenReady().then(() => {
  createWindow();

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
