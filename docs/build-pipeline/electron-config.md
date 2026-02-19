# Electron Configuration Review

**Reviewer:** Carlos (Electron Architect)
**Date:** 2026-02-18
**Scope:** Complete review of the CachiBot Electron desktop app setup

---

## Overall Assessment

**Maturity: Early-to-Mid stage (6/10)**

The Electron setup is functional and reasonably well-structured for a project at this stage. The architecture makes sound fundamental choices (context isolation, no nodeIntegration, preload script pattern), and the backend lifecycle management is robust. However, there are notable gaps in code signing, single-instance management, and security hardening that must be addressed before wider distribution.

| Area | Status |
|------|--------|
| electron-builder config | Complete for all 3 platforms |
| Main process | Well-structured, good backend lifecycle |
| Security (BrowserWindow) | Good foundation, missing hardening |
| Code signing | Not configured (explicitly disabled in CI) |
| App identity | Mostly complete, missing protocol handler |
| Install behavior | Configurable NSIS, clean uninstall |
| Instance management | Missing entirely |
| Dev vs prod loading | Clean separation, reliable |
| IPC channels | Well-typed, properly scoped |
| Auto-updater | Integrated with graceful degradation |

---

## Configuration Analysis

### electron-builder Config (`desktop/package.json` "build" key)

**Location:** `desktop/package.json:26-85`

The config is embedded in package.json rather than a separate `electron-builder.yml`. This is valid but can become unwieldy as it grows.

#### What is configured:

- **appId:** `com.cachibot.desktop` -- Good reverse-domain format
- **productName:** `CachiBot`
- **copyright:** `Copyright 2025-2026 Juan Denis`
- **Output directory:** `../release` (relative to desktop/)
- **Build resources:** `../build` (contains entitlements, installer script, PyInstaller artifacts)

#### Files included in the app:

```json
"files": ["main.js", "preload.js", "package.json"]
```

This is minimal and correct -- only the Electron main process files. The frontend is served by the backend, not bundled as static files in the Electron app itself.

#### Extra Resources:

```json
"extraResources": [
  { "from": "../build/backend/", "to": "backend", "filter": ["**/*"] },
  { "from": "../assets/", "to": "assets", "filter": ["icon.ico", "icon.png"] }
]
```

The PyInstaller-bundled backend binary is placed in `resources/backend/`. This is the correct approach -- extraResources land outside the asar archive, allowing the binary to be executed directly.

#### Platform Targets:

| Platform | Targets | Architecture |
|----------|---------|-------------|
| Windows | NSIS installer | x64 only |
| macOS | DMG + ZIP | Universal (default) |
| Linux | AppImage + DEB | x64 only |

**Observations:**
- macOS does not specify `arch`, so it defaults to the build runner's architecture. The CI uses `macos-latest` which is ARM64 (M-series). This means the DMG/ZIP will be arm64-only, not universal. This is likely unintentional -- the release notes advertise "Universal".
- Windows only targets x64 (ARM64 Windows excluded, reasonable for now).
- Linux targets AppImage (portable) and DEB (Debian/Ubuntu). No RPM (Fedora/RHEL), Snap, or Flatpak.

#### Artifact Naming:

```
Windows: CachiBot-Setup-${version}-win.exe
macOS:   CachiBot-${version}-mac.dmg / .zip
Linux:   CachiBot-${version}-linux.AppImage / .deb
```

Naming is clean and consistent. No arch suffix, which is fine while only targeting one arch per platform.

#### Publish Config:

```json
"publish": {
  "provider": "github",
  "owner": "jhd3197",
  "repo": "cachibot",
  "releaseType": "release"
}
```

This feeds the `electron-updater` auto-update system. The `--publish always` flag in CI uploads artifacts directly to the GitHub Release.

---

### Main Process (`desktop/main.js`)

**File:** `desktop/main.js` (566 lines)

#### Startup Flow:

