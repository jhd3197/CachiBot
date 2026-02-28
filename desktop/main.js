const { app, BrowserWindow, shell, dialog, ipcMain, session, Tray, Menu, nativeImage } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn, execFile } = require('child_process');
const net = require('net');

// electron-updater is optional — gracefully degrade if missing
let autoUpdater = null;
try {
  autoUpdater = require('electron-updater').autoUpdater;
} catch {
  console.log('[electron] electron-updater not available, auto-updates disabled');
}

let mainWindow = null;
let backendProcess = null;
let tray = null;
let backendStderr = ''; // Capture stderr for error reporting

const isDev = !app.isPackaged;
const BACKEND_PORT = 5870;
const BACKEND_HOST = '127.0.0.1';
const BACKEND_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`;

// In dev mode, load from Vite dev server for hot reload when available
const DEV_FRONTEND_URL = process.env.ELECTRON_DEV_URL || null;

function isAllowedOrigin(url) {
  try {
    const parsed = new URL(url);
    if (parsed.hostname === BACKEND_HOST && parsed.port === String(BACKEND_PORT)) return true;
    if (isDev && DEV_FRONTEND_URL) {
      const devParsed = new URL(DEV_FRONTEND_URL);
      if (parsed.hostname === devParsed.hostname && parsed.port === devParsed.port) return true;
    }
    return false;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Backend lifecycle
// ---------------------------------------------------------------------------

function getBackendCommand() {
  if (isDev) {
    // Dev mode: use the installed cachibot CLI directly
    return { cmd: 'cachibot', args: ['server', '--port', String(BACKEND_PORT)] };
  }
  // Production: use the PyInstaller-bundled binary
  const ext = process.platform === 'win32' ? '.exe' : '';
  const binary = path.join(process.resourcesPath, 'backend', `cachibot-server${ext}`);
  return { cmd: binary, args: ['--port', String(BACKEND_PORT)] };
}

function startBackend() {
  const { cmd, args } = getBackendCommand();
  console.log('[electron] Starting backend:', cmd, args.join(' '));

  backendProcess = spawn(cmd, args, {
    env: {
      ...process.env,
      CACHIBOT_DESKTOP: 'true',
      // Use the user's home directory as default workspace
      CACHIBOT_WORKSPACE: app.getPath('home'),
    },
    stdio: ['ignore', 'pipe', 'pipe'],
    shell: isDev, // Use shell in dev to resolve PATH
    detached: process.platform !== 'win32',
  });

  backendProcess.stdout.on('data', (d) => console.log('[backend]', d.toString().trim()));
  backendProcess.stderr.on('data', (d) => {
    const text = d.toString().trim();
    console.error('[backend]', text);
    // Keep last 2KB of stderr for error reporting
    backendStderr = (backendStderr + '\n' + text).slice(-2048);
  });

  backendProcess.on('error', (err) => {
    console.error('[electron] Failed to start backend:', err.message);
    dialog.showErrorBox(
      'Backend Error',
      isDev
        ? `Could not start "cachibot server". Make sure cachibot is installed:\n  pip install -e .\n\nError: ${err.message}`
        : `The CachiBot backend failed to start.\n\nError: ${err.message}`
    );
  });

  backendProcess.on('exit', (code, signal) => {
    console.log('[electron] Backend exited with code', code, 'signal', signal);
    backendProcess = null;
  });
}

function stopBackend() {
  if (!backendProcess) return;
  console.log('[electron] Stopping backend...');
  const pid = backendProcess.pid;
  if (process.platform === 'win32' && pid) {
    // On Windows, kill the entire process tree so child processes (uvicorn
    // workers, etc.) don't linger after the app closes.
    try {
      execFile('taskkill', ['/pid', String(pid), '/T', '/F'], (err) => {
        if (err) console.error('[electron] taskkill error:', err.message);
      });
    } catch (err) {
      console.error('[electron] taskkill spawn error:', err.message);
      backendProcess.kill();
    }
  } else {
    // Kill the entire process group (backend + uvicorn workers)
    try {
      process.kill(-backendProcess.pid);
    } catch (err) {
      console.error('[electron] process group kill failed:', err.message);
      backendProcess.kill();
    }
  }
  backendProcess = null;

  // Clean up PID file after stopping backend
  try { fs.unlinkSync(PID_FILE); } catch {}
}

// ---------------------------------------------------------------------------
// Wait for the backend HTTP port to be ready
// ---------------------------------------------------------------------------

function waitForPort(port, retries = 60, delay = 500) {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    let backendExited = false;
    let exitCode = null;

    // Listen for early backend crash so we can fail fast
    const onExit = (code) => {
      backendExited = true;
      exitCode = code;
    };
    if (backendProcess) backendProcess.once('exit', onExit);

    const tryConnect = () => {
      // If the backend already exited, fail immediately instead of waiting 30s
      if (backendExited) {
        if (backendProcess) backendProcess.removeListener('exit', onExit);
        return reject(new Error(`Backend process exited with code ${exitCode} before becoming ready`));
      }

      const sock = new net.Socket();
      sock.setTimeout(delay);
      sock.once('connect', () => {
        sock.destroy();
        if (backendProcess) backendProcess.removeListener('exit', onExit);
        resolve();
      });
      sock.once('error', () => {
        sock.destroy();
        if (++attempts >= retries) {
          if (backendProcess) backendProcess.removeListener('exit', onExit);
          return reject(new Error(`Port ${port} not ready after ${retries} attempts`));
        }
        setTimeout(tryConnect, delay);
      });
      sock.once('timeout', () => {
        sock.destroy();
        if (++attempts >= retries) {
          if (backendProcess) backendProcess.removeListener('exit', onExit);
          return reject(new Error(`Port ${port} timed out`));
        }
        setTimeout(tryConnect, delay);
      });
      sock.connect(port, BACKEND_HOST);
    };
    tryConnect();
  });
}

function isPortInUse(port) {
  return new Promise((resolve) => {
    const sock = new net.Socket();
    sock.setTimeout(500);
    sock.once('connect', () => { sock.destroy(); resolve(true); });
    sock.once('error', () => { sock.destroy(); resolve(false); });
    sock.once('timeout', () => { sock.destroy(); resolve(false); });
    sock.connect(port, BACKEND_HOST);
  });
}

const PID_FILE = path.join(require('os').homedir(), '.cachibot', 'server.pid');

async function killStalePidFile() {
  let data;
  try {
    data = JSON.parse(fs.readFileSync(PID_FILE, 'utf8'));
  } catch {
    return; // No PID file or invalid JSON
  }

  const pid = data.pid;
  if (!pid) return;

  console.log(`[electron] Found stale PID file (PID ${pid}), killing...`);

  if (process.platform === 'win32') {
    try {
      await new Promise((resolve) => {
        execFile('taskkill', ['/PID', String(pid), '/T', '/F'], (err) => {
          if (err) console.warn('[electron] taskkill stale PID error:', err.message);
          resolve();
        });
      });
    } catch {}
  } else {
    try { process.kill(pid, 'SIGKILL'); } catch {}
  }

  try { fs.unlinkSync(PID_FILE); } catch {}
}

function killProcessOnPort(port) {
  return new Promise((resolve) => {
    if (process.platform === 'win32') {
      // Find PID listening on the port, then taskkill it
      execFile('cmd', ['/c', `for /f "tokens=5" %a in ('netstat -aon ^| findstr :${port} ^| findstr LISTENING') do taskkill /F /PID %a`], { shell: true }, (err) => {
        if (err) console.warn('[electron] Failed to kill process on port:', err.message);
        resolve();
      });
    } else {
      // Unix: use fuser or lsof
      execFile('sh', ['-c', `lsof -ti :${port} | xargs kill -9 2>/dev/null || fuser -k ${port}/tcp 2>/dev/null`], (err) => {
        if (err) console.warn('[electron] Failed to kill process on port:', err.message);
        resolve();
      });
    }
  });
}

// ---------------------------------------------------------------------------
// Window creation
// ---------------------------------------------------------------------------

function createWindow(splash = null) {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    title: 'CachiBot',
    icon: path.join(__dirname, '..', 'assets', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      additionalArguments: [`--app-version=${app.getVersion()}`],
    },
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'hidden',
    titleBarOverlay: false,
    frame: process.platform === 'darwin',
    backgroundColor: '#ffffff',
    show: false,
  });

  // Open external links in the system browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (isAllowedOrigin(url)) return { action: 'allow' };
    if (url.startsWith('http')) shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (!isAllowedOrigin(url)) {
      event.preventDefault();
      if (url.startsWith('http')) shell.openExternal(url);
    }
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    if (splash && !splash.isDestroyed()) splash.close();
  });

  // Forward maximize state changes to the renderer for title bar icon updates
  mainWindow.on('maximize', () => mainWindow.webContents.send('window:maximized', true));
  mainWindow.on('unmaximize', () => mainWindow.webContents.send('window:maximized', false));

  // In dev mode, load from Vite dev server for hot reload; otherwise load from backend
  const loadURL = (isDev && DEV_FRONTEND_URL) ? DEV_FRONTEND_URL : BACKEND_URL;
  mainWindow.loadURL(loadURL);

  if (isDev) {
    mainWindow.webContents.openDevTools();
  }
}

// ---------------------------------------------------------------------------
// Splash / loading screen while backend starts
// ---------------------------------------------------------------------------

function createSplashWindow() {
  const splash = new BrowserWindow({
    width: 420,
    height: 340,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    webPreferences: { nodeIntegration: false, contextIsolation: true },
  });

  const version = require('./package.json').version;

  splash.loadFile(path.join(__dirname, 'splash.html'), {
    query: { version },
  });

  return splash;
}

function splashStatus(splash, text) {
  if (splash && !splash.isDestroyed()) {
    const escaped = text.replace(/'/g, "\\'");
    splash.webContents.executeJavaScript(`window.updateStatus('${escaped}')`).catch(() => {});
  }
}

// ---------------------------------------------------------------------------
// System tray
// ---------------------------------------------------------------------------

function createTray() {
  const iconFile = process.platform === 'win32' ? 'icon.ico' : 'icon.png';
  const iconPath = isDev
    ? path.join(__dirname, '..', 'assets', iconFile)
    : path.join(process.resourcesPath, 'assets', iconFile);

  // Resize to 16x16 for the tray (Windows/Linux standard)
  let trayIcon;
  try {
    trayIcon = nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 });
  } catch {
    // Fallback: try png if ico fails
    const fallback = iconPath.replace('icon.ico', 'icon.png');
    trayIcon = nativeImage.createFromPath(fallback).resize({ width: 16, height: 16 });
  }

  tray = new Tray(trayIcon);
  tray.setToolTip(`CachiBot v${app.getVersion()}`);

  rebuildTrayMenu();

  function rebuildTrayMenu() {
    const contextMenu = Menu.buildFromTemplate([
      {
        label: 'Show CachiBot',
        click: () => {
          if (mainWindow) {
            mainWindow.show();
            mainWindow.focus();
          }
        },
      },
      { type: 'separator' },
      {
        label: 'Check for Updates',
        enabled: !!autoUpdater,
        click: () => {
          if (autoUpdater) {
            autoUpdater.checkForUpdates().catch(() => {});
          }
          if (mainWindow) {
            mainWindow.show();
            mainWindow.focus();
          }
        },
      },
      {
        label: 'Show Logs',
        click: () => {
          const logsDir = path.join(app.getPath('home'), '.cachibot', 'logs');
          shell.openPath(logsDir);
        },
      },
      {
        label: 'Start on Boot',
        type: 'checkbox',
        checked: getStartOnBoot(),
        click: (menuItem) => {
          setStartOnBoot(menuItem.checked);
        },
      },
      {
        label: 'Restart App',
        click: () => {
          stopBackend();
          app.relaunch();
          app.exit(0);
        },
      },
      { type: 'separator' },
      {
        label: 'Quit CachiBot',
        click: () => {
          app.quit();
        },
      },
    ]);

    tray.setContextMenu(contextMenu);
  }

  // Click the tray icon to show/focus the window
  tray.on('click', () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.focus();
      } else {
        mainWindow.show();
      }
    }
  });
}

// ---------------------------------------------------------------------------
// Version tracking — clear Chromium cache on version change
// ---------------------------------------------------------------------------

const VERSION_FILE = path.join(app.getPath('userData'), '.cachibot-version');

// ---------------------------------------------------------------------------
// Persistent settings (plain JSON, no dependencies)
// ---------------------------------------------------------------------------

const SETTINGS_FILE = path.join(app.getPath('userData'), 'settings.json');

function loadSettings() {
  try { return JSON.parse(fs.readFileSync(SETTINGS_FILE, 'utf8')); }
  catch { return {}; }
}

function saveSetting(key, value) {
  const settings = loadSettings();
  settings[key] = value;
  try { fs.writeFileSync(SETTINGS_FILE, JSON.stringify(settings, null, 2), 'utf8'); }
  catch (err) { console.error('[electron] Failed to save settings:', err.message); }
}

function getSetting(key, defaultValue) {
  const settings = loadSettings();
  return settings[key] !== undefined ? settings[key] : defaultValue;
}

// ---------------------------------------------------------------------------
// Start on boot
// ---------------------------------------------------------------------------

function setStartOnBoot(enabled) {
  app.setLoginItemSettings({ openAtLogin: enabled });
  saveSetting('startOnBoot', enabled);
}

function getStartOnBoot() {
  return getSetting('startOnBoot', false);
}

function checkVersionChange() {
  const current = app.getVersion();
  let previous = null;
  try { previous = fs.readFileSync(VERSION_FILE, 'utf8').trim(); } catch {}
  // Clear cache when version changes OR when no version file exists (reinstall
  // after a dirty uninstall that left stale Chromium cache behind).
  const needsClear = previous !== current;
  try { fs.writeFileSync(VERSION_FILE, current, 'utf8'); } catch {}
  return needsClear;
}

async function clearAllCaches() {
  await session.defaultSession.clearCache();
  await session.defaultSession.clearStorageData({
    storages: [
      'cachestorage', 'serviceworkers', 'localstorage',
      'shadercache', 'websql', 'indexdb',
    ],
  });
  const codeCacheDir = path.join(app.getPath('userData'), 'Code Cache');
  try { fs.rmSync(codeCacheDir, { recursive: true, force: true }); } catch {}
}

// ---------------------------------------------------------------------------
// Auto-updater
// ---------------------------------------------------------------------------

function configureAutoUpdater() {
  if (isDev || !autoUpdater) return;

  const channel = getSetting('updateChannel', 'stable');
  autoUpdater.allowPrerelease = channel === 'beta';

  autoUpdater.autoDownload = false;
  autoUpdater.autoInstallOnAppQuit = true;
}

function setupAutoUpdater() {
  if (isDev || !autoUpdater) return;

  autoUpdater.on('update-available', (info) => {
    console.log('[updater] Update available:', info.version);
    if (mainWindow) {
      mainWindow.webContents.send('update:available', {
        available: true,
        version: info.version,
        releaseNotes: info.releaseNotes || null,
      });
    }
  });

  autoUpdater.on('update-not-available', () => {
    console.log('[updater] No update available');
  });

  autoUpdater.on('update-downloaded', (info) => {
    console.log('[updater] Update downloaded:', info.version);
    if (mainWindow) {
      mainWindow.webContents.send('update:downloaded', { version: info.version });
    }
  });

  autoUpdater.on('download-progress', (progress) => {
    console.log('[updater] Download progress:', Math.round(progress.percent) + '%');
    if (mainWindow) {
      mainWindow.webContents.send('update:download-progress', progress);
    }
  });

  autoUpdater.on('error', (err) => {
    console.error('[updater] Error:', err.message);
    if (mainWindow) {
      mainWindow.webContents.send('update:error', {
        message: err.message,
      });
    }
  });

  // Initial check on startup (respects toggle)
  if (getSetting('autoUpdateEnabled', true)) {
    autoUpdater.checkForUpdates().catch(() => {});
  }

  // Periodic check every 6 hours (respects toggle)
  setInterval(() => {
    if (getSetting('autoUpdateEnabled', true)) {
      console.log('[updater] Periodic update check');
      autoUpdater.checkForUpdates().catch(() => {});
    }
  }, 6 * 60 * 60 * 1000);
}

// ---------------------------------------------------------------------------
// Auto-update during splash (before backend starts)
// ---------------------------------------------------------------------------

function checkAndAutoUpdate(splash) {
  if (isDev || !autoUpdater || !getSetting('autoInstallUpdates', false)) {
    return Promise.resolve();
  }

  return new Promise((resolve) => {
    splashStatus(splash, 'Checking for updates...');

    // Remove any existing listeners to avoid conflicts with setupAutoUpdater
    autoUpdater.removeAllListeners('update-available');
    autoUpdater.removeAllListeners('update-not-available');
    autoUpdater.removeAllListeners('update-downloaded');
    autoUpdater.removeAllListeners('download-progress');
    autoUpdater.removeAllListeners('error');

    let updateFound = false;

    autoUpdater.once('update-available', (info) => {
      updateFound = true;
      console.log('[splash-updater] Update available:', info.version);
      splashStatus(splash, `Downloading update v${info.version}...`);

      // Switch to determinate progress
      if (splash && !splash.isDestroyed()) {
        splash.webContents.executeJavaScript('window.showDeterminateProgress()').catch(() => {});
      }

      autoUpdater.downloadUpdate().catch((err) => {
        console.error('[splash-updater] Download failed:', err.message);
        // Restore indeterminate progress and continue normal startup
        if (splash && !splash.isDestroyed()) {
          splash.webContents.executeJavaScript('window.showIndeterminateProgress()').catch(() => {});
        }
        resolve();
      });
    });

    autoUpdater.once('update-not-available', () => {
      console.log('[splash-updater] No update available');
      resolve();
    });

    autoUpdater.on('download-progress', (progress) => {
      console.log('[splash-updater] Download progress:', Math.round(progress.percent) + '%');
      if (splash && !splash.isDestroyed()) {
        splash.webContents.executeJavaScript(`window.updateProgress(${progress.percent})`).catch(() => {});
      }
    });

    autoUpdater.once('update-downloaded', () => {
      console.log('[splash-updater] Update downloaded, installing...');
      splashStatus(splash, 'Installing update...');
      // Give the user a moment to see the status
      setTimeout(() => {
        autoUpdater.quitAndInstall();
      }, 1500);
    });

    autoUpdater.once('error', (err) => {
      console.error('[splash-updater] Error:', err.message);
      // Don't block startup — just continue
      if (splash && !splash.isDestroyed()) {
        splash.webContents.executeJavaScript('window.showIndeterminateProgress()').catch(() => {});
      }
      resolve();
    });

    autoUpdater.checkForUpdates().catch((err) => {
      console.error('[splash-updater] Check failed:', err.message);
      resolve();
    });

    // Safety timeout: don't block startup for more than 60 seconds
    setTimeout(() => {
      if (!updateFound) {
        console.log('[splash-updater] Timeout waiting for update check');
      }
      resolve();
    }, 60000);
  });
}

// ---------------------------------------------------------------------------
// Window control IPC handlers (custom title bar)
// ---------------------------------------------------------------------------

ipcMain.on('window:minimize', () => mainWindow?.minimize());
ipcMain.on('window:maximize', () => {
  if (mainWindow?.isMaximized()) {
    mainWindow.unmaximize();
  } else {
    mainWindow?.maximize();
  }
});
ipcMain.on('window:close', () => mainWindow?.close());
ipcMain.handle('window:isMaximized', () => mainWindow?.isMaximized() ?? false);

// ---------------------------------------------------------------------------
// Update & cache IPC handlers
// ---------------------------------------------------------------------------

ipcMain.handle('settings:get', (_event, key, defaultValue) => getSetting(key, defaultValue));
ipcMain.handle('settings:set', (_event, key, value) => {
  saveSetting(key, value);
  return { success: true };
});

ipcMain.handle('startup:get', () => getStartOnBoot());
ipcMain.handle('startup:set', (_event, enabled) => {
  setStartOnBoot(enabled);
  return { success: true };
});

ipcMain.handle('update:check', async () => {
  if (!autoUpdater) return { available: false };
  try {
    const result = await autoUpdater.checkForUpdates();
    if (result && result.updateInfo) {
      const info = result.updateInfo;
      return { available: true, version: info.version, releaseNotes: info.releaseNotes || null };
    }
    return { available: false };
  } catch {
    return { available: false };
  }
});

ipcMain.handle('update:download', async () => {
  if (!autoUpdater) return { success: false };
  try {
    await autoUpdater.downloadUpdate();
    return { success: true };
  } catch {
    return { success: false };
  }
});

ipcMain.on('update:install', () => {
  if (!autoUpdater) return;
  // Gracefully stop the backend before quitting to avoid SQLite corruption
  stopBackend();
  // Give the backend a moment to flush and close
  setTimeout(() => autoUpdater.quitAndInstall(), 1000);
});

ipcMain.handle('cache:clear', async () => {
  try {
    await clearAllCaches();
    return { success: true };
  } catch (err) {
    return { success: false, error: err.message };
  }
});

// ---------------------------------------------------------------------------
// Single instance lock — prevent duplicate windows / port conflicts
// ---------------------------------------------------------------------------

const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
}

// ---------------------------------------------------------------------------
// App lifecycle
// ---------------------------------------------------------------------------

app.whenReady().then(async () => {
  // Sync login item with saved setting
  app.setLoginItemSettings({ openAtLogin: getStartOnBoot() });

  // Clear Chromium cache when app version changes (e.g. after reinstall)
  if (checkVersionChange()) {
    console.log('[electron] Version changed, clearing all Chromium caches');
    await clearAllCaches();
  }

  // Content-Security-Policy
  const cspSources = [
    `http://${BACKEND_HOST}:${BACKEND_PORT}`,
    `ws://${BACKEND_HOST}:${BACKEND_PORT}`,
  ];
  if (isDev && DEV_FRONTEND_URL) cspSources.push(DEV_FRONTEND_URL, DEV_FRONTEND_URL.replace('http', 'ws'));

  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [
          [
            "default-src 'self'",
            `connect-src 'self' ${cspSources.join(' ')}`,
            "script-src 'self' 'unsafe-inline'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: blob:",
            "media-src 'self' data: blob:",
            "font-src 'self' data:",
            "object-src 'none'",
            "base-uri 'self'",
          ].join('; '),
        ],
      },
    });
  });

  session.defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => {
    callback(false);
  });

  const splash = createSplashWindow();

  // Configure auto-updater settings (channel, prerelease) before any checks
  configureAutoUpdater();

  // Auto-install updates during splash if enabled
  await checkAndAutoUpdate(splash);

  // When launched from dev script, backend is already running externally
  const externalBackend = !!DEV_FRONTEND_URL;
  if (externalBackend) {
    // Dev mode: skip backend startup/wait, Vite proxy handles API calls
    console.log('[electron] Dev mode: loading from', DEV_FRONTEND_URL);
    splashStatus(splash, 'Connecting to dev server...');
    await new Promise((r) => setTimeout(r, 800));
  } else {
    // Kill any orphaned server process from a previous crash
    await killStalePidFile();

    const portInUse = await isPortInUse(BACKEND_PORT);
    if (portInUse) {
      splashStatus(splash, 'Clearing stale process...');
      console.log(`[electron] Port ${BACKEND_PORT} in use, killing existing process...`);
      await killProcessOnPort(BACKEND_PORT);
      // Give the OS a moment to release the port
      await new Promise((r) => setTimeout(r, 500));
    }

    splashStatus(splash, 'Starting server...');
    startBackend();
    splashStatus(splash, 'Waiting for server...');
    try {
      await waitForPort(BACKEND_PORT);
    } catch (err) {
      splash.close();
      console.error('[electron] Backend failed to start:', err.message);
      const details = backendStderr.trim()
        ? `\n\nBackend output:\n${backendStderr.trim().split('\n').slice(-10).join('\n')}`
        : '';
      dialog.showErrorBox(
        'Backend Error',
        `The CachiBot backend failed to start.\n\n${err.message}${details}`
      );
      app.quit();
      return;
    }
    splashStatus(splash, 'Server ready');
  }

  splashStatus(splash, 'Loading interface...');
  createWindow(splash);
  createTray();
  setupAutoUpdater();
});

app.on('window-all-closed', () => {
  if (!process.env.ELECTRON_DEV_URL) stopBackend();
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on('before-quit', () => {
  if (!process.env.ELECTRON_DEV_URL) stopBackend();
});
