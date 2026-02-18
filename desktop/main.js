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
const BACKEND_PORT = 6392;
const BACKEND_HOST = '127.0.0.1';
const BACKEND_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`;

// In dev mode, load from Vite dev server for hot reload when available
const DEV_FRONTEND_URL = process.env.ELECTRON_DEV_URL || null;

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
    backendProcess.kill();
  }
  backendProcess = null;
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

// ---------------------------------------------------------------------------
// Window creation
// ---------------------------------------------------------------------------

function createWindow() {
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
    },
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'hidden',
    titleBarOverlay: false,
    frame: process.platform === 'darwin',
    backgroundColor: '#09090b', // zinc-950
    show: false,
  });

  // Open external links in the system browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http') && !url.includes(BACKEND_HOST)) {
      shell.openExternal(url);
      return { action: 'deny' };
    }
    return { action: 'allow' };
  });

  mainWindow.once('ready-to-show', () => mainWindow.show());

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
    width: 400,
    height: 300,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    webPreferences: { nodeIntegration: false, contextIsolation: true },
  });

  splash.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(`
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        body {
          margin: 0; display: flex; align-items: center; justify-content: center;
          height: 100vh; background: #09090b; color: #a1a1aa; font-family: system-ui;
          flex-direction: column; gap: 16px; border-radius: 12px;
          -webkit-app-region: drag;
        }
        .title { font-size: 28px; font-weight: 700; color: #10b981; }
        .subtitle { font-size: 14px; opacity: 0.7; }
        .spinner {
          width: 32px; height: 32px; border: 3px solid #27272a;
          border-top-color: #10b981; border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
      </style>
    </head>
    <body>
      <div class="title">CachiBot</div>
      <div class="spinner"></div>
      <div class="subtitle">Starting the armored agent...</div>
    </body>
    </html>
  `)}`);

  return splash;
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
  tray.setToolTip('CachiBot');

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

// ---------------------------------------------------------------------------
// Auto-updater
// ---------------------------------------------------------------------------

function setupAutoUpdater() {
  if (isDev || !autoUpdater) return;

  autoUpdater.autoDownload = false;
  autoUpdater.autoInstallOnAppQuit = true;

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
  });

  autoUpdater.on('download-progress', (progress) => {
    console.log('[updater] Download progress:', Math.round(progress.percent) + '%');
    if (mainWindow) {
      mainWindow.webContents.send('update:download-progress', progress);
    }
  });

  autoUpdater.on('error', (err) => {
    console.error('[updater] Error:', err.message);
  });

  // Initial check on startup
  autoUpdater.checkForUpdates().catch(() => {});

  // Periodic check every 6 hours
  setInterval(() => {
    console.log('[updater] Periodic update check');
    autoUpdater.checkForUpdates().catch(() => {});
  }, 6 * 60 * 60 * 1000);
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
    await session.defaultSession.clearCache();
    await session.defaultSession.clearStorageData({
      storages: [
        'cachestorage',
        'serviceworkers',
        'localstorage',
        'shadercache',
        'websql',
        'indexdb',
      ],
    });
    // Delete V8 Code Cache directory
    const codeCacheDir = path.join(app.getPath('userData'), 'Code Cache');
    try { fs.rmSync(codeCacheDir, { recursive: true, force: true }); } catch {}
    return { success: true };
  } catch (err) {
    return { success: false, error: err.message };
  }
});

// ---------------------------------------------------------------------------
// App lifecycle
// ---------------------------------------------------------------------------

app.whenReady().then(async () => {
  // Clear Chromium cache when app version changes (e.g. after reinstall)
  if (checkVersionChange()) {
    console.log('[electron] Version changed, clearing all Chromium caches');
    await session.defaultSession.clearCache();
    await session.defaultSession.clearStorageData({
      storages: [
        'cachestorage',
        'serviceworkers',
        'localstorage',
        'shadercache',
        'websql',
        'indexdb',
      ],
    });
    // Delete V8 Code Cache directory — compiled JS from the old UI
    const codeCacheDir = path.join(app.getPath('userData'), 'Code Cache');
    try { fs.rmSync(codeCacheDir, { recursive: true, force: true }); } catch {}
  }

  const splash = createSplashWindow();

  // When launched from dev script, backend is already running externally
  const externalBackend = !!DEV_FRONTEND_URL;
  if (externalBackend) {
    // Dev mode: skip backend startup/wait, Vite proxy handles API calls
    console.log('[electron] Dev mode: loading from', DEV_FRONTEND_URL);
  } else {
    startBackend();
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
  }

  createWindow();
  createTray();
  splash.close();
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