1. `app.whenReady()` fires
2. `checkVersionChange()` -- clears all Chromium caches if app version changed (prevents stale UI after update)
3. `createSplashWindow()` -- shows a loading splash
4. `startBackend()` -- spawns the PyInstaller binary (or `cachibot server` in dev)
5. `waitForPort(6392)` -- polls TCP port with 60 retries * 500ms = 30s max wait
6. `createWindow()` -- creates main BrowserWindow
7. `createTray()` -- creates system tray icon
8. Splash closes, auto-updater initializes

**This is a solid startup flow.** The splash screen gives feedback during the potentially slow backend startup, and the port-waiting logic has good timeout/retry behavior with early exit detection if the backend process crashes.

#### BrowserWindow Configuration:

```javascript
mainWindow = new BrowserWindow({
  width: 1400, height: 900,
  minWidth: 1000, minHeight: 700,
  webPreferences: {
    preload: path.join(__dirname, 'preload.js'),
    contextIsolation: true,
    nodeIntegration: false,
  },
  titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'hidden',
  titleBarOverlay: false,
  frame: process.platform === 'darwin',
  backgroundColor: '#09090b',
  show: false,  // shown on ready-to-show
});
```

**Good:**
- `contextIsolation: true` -- correct, isolates preload from renderer
- `nodeIntegration: false` -- correct, renderer cannot access Node.js APIs
- `show: false` + `ready-to-show` -- prevents white flash
- Platform-aware titlebar handling

**Missing (security hardening):**
- `sandbox: true` -- not explicitly set. While Electron 20+ defaults sandbox to true, it is best practice to set it explicitly
- `webSecurity: true` -- not explicitly set (defaults to true, but should be explicit)
- No `Content-Security-Policy` header set via `session.defaultSession.webRequest`
- No `will-navigate` handler to prevent navigation away from the app
- No `permission-request-handler` to limit permissions (camera, mic, geolocation, etc.)

#### External Link Handling:

```javascript
mainWindow.webContents.setWindowOpenHandler(({ url }) => {
  if (url.startsWith('http') && !url.includes(BACKEND_HOST)) {
    shell.openExternal(url);
    return { action: 'deny' };
  }
  return { action: 'allow' };
});
```

This is a reasonable approach but has a subtle issue: `url.includes(BACKEND_HOST)` checks for `127.0.0.1` anywhere in the URL string, which could be bypassed with a crafted URL like `https://evil.com/127.0.0.1/redirect`. A more robust check would parse the URL and compare the hostname.

#### Backend Lifecycle:

The backend management is well-implemented:

- **Dev mode:** Runs `cachibot server` via shell (resolves PATH)
- **Production:** Runs the PyInstaller binary from `process.resourcesPath`
- **Shutdown:** On Windows, uses `taskkill /T /F` to kill the entire process tree (prevents zombie uvicorn workers). On other platforms, uses simple `.kill()`
- **Error handling:** Captures last 2KB of stderr for error reporting in dialogs
- **Port waiting:** TCP socket polling with configurable retries, early exit on backend crash

**One concern:** The `stopBackend()` function on non-Windows platforms uses `backendProcess.kill()` which sends SIGTERM. This should work for uvicorn, but if the backend spawns child processes on Linux/macOS, they could become orphaned. Consider using process groups (`process.kill(-pid, 'SIGTERM')`) or a similar approach.

#### Version Cache Clearing:

```javascript
const VERSION_FILE = path.join(app.getPath('userData'), '.cachibot-version');
```

Tracks the last-run version. On version change, clears all Chromium caches including Code Cache, localStorage, service workers, etc. This is a smart approach to prevent stale frontend code after an update. The cache clearing logic is duplicated in 3 places (startup check, tray menu, IPC handler) -- could be extracted into a shared function.

---

### Preload Script (`desktop/preload.js`)

**File:** `desktop/preload.js` (38 lines)

Uses `contextBridge.exposeInMainWorld` correctly to expose a limited API surface as `window.electronAPI`.

#### Exposed API Surface:

