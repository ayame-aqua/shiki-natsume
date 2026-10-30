/**
 * 预加载脚本：提供安全的 IPC 桥接
 * P5 切片 2：添加勿扰模式 API
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  getWindowBounds: () => ipcRenderer.invoke('get-window-bounds'),
  setWindowBounds: (bounds) => ipcRenderer.invoke('set-window-bounds', bounds),
  getDndStatus: () => ipcRenderer.invoke('get-dnd-status'),
  toggleDnd: () => ipcRenderer.invoke('toggle-dnd'),
  onProactiveMessage: (callback) => {
    ipcRenderer.on('proactive-message', (event, data) => callback(data));
  }
});
