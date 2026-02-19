# Update System Review

## Current State: PARTIAL / TWO COMPETING SYSTEMS

CachiBot has **two independent update mechanisms** that serve different deployment modes. The Electron (desktop) path uses `electron-updater` for native OS-level updates, while the pip (server) path uses PyPI + `pip install` for in-place backend upgrades. Both are implemented but have significant gaps and conflicts.

---

## 1. Electron Auto-Update (Desktop Path)

### 1.1 Installation & Configuration

- **Package**: `electron-updater@^6.3.0` is listed in `desktop/package.json` dependencies.
- **Import**: Loaded with a graceful fallback in `desktop/main.js:7-13` -- if the module is missing, `autoUpdater` is set to `null` and the app continues without update support.
- **Provider**: GitHub Releases, configured in `desktop/package.json` `build.publish`:
  ```json
  "publish": {
    "provider": "github",
    "owner": "jhd3197",
    "repo": "cachibot",
    "releaseType": "release"
  }
  ```

### 1.2 Update Flow

The full flow is implemented in `desktop/main.js:373-417` (`setupAutoUpdater()`):

| Step | Implemented | Details |
|------|-------------|---------|
| Check on app launch | Yes | `autoUpdater.checkForUpdates()` called in `setupAutoUpdater()` (line 410) |
| Periodic check | Yes | Every 6 hours via `setInterval` (line 413-416) |
| Manual check | Yes | Tray menu "Check for Updates" (line 286-296) and Settings UI button |
| Auto-download | No (intentional) | `autoUpdater.autoDownload = false` (line 376) |
| Notify user | Yes | Sends `update:available` IPC to renderer (line 382-387) |
| Download progress | Yes | Sends `update:download-progress` IPC to renderer (line 398-403) |
| Download on demand | Yes | IPC handler `update:download` (line 456-464) |
| Install on demand | Yes | IPC handler `update:install` (line 466-472), stops backend first |
| Auto-install on quit | Yes | `autoUpdater.autoInstallOnAppQuit = true` (line 377) |

### 1.3 Update UI (Electron)

Located in `frontend/src/components/views/AppSettingsView.tsx`, the `ElectronUpdatesSection` component (line 361-537) provides:

- Current version display
- "Check for Updates" button
- Available version display when an update is found
- Release notes (expandable)
- "Download Update" button with a progress bar (percentage + visual bar)
- "Restart & Install" button after download completes
- Progress states: checking, downloading (with percent), downloaded

The tray context menu also has a "Check for Updates" item (`desktop/main.js:286-296`).

### 1.4 IPC Bridge

Defined in `desktop/preload.js:22-35`, the renderer has access to:
- `checkForUpdate()` -- invoke from Settings UI
- `downloadUpdate()` -- trigger download
- `installUpdate()` -- quit and install
- `onUpdateAvailable(callback)` -- listen for push notifications from main process
- `onUpdateProgress(callback)` -- listen for download progress

TypeScript types are declared in `frontend/src/vite-env.d.ts:8-43`.

### 1.5 Error Handling

- **Updater errors**: Caught with `autoUpdater.on('error')` (line 405-407), logged to console only. No user-facing notification.
- **Check failures**: `checkForUpdates().catch(() => {})` silently swallows errors (lines 410, 415).
- **Download failures**: Returns `{ success: false }` to the renderer, which shows a toast error "Failed to download update" (AppSettingsView line 412-414).
- **Missing updater**: Gracefully handled -- tray "Check for Updates" is disabled, all IPC handlers return safe defaults.

---

## 2. Pip Update System (Server/CLI Path)

### 2.1 Backend Implementation

A full pip-based update service exists at `src/cachibot/services/update_service.py` (651 lines) with:

- **Version check**: Queries PyPI JSON API (`https://pypi.org/pypi/cachibot/json`) for latest stable and pre-release versions.
- **Release notes**: Fetches from GitHub API (`https://api.github.com/repos/jhd3197/cachibot/releases/tags/v{version}`).
- **Caching**: Results cached for 1 hour (configurable via `CACHE_TTL`).
- **Docker detection**: Blocks updates if running in Docker container.

### 2.2 Update Flow

