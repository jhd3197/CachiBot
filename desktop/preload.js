const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  isDesktop: true,
  appVersion: (() => {
    const flag = process.argv.find(a => a.startsWith('--app-version='));
    return flag ? flag.split('=')[1] : 'unknown';
  })(),
  versions: {
    electron: process.versions.electron,
    node: process.versions.node,
    chrome: process.versions.chrome,
  },
  // Window controls for custom title bar
  windowMinimize: () => ipcRenderer.send('window:minimize'),
  windowMaximize: () => ipcRenderer.send('window:maximize'),
  windowClose: () => ipcRenderer.send('window:close'),
  windowIsMaximized: () => ipcRenderer.invoke('window:isMaximized'),
  onMaximizedChange: (callback) => {
    const handler = (_event, maximized) => callback(maximized);
    ipcRenderer.on('window:maximized', handler);
    return () => ipcRenderer.removeListener('window:maximized', handler);
  },
  // Update management
  checkForUpdate: () => ipcRenderer.invoke('update:check'),
  downloadUpdate: () => ipcRenderer.invoke('update:download'),
  installUpdate: () => ipcRenderer.send('update:install'),
  onUpdateAvailable: (callback) => {
    const handler = (_event, info) => callback(info);
    ipcRenderer.on('update:available', handler);
    return () => ipcRenderer.removeListener('update:available', handler);
  },
  onUpdateProgress: (callback) => {
    const handler = (_event, progress) => callback(progress);
    ipcRenderer.on('update:download-progress', handler);
    return () => ipcRenderer.removeListener('update:download-progress', handler);
  },
  onUpdateError: (callback) => {
    const handler = (_event, error) => callback(error);
    ipcRenderer.on('update:error', handler);
    return () => ipcRenderer.removeListener('update:error', handler);
  },
  // Cache management
  clearCache: () => ipcRenderer.invoke('cache:clear'),
  // Settings
  getSetting: (key, defaultValue) => ipcRenderer.invoke('settings:get', key, defaultValue),
  setSetting: (key, value) => ipcRenderer.invoke('settings:set', key, value),
});