| API | Type | Direction |
|-----|------|-----------|
| `platform` | Sync property | Main -> Renderer |
| `isDesktop` | Sync property | Main -> Renderer |
| `appVersion` | Sync IPC | Main -> Renderer |
| `versions` | Sync property | Main -> Renderer |
| `windowMinimize` | `ipcRenderer.send` | Renderer -> Main |
| `windowMaximize` | `ipcRenderer.send` | Renderer -> Main |
| `windowClose` | `ipcRenderer.send` | Renderer -> Main |
| `windowIsMaximized` | `ipcRenderer.invoke` | Renderer -> Main (async) |
| `onMaximizedChange` | `ipcRenderer.on` | Main -> Renderer (listener) |
| `checkForUpdate` | `ipcRenderer.invoke` | Renderer -> Main (async) |
| `downloadUpdate` | `ipcRenderer.invoke` | Renderer -> Main (async) |
| `installUpdate` | `ipcRenderer.send` | Renderer -> Main |
| `onUpdateAvailable` | `ipcRenderer.on` | Main -> Renderer (listener) |
| `onUpdateProgress` | `ipcRenderer.on` | Main -> Renderer (listener) |
| `clearCache` | `ipcRenderer.invoke` | Renderer -> Main (async) |

**Good:**
- All IPC is one-way or invoke-based (no raw `ipcRenderer` exposed)
- Event listeners return cleanup functions for React effect cleanup
- API surface is minimal and focused

**Concern:**
- `appVersion: ipcRenderer.sendSync('app:getVersion')` -- `sendSync` blocks the renderer process. While this is a quick call, it is an anti-pattern. Consider using an async approach or passing the version through the preload directly (e.g., `app.getVersion()` is not available in preload, but the version could be passed via `additionalArguments` or a shared constant).

#### TypeScript Typings:

The frontend properly types `window.electronAPI` in `frontend/src/vite-env.d.ts:21-47`, including `UpdateCheckResult` and `UpdateDownloadProgress` interfaces. The optional `?` on `Window.electronAPI` correctly handles the non-Electron (browser) case.

---

### App Signing

**Status: Not configured. Explicitly disabled in CI.**

From `.github/workflows/publish.yml:290-295`:
```yaml
- name: Build Electron app
  shell: bash
  run: |
    unset CSC_LINK CSC_KEY_PASSWORD
    npx electron-builder --${{ matrix.platform }} --publish always
  env:
    CSC_IDENTITY_AUTO_DISCOVERY: false
```

The CI explicitly removes signing variables and disables auto-discovery. This means:

- **Windows:** Installer is unsigned. Users will see "Windows protected your PC" (SmartScreen) on first run. After enough downloads, SmartScreen may learn to trust it, but this is unreliable.
- **macOS:** DMG is unsigned and unnotarized. Users will see "CachiBot can't be opened because Apple cannot check it for malicious software." Users must right-click > Open, or use `xattr -cr` to bypass. This is a significant friction point.
- **Linux:** No signing needed for AppImage/DEB (though DEB can be signed with GPG).

**The `build/entitlements.mac.plist` file exists** with JIT, unsigned executable memory, dyld environment variables, and network entitlements. These are correct for a Chromium-based app that bundles a Python backend, but they are currently unused since signing is disabled.

**Impact:** This is the single biggest barrier to professional distribution. Unsigned apps on macOS are practically unusable for non-technical users, and unsigned Windows apps trigger scary warnings.

---

### App Identity

| Property | Configured? | Value |
|----------|-------------|-------|
| App ID | Yes | `com.cachibot.desktop` |
| Product Name | Yes | `CachiBot` |
| Description | Yes | In package.json |
| Author | Yes | Juan Denis |
| Homepage | Yes | https://cachibot.ai |
| License | Yes | MIT |
| Icon (Windows) | Yes | `assets/icon.ico` |
| Icon (macOS) | Yes | `assets/icon.png` |
| Icon (Linux) | Yes | `assets/icon.png` |
| Category (Linux) | Yes | `Utility` |
| Protocol handler | No | Not configured |
| File associations | No | Not configured |
| Deep links | No | Not configured |

