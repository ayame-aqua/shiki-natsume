/**
 * 预加载脚本：只暴露窗口和勿扰，不把 Node 能力交给页面。
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  getWindowBounds: () => ipcRenderer.invoke('get-window-bounds'),
  setWindowBounds: (bounds) => ipcRenderer.invoke('set-window-bounds', bounds),
  getDndStatus: () => ipcRenderer.invoke('get-dnd-status'),
  toggleDnd: () => ipcRenderer.invoke('toggle-dnd'),
});
