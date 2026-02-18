const { app, BrowserWindow, shell, dialog, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
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
  if (backendProcess) {
    console.log('[electron] Stopping backend...');
    backendProcess.kill();
    backendProcess = null;
  }
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
// Auto-updater
// ---------------------------------------------------------------------------

function setupAutoUpdater() {
  if (isDev || !autoUpdater) return;

  autoUpdater.autoDownload = false;
  autoUpdater.autoInstallOnAppQuit = true;

  autoUpdater.on('update-available', (info) => {
    dialog
      .showMessageBox(mainWindow, {
        type: 'info',
        title: 'Update Available',
        message: `CachiBot v${info.version} is available. Download now?`,
        buttons: ['Download', 'Later'],
      })
      .then(({ response }) => {
        if (response === 0) autoUpdater.downloadUpdate();
      });
  });

  autoUpdater.on('update-downloaded', () => {
    dialog
      .showMessageBox(mainWindow, {
        type: 'info',
        title: 'Update Ready',
        message: 'Update downloaded. CachiBot will restart to install it.',
        buttons: ['Restart Now', 'Later'],
      })
      .then(({ response }) => {
        if (response === 0) autoUpdater.quitAndInstall();
      });
  });

  autoUpdater.checkForUpdates().catch(() => {});
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
// App lifecycle
// ---------------------------------------------------------------------------

app.whenReady().then(async () => {
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