**Missing:**
- No `cachibot://` protocol handler. This would be useful for opening specific chats/bots from external links.
- No file associations (e.g., `.cachibot` config files).
- macOS icon should ideally be an `.icns` file (not `.png`). electron-builder can convert PNG to ICNS at build time, but an explicit ICNS with all required sizes (16x16 through 1024x1024) ensures best quality.

---

### Install Behavior

#### Windows (NSIS):

```json
"nsis": {
  "oneClick": false,
  "allowToChangeInstallationDirectory": true
}
```

- **Not one-click:** Shows the installer wizard with options (good for power users)
- **Custom install path:** User can choose where to install
- **Default location:** Per-user (`%LOCALAPPDATA%\Programs\CachiBot`) by default (standard for NSIS)
- **User data:** Stored in `%APPDATA%\cachibot-desktop` (Electron default via `app.getPath('userData')`)

**Custom uninstaller script** (`build/installer.nsh`):
```nsh
!macro customUnInstall
  MessageBox MB_YESNO "Delete all CachiBot app data (settings, cache)?" IDYES removeData IDNO skipRemove
  removeData:
    RMDir /r "$APPDATA\cachibot-desktop"
  skipRemove:
!macroend
```

This is a nice touch -- asks the user if they want to remove app data on uninstall.

**Missing:**
- `perMachine: false` is not explicitly set (defaults to per-user, which is fine)
- No `deleteAppDataOnUninstall` option (handled by the custom script)
- No Start Menu shortcut configuration (uses electron-builder defaults)

#### macOS (DMG):

Standard DMG with drag-to-Applications behavior. No custom DMG background image or window layout configured.

#### Linux:

- **AppImage:** Portable, no installation needed
- **DEB:** Standard Debian package in `Utility` category
- **Missing:** No desktop file customization, no `mimeType` associations

---

### Instance Management

**Status: Not implemented.**

There is no call to `app.requestSingleInstanceLock()` anywhere in the codebase. This means:

- Users can open multiple instances of CachiBot simultaneously
- Each instance would try to start its own backend on port 6392, causing a port conflict
- The second instance's backend would fail to bind, and the user would see an error dialog
- Multiple tray icons would appear

**This is a critical issue** that should be addressed before release.

---

### Dev vs Prod Loading

The loading strategy is clean and reliable:

```javascript
const isDev = !app.isPackaged;
const DEV_FRONTEND_URL = process.env.ELECTRON_DEV_URL || null;

// In createWindow():
const loadURL = (isDev && DEV_FRONTEND_URL) ? DEV_FRONTEND_URL : BACKEND_URL;
```

**Three modes:**

1. **Packaged app (production):** Loads from `http://127.0.0.1:6392` (backend serves the built frontend)
2. **Dev with ELECTRON_DEV_URL set:** Loads from Vite dev server (hot reload), skips backend startup entirely (assumes external backend)
3. **Dev without ELECTRON_DEV_URL:** Starts `cachibot server` via CLI, loads from backend URL

This is a well-thought-out approach. The frontend is always served by HTTP (either Vite or the backend), never loaded from `file://` protocol. This avoids CORS issues and keeps the architecture consistent between desktop and web.

---

### IPC Channels

#### Main -> Renderer (push):

| Channel | Data | Purpose |
|---------|------|---------|
| `window:maximized` | `boolean` | Window maximize state changes |
| `update:available` | `{available, version, releaseNotes}` | Auto-updater found an update |
| `update:download-progress` | `{bytesPerSecond, percent, transferred, total}` | Download progress |

#### Renderer -> Main (request/response):

| Channel | Method | Response | Purpose |
|---------|--------|----------|---------|
| `app:getVersion` | `sendSync` | `string` | Get app version (sync!) |
| `window:minimize` | `send` | None | Minimize window |
| `window:maximize` | `send` | None | Toggle maximize |
| `window:close` | `send` | None | Close window |
| `window:isMaximized` | `invoke` | `boolean` | Check maximize state |
| `update:check` | `invoke` | `{available, version?, releaseNotes?}` | Check for updates |
| `update:download` | `invoke` | `{success}` | Download update |
| `update:install` | `send` | None | Install and restart |
| `cache:clear` | `invoke` | `{success, error?}` | Clear Chromium caches |