Exposed via REST API at `src/cachibot/api/routes/update.py`:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/update/check` | GET | Check PyPI for new versions |
| `/api/update/apply` | POST | Download and install via pip |
| `/api/update/restart` | POST | Restart the server process |
| `/api/update/diagnostics` | GET | Installation health check |

The `perform_update()` flow (line 392-493):
1. Block if Docker
2. Resolve target version from PyPI
3. Save current version as "last-known-good" for rollback
4. Clean corrupted artifacts (Windows `~`-prefixed dirs)
5. Run `pip install` with retry (3 attempts, exponential backoff)
6. On Windows: adds `--force-reinstall --no-cache-dir` flags
7. Post-install cleanup
8. Verify installation (import test of critical modules)
9. On failure: rollback to previous version

### 2.3 Update UI (Pip)

- **Banner**: `frontend/src/components/common/UpdateBanner.tsx` -- dismissible notification bar showing available version.
- **Dialog**: `frontend/src/components/dialogs/UpdateDialog.tsx` -- full update dialog with release notes, progress spinner, pip output, and restart button.
- **Settings**: `PipUpdatesSection` in AppSettingsView (line 540+) -- version display, check button, beta opt-in.
- **State**: Zustand store at `frontend/src/stores/update.ts` with persistence for skipped versions, beta opt-in, and last check time.

**Both the UpdateBanner and UpdateDialog explicitly return `null` when running in Electron** (lines checking `window.electronAPI?.isDesktop`), so they are disabled in desktop mode.

### 2.4 Windows-Specific Safety

The pip update system has extensive Windows safety measures:
- Corruption detection: Scans for `~`-prefixed directories (left by interrupted pip installs on NTFS)
- External updater script: On Windows, a detached Python script handles the restart to avoid file lock issues
- Force reinstall: Adds `--force-reinstall --no-cache-dir` on Windows
- Repair command: `cachibot repair` CLI for manual corruption cleanup

---

## 3. Dual Update Path Analysis

### 3.1 The Conflict

The two update systems target **different components**:

| System | What It Updates | Version Source |
|--------|----------------|----------------|
| electron-updater | Entire desktop app (Electron shell + bundled PyInstaller backend) | `desktop/package.json` version (currently `0.2.23`) |
| pip update | Only the Python `cachibot` package in the environment | `pyproject.toml` version (currently `0.2.0` in source) |

**In the desktop app, the pip update path is dead code.** The bundled PyInstaller binary does not have pip. The pip update endpoints still exist on the server but:
- The UI (UpdateBanner, UpdateDialog) is hidden in Electron mode
- The PipUpdatesSection is replaced by ElectronUpdatesSection
- Even if triggered via API, `pip install` would fail inside a frozen binary

### 3.2 Version Sync Problem

There are **three separate version numbers**:

| Location | Current Value | Purpose |
|----------|---------------|---------|
| `desktop/package.json` version | `0.2.23` | Electron app version, used by electron-updater |
| `pyproject.toml` version | `0.2.0` | Python package version, used by pip/PyPI |
| `VERSION` file (repo root) | `0.2.34` | Written by CI, read as fallback by `__init__.py` |

The CI workflow (`publish.yml`) attempts to sync these:
1. `mathieudutour/github-tag-action` bumps and creates a new version tag
2. The new version is written to `VERSION` file and `pyproject.toml` is patched via `sed`
3. `desktop/package.json` is patched with `npm version` in the build-desktop job

**But locally, these are permanently out of sync.** The source `pyproject.toml` says `0.2.0`, the VERSION file says `0.2.34`, and `desktop/package.json` says `0.2.23`. Only CI builds produce a coherent version.

### 3.3 What Happens If Someone Updates Pip But Not Electron (or Vice Versa)

- **Pip update only**: Not possible in desktop mode (PyInstaller binary, no pip).
- **Electron update only**: The entire app (including bundled backend) is replaced. This is the only valid desktop update path.
- **Pip update in server mode**: Works correctly for `pip install cachibot` users who run the server standalone.

---

## 4. Issues Found

### CRITICAL

1. **Publish config repo case mismatch**: `desktop/package.json` `build.publish.repo` is `"cachibot"` (lowercase) but the actual GitHub repo is `CachiBot` (mixed case). GitHub URLs are case-insensitive for web, but `electron-updater` generates API URLs like `https://api.github.com/repos/jhd3197/cachibot/releases/latest` which may not resolve correctly depending on GitHub's API behavior. This should be verified and corrected to `"CachiBot"` to match the actual repo name.

2. **No code signing**: The CI builds Electron apps with `CSC_IDENTITY_AUTO_DISCOVERY: false` and explicitly unsets `CSC_LINK`. On Windows, unsigned NSIS installers trigger SmartScreen warnings. On macOS, unsigned apps are blocked by Gatekeeper. **electron-updater will also refuse to install unsigned updates on macOS** because the app's signature cannot be verified.

3. **No `latest.yml` verification**: electron-updater relies on `latest.yml` / `latest-mac.yml` / `latest-linux.yml` files being uploaded to the GitHub release as artifacts. The `electron-builder --publish always` command should produce these, but there is no verification step in CI that confirms they were uploaded. If they are missing, update checks will silently fail.

### HIGH

4. **Update error is invisible to user**: When `autoUpdater.on('error')` fires (line 405-407), it only logs to console. No IPC message is sent to the renderer. The user has no idea the update check failed, even if they triggered it manually from the tray. The Settings UI `handleCheck` has a `try/finally` but does not show an error toast.

5. **Version mismatch between pyproject.toml and desktop/package.json**: Locally, these are always out of sync. The pyproject version is `0.2.0` while desktop is `0.2.23`. This means local dev builds will have wrong versions. The health endpoint shows the Python `__version__`, while the Electron title bar uses `app.getVersion()` (from desktop/package.json). A user could see conflicting versions in different parts of the UI.

6. **Pip update endpoints are accessible in desktop mode**: While the UI hides the pip update controls, the REST API endpoints (`/api/update/check`, `/api/update/apply`) are still active. An API call to `/api/update/apply` would attempt `pip install` inside a PyInstaller bundle, which would fail unpredictably.

### MEDIUM

7. **No update channel support**: There is no beta/canary channel for the Electron updater. The pip system has `optIntoBeta` (pre-release support), but the Electron system has no equivalent. `autoUpdater.channel` is never set.

8. **No user setting to disable auto-updates**: The Electron auto-updater always checks on startup and every 6 hours. There is no toggle in Settings to disable this. The pip system has client-side rate limiting but no disable toggle either.

9. **Tray tooltip version may be stale**: `tray.setToolTip(`CachiBot v${app.getVersion()}`)` is set once at creation and never updated after an update is downloaded.

10. **Backend not gracefully stopped on all update paths**: `update:install` handler (line 466-472) calls `stopBackend()` then waits 1 second before `quitAndInstall()`. The 1-second delay is arbitrary and may not be enough for SQLite to flush on slow systems.

### LOW

11. **Periodic check interval mismatch**: The Electron main process checks every 6 hours. The pip update store checks every 1 hour. These should be aligned or at least documented as intentionally different.

12. **No differential/delta updates**: The NSIS full installer is downloaded every time. For a large app with a bundled Python backend, this could be 100+ MB per update.

---

## 5. Recommendations

### Short-Term (Fix Current System)

1. **Verify repo case in publish config**: Change `"repo": "cachibot"` to `"repo": "CachiBot"` in `desktop/package.json` to match the actual GitHub repository name exactly.

2. **Surface update errors to the user**: Add an IPC event `update:error` in `setupAutoUpdater()` and handle it in the renderer to show a toast notification.

3. **Disable pip update endpoints in desktop mode**: Check `CACHIBOT_DESKTOP` env var in the update routes and return 404 or a descriptive error when running inside Electron.

4. **Add CI verification for `latest.yml`**: After the electron-builder step in CI, verify that `latest.yml` (or platform-equivalent) was uploaded to the release.

### Medium-Term (Improve UX)

5. **Add auto-update toggle**: Add a setting in AppSettingsView to enable/disable auto-update checks. Store in electron-store or equivalent.

6. **Add update channel support**: Allow users to opt into beta channel via `autoUpdater.channel = 'beta'` in the Electron updater, mirroring the pip system's `optIntoBeta`.

7. **Unify version management**: Use a single source of truth (the `VERSION` file) and have both `pyproject.toml` and `desktop/package.json` derive their versions from it at build time. Currently, CI does this but local development does not.

8. **Show update notification in-app**: Beyond the Settings page, show a subtle notification badge or banner when an update is available (similar to what the pip UpdateBanner does, but for Electron).

### Long-Term (Architecture)

9. **Code signing**: Set up code signing for Windows (EV certificate) and macOS (Apple Developer ID) to eliminate SmartScreen/Gatekeeper warnings and enable secure auto-updates.

10. **Consider NSIS differential updates or `nsis-web` target**: To reduce download size for updates, use electron-builder's `nsis-web` target which supports differential downloads.

11. **Consolidate to a single update path per deployment mode**: Document clearly that desktop users get updates via electron-updater ONLY, and pip users get updates via pip ONLY. Consider removing the pip update service entirely from PyInstaller builds to avoid confusion.

---

## 6. File Reference

| File | Role |
|------|------|
| `desktop/package.json` | electron-updater dependency, publish config, Electron version |
| `desktop/main.js:373-417` | `setupAutoUpdater()` -- Electron auto-update logic |
| `desktop/main.js:442-472` | IPC handlers for update:check, update:download, update:install |
| `desktop/preload.js:22-35` | IPC bridge exposed to renderer |
| `frontend/src/vite-env.d.ts:8-47` | TypeScript types for ElectronAPI |
| `frontend/src/components/views/AppSettingsView.tsx:361-537` | Electron update UI |
| `frontend/src/components/views/AppSettingsView.tsx:540+` | Pip update UI |
| `frontend/src/components/common/UpdateBanner.tsx` | Pip update banner (hidden in Electron) |
| `frontend/src/components/dialogs/UpdateDialog.tsx` | Pip update dialog (hidden in Electron) |
| `frontend/src/stores/update.ts` | Pip update Zustand store |
| `frontend/src/api/client.ts:1271-1315` | Pip update API client |
| `src/cachibot/api/routes/update.py` | Pip update REST endpoints |
| `src/cachibot/services/update_service.py` | Full pip update service (check, install, verify, rollback, repair) |
| `src/cachibot/__init__.py:15-35` | Version resolution logic |
| `.github/workflows/publish.yml` | CI: tag, release, build, publish |
| `pyproject.toml` | Python package version (source: `0.2.0`) |
| `VERSION` | CI-written version file (currently `0.2.34`) |