**All IPC channels are properly handled** -- every `send`/`invoke` in the preload has a matching `on`/`handle` in main.js. No orphaned channels.

---

## Security Review

### Strengths

1. **Context isolation enabled** -- preload script runs in isolated context
2. **nodeIntegration disabled** -- renderer cannot access Node.js APIs
3. **Preload uses contextBridge** -- no raw `ipcRenderer` exposed to the renderer
4. **External links open in system browser** -- `setWindowOpenHandler` prevents navigation
5. **Backend binds to 127.0.0.1 only** -- not exposed to the network
6. **Update installation gracefully stops backend first** -- prevents SQLite corruption

### Weaknesses

1. **No Content-Security-Policy** -- the renderer can load resources from any origin. Should restrict to `self` and the backend URL.

2. **No `will-navigate` handler** -- if the renderer content somehow triggers navigation (e.g., a malicious link in markdown rendering), the main window could navigate to an external site. Add:
   ```javascript
   mainWindow.webContents.on('will-navigate', (event, url) => {
     if (!url.startsWith(BACKEND_URL) && !(isDev && DEV_FRONTEND_URL && url.startsWith(DEV_FRONTEND_URL))) {
       event.preventDefault();
     }
   });
   ```

3. **No permission request handler** -- the app does not restrict web permissions (camera, microphone, geolocation, notifications). Add:
   ```javascript
   session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
     callback(false); // Deny all by default, whitelist as needed
   });
   ```

4. **`setWindowOpenHandler` bypass** -- the URL check `url.includes(BACKEND_HOST)` is vulnerable to URL containing `127.0.0.1` as a path component (e.g., `https://evil.com/127.0.0.1`). Should parse the URL and compare the hostname:
   ```javascript
   const parsed = new URL(url);
   if (parsed.hostname === BACKEND_HOST) { return { action: 'allow' }; }
   ```

5. **Unsigned binaries** -- both the Electron app and the PyInstaller backend binary are unsigned. This means any attacker who can modify the files (e.g., via a compromised download mirror) can inject code without detection.

6. **No sandbox explicitly set** -- while Electron 20+ defaults to sandbox=true, explicitly setting `sandbox: true` in webPreferences prevents any future Electron version changes from silently disabling it.

---

## Issues Found

### Critical

| # | Issue | Impact | Location |
|---|-------|--------|----------|
| C1 | No single instance lock | Multiple instances cause port conflicts, duplicate tray icons, confusing UX | `desktop/main.js` -- missing `app.requestSingleInstanceLock()` |
| C2 | No code signing on any platform | macOS: app requires manual bypass to open. Windows: SmartScreen warnings scare users away. Blocks professional distribution. | `.github/workflows/publish.yml:290-295` |

### Major

| # | Issue | Impact | Location |
|---|-------|--------|----------|
| M1 | macOS builds may be ARM64-only, not Universal | Intel Mac users cannot run the app. Release notes claim "Universal" but CI likely produces ARM64 only. | `desktop/package.json:63` -- no `arch` specified; CI runs on `macos-latest` (arm64) |
| M2 | No Content-Security-Policy | XSS or injected content could load arbitrary scripts/resources | `desktop/main.js` -- missing `webRequest.onHeadersReceived` |
| M3 | No `will-navigate` handler | Main window could be navigated to external sites | `desktop/main.js:160-202` |
| M4 | `setWindowOpenHandler` URL check is bypassable | Crafted URL with `127.0.0.1` in path could be allowed to open in-app | `desktop/main.js:181-187` |
| M5 | Non-Windows backend shutdown may orphan children | `backendProcess.kill()` on Linux/macOS sends SIGTERM only to the parent process; uvicorn workers may linger | `desktop/main.js:97-99` |

### Minor

| # | Issue | Impact | Location |
|---|-------|--------|----------|
| m1 | `sendSync` for app version | Blocks renderer during startup. Anti-pattern. | `desktop/preload.js:6` |
| m2 | Cache-clearing logic duplicated 3 times | Maintenance burden, risk of divergence | `desktop/main.js:300-318`, `main.js:474-494`, `main.js:500-518` |
| m3 | No macOS `.icns` icon file | PNG works but may not render at all resolutions optimally | `assets/icon.png` used for macOS |
| m4 | No sandbox explicitly set in webPreferences | Relies on Electron default (true since v20), could change | `desktop/main.js:168-172` |
| m5 | No `perMachine` or `allowElevation` in NSIS config | Defaults are fine, but explicit is better for documentation | `desktop/package.json:58-61` |
| m6 | No RPM target for Linux | Fedora/RHEL users have no native package | `desktop/package.json:71-78` |

---

## Recommendations

### Immediate (before next release)

1. **Add single instance lock** -- Prevent multiple instances from conflicting:
   ```javascript
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
   ```

2. **Fix macOS architecture** -- Add explicit arch to the mac target:
   ```json
   "mac": {
     "target": [
       { "target": "dmg", "arch": ["universal"] },
       { "target": "zip", "arch": ["universal"] }
     ]
   }
   ```
   Or at minimum, `["x64", "arm64"]` to build both. Note: universal binaries require that the PyInstaller backend also be built for both architectures.

3. **Add `will-navigate` handler** and **fix URL check** in `setWindowOpenHandler`.

4. **Extract cache-clearing into a shared function** to eliminate duplication.

### Short-term (next 1-3 releases)

5. **Add Content-Security-Policy** via session handler:
   ```javascript
   session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
     callback({
       responseHeaders: {
         ...details.responseHeaders,
         'Content-Security-Policy': ["default-src 'self' http://127.0.0.1:6392; script-src 'self'; style-src 'self' 'unsafe-inline'"]
       }
     });
   });
   ```

6. **Set up code signing** -- At minimum for macOS (required for non-scary UX). Windows EV code signing is expensive but standard signing is affordable. This requires:
   - macOS: Apple Developer account ($99/year), certificate, notarization via `electron-builder`'s `afterSign` hook
   - Windows: Code signing certificate (DigiCert, Sectigo, etc.)

7. **Add permission request handler** to deny unnecessary permissions.

8. **Explicitly set `sandbox: true`** in webPreferences.

### Long-term

9. **Consider `cachibot://` protocol handler** for deep linking from web/external apps.
10. **Add DMG background image** for a more polished macOS installation experience.
11. **Add RPM target** for Fedora/RHEL Linux users.
12. **Replace `sendSync` for version** with an async approach or preload-time constant.

---

## File Inventory

| File | Purpose | Lines |
|------|---------|-------|
| `desktop/package.json` | Electron deps + electron-builder config | 86 |
| `desktop/main.js` | Main process (backend lifecycle, window, tray, IPC, updater) | 566 |
| `desktop/preload.js` | Context bridge API for renderer | 38 |
| `desktop/pyinstaller-server.py` | Entry point for PyInstaller binary | 34 |
| `build/entitlements.mac.plist` | macOS entitlements (currently unused) | 16 |
| `build/installer.nsh` | Custom NSIS uninstall script | 6 |
| `frontend/src/vite-env.d.ts` | TypeScript types for ElectronAPI | 47 |
| `frontend/src/components/layout/TitleBar.tsx` | Custom window title bar | 63 |
| `frontend/src/components/views/AppSettingsView.tsx` | Settings UI with Electron update/cache sections | ~1650 |
| `frontend/src/components/dialogs/UpdateDialog.tsx` | pip-based update dialog (disabled in Electron) | 201 |
| `frontend/src/components/common/UpdateBanner.tsx` | pip-based update banner (disabled in Electron) | 37 |
