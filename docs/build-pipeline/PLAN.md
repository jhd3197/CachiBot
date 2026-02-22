# Build Pipeline Action Plan

> **Synthesized:** 2026-02-18
> **Source docs:** [version-system.md](version-system.md) | [electron-config.md](electron-config.md) | [update-system.md](update-system.md) | [ci-cd-review.md](ci-cd-review.md) | [python-packaging.md](python-packaging.md) | [distribution-strategy.md](distribution-strategy.md)

---

## Summary Table

| Priority | Issue | Fix | Effort | Status |
|----------|-------|-----|--------|--------|
| **P0** | PyInstaller missing tukuy/prompture -- binary crashes on startup | Add `--collect-all tukuy --collect-all prompture` to PyInstaller command | 1 hour | Not started |
| **P0** | PyInstaller missing cachibot submodules (adapters, webhooks, telemetry) | Add `--collect-submodules cachibot` to PyInstaller command | 1 hour | Not started |
| **P0** | Binary size is 2.6 GB due to torch/scipy | Exclude torch, torchvision, scipy from PyInstaller build | 2 hours | Not started |
| **P0** | Version shows "0.0.0-unknown" in desktop app | Add `--copy-metadata cachibot` to PyInstaller + make pyproject.toml use dynamic version from VERSION file | 2 hours | Partially started (daf1162) |
| **P1** | No single instance lock -- duplicate Electron windows cause port conflict | Add `app.requestSingleInstanceLock()` to main.js | 1 hour | Not started |
| **P1** | PyInstaller `--onefile` causes 10-30s startup extraction delay | Switch to `--onedir` mode and update Electron extraResources path | 3 hours | Not started |
| **P1** | No code signing -- macOS blocks app, Windows shows SmartScreen | Purchase Apple Dev cert + Windows EV cert; configure in CI | 2-3 days | Not started |
| **P1** | Spec file and CI PyInstaller command have diverged | Unify to a single spec file used in both local and CI builds | 2 hours | Not started |
| **P1** | No CI gate before release -- broken code can ship to PyPI | Add branch protection requiring CI pass, or add `needs: ci` in publish.yml | 1 hour | Not started |
| **P1** | Frontend has zero CI validation -- no lint, build, or type check | Add `npm run build` + `npm run lint` steps to ci.yml | 1 hour | Not started |
| **P1** | Pip update endpoints still accessible in Electron (could break PyInstaller binary) | Disable `/api/update/apply` when `CACHIBOT_DESKTOP=true` | 1 hour | Not started |
| **P1** | `dev.yml` bot-ignore logic is broken -- `exit 0` only exits the step | Use job-level `if` condition instead of step `exit 0` | 30 min | Not started |
| **P2** | macOS builds may be ARM64-only, not Universal as advertised | Add explicit `"arch": ["universal"]` to electron-builder mac config | 2 hours | Not started |
| **P2** | No Content-Security-Policy in Electron shell | Add CSP via `session.defaultSession.webRequest.onHeadersReceived` | 1 hour | Not started |
| **P2** | Electron URL check in `setWindowOpenHandler` is bypassable | Parse URL and compare hostname instead of `url.includes()` | 30 min | Not started |
| **P2** | No `will-navigate` handler -- main window could navigate to external sites | Add `will-navigate` event handler | 30 min | Not started |
| **P2** | No auto-update toggle for users | Add enable/disable setting in AppSettingsView | 2 hours | Not started |
| **P2** | electron-updater repo name case mismatch ("cachibot" vs "CachiBot") | Change to `"CachiBot"` in desktop/package.json publish config | 10 min | Not started |
| **P2** | Update errors invisible to user -- only logged to console | Add `update:error` IPC event to surface errors in renderer | 1 hour | Not started |
| **P2** | Frontend built 4 times per release (redundant) | Build once, share as artifact across jobs | 2 hours | Not started |
| **P2** | mypy not run in CI despite being configured | Add `mypy src/cachibot` step to ci.yml | 30 min | Not started |
| **P2** | Inconsistent `actions/setup-python` versions (v4 vs v5) | Standardize all to `@v5` | 15 min | Not started |
| **P3** | Non-Windows backend shutdown may orphan uvicorn workers | Use process groups on Linux/macOS | 1 hour | Not started |
| **P3** | `sendSync` for app version blocks renderer | Replace with async approach or preload constant | 1 hour | Not started |
| **P3** | Cache-clearing logic duplicated 3 times in main.js | Extract into shared function | 30 min | Not started |
| **P3** | No RPM target for Linux | Add RPM to electron-builder config | 30 min | Not started |
| **P3** | No beta channel for Electron updates | Implement `autoUpdater.channel = 'beta'` | 2 hours | Not started |

---

## P0: Fix Now (Ship-Blocking Issues)

### 1. PyInstaller Cannot Bundle tukuy/prompture

**Root cause:** PyInstaller cannot trace editable-installed namespace packages. The entire tukuy and prompture libraries are missing from the frozen binary, causing an **immediate crash on startup** when any tukuy import is hit.

**Files to change:**
- `.github/workflows/publish.yml` -- "Build backend binary" step (~line 212)
- `cachibot-server.spec` -- `hiddenimports` list

**Exact change (CI command):**
```
Add to the pyinstaller invocation:
  --collect-all tukuy
  --collect-all prompture
  --collect-submodules cachibot
```

**Exact change (spec file):**
```python
# Add to Analysis() call:
collect_all('tukuy')
collect_all('prompture')
collect_submodules('cachibot')
```

**Effort:** 1 hour
**Risk:** Low -- adds more files to the bundle, increases size, but guarantees correct module resolution.
**Cross-ref:** [python-packaging.md](python-packaging.md) C1, M2

### 2. Binary Size is 2.6 GB (Unshippable)

**Root cause:** `fastembed` transitively pulls `torch`, `torchvision`, and `scipy` which together add ~1.5-2 GB. These are not needed at runtime -- fastembed uses `onnxruntime` directly for CPU inference.

**Files to change:**
- `.github/workflows/publish.yml` -- "Build backend binary" step
- `cachibot-server.spec`

**Exact change:**
```
Add to pyinstaller invocation:
  --exclude-module torch
  --exclude-module torchvision
  --exclude-module scipy
  --exclude-module playwright
  --exclude-module gunicorn
  --exclude-module setuptools
  --exclude-module pip
  --exclude-module pytest
  --exclude-module _pytest
```

**Expected result:** Binary shrinks from 2.6 GB to approximately 200-400 MB.
**Effort:** 2 hours (includes testing fastembed works without torch)
**Risk:** Medium -- must verify fastembed's embedding models still load correctly with onnxruntime-only. If fastembed hard-requires torch, consider using `fastembed[cpu]` or an API-based embedding approach.
**Cross-ref:** [python-packaging.md](python-packaging.md) C2, Section 5

### 3. Version Shows "0.0.0-unknown"

**Root cause (chain of failures):**
1. `importlib.metadata.version("cachibot")` fails in PyInstaller because `.dist-info` is not bundled.
2. The VERSION file fallback works **if** it's correctly bundled at `_MEIPASS/cachibot/VERSION`.
3. If the VERSION file is missing or empty, the final fallback returns `"0.0.0-unknown"`.
4. Until commit `daf1162` (unreleased, on `dev`), the Settings page never used `app.getVersion()` -- only the backend response.
5. `pyproject.toml` hardcodes `version = "0.2.0"`, meaning local editable installs report the wrong version too.

**Fix -- belt and suspenders:**

**Fix A (PyInstaller metadata):**
Add `--copy-metadata cachibot` to the PyInstaller command so `importlib.metadata` works in frozen binaries.

**Fix B (Dynamic version in pyproject.toml):**
Change `pyproject.toml` from static to dynamic versioning:
```toml
# REMOVE:
version = "0.2.0"

# ADD:
dynamic = ["version"]

# ADD to [tool.hatch.version]:
[tool.hatch.version]
path = "VERSION"
pattern = "(?P<version>.+)"
```

This makes `pip install -e .` read the VERSION file, so `importlib.metadata` returns the correct version in local dev too.

**Fix C (already in progress):**
Commit `daf1162` adds `window.electronAPI?.appVersion` as the primary version source in the Settings UI. This needs to ship in the next release.

**Files to change:**
- `pyproject.toml` lines 5-7
- `.github/workflows/publish.yml` -- add `--copy-metadata cachibot`
- `cachibot-server.spec` -- add copy_metadata
- Already on `dev`: `frontend/src/components/views/AppSettingsView.tsx` (commit daf1162)

**Effort:** 2 hours
**Risk:** Low. Dynamic versioning is a standard hatchling feature.
**Cross-ref:** [version-system.md](version-system.md), [ci-cd-review.md](ci-cd-review.md) Section 4

---

## P1: Fix Next (High-Impact Issues)

### 4. No Single Instance Lock

Multiple CachiBot windows can be opened simultaneously, each trying to bind to port 5870. The second instance's backend fails, showing an error dialog.

**File:** `desktop/main.js` -- add before `app.whenReady()`:
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

**Effort:** 1 hour
**Cross-ref:** [electron-config.md](electron-config.md) C1

### 5. Switch PyInstaller from `--onefile` to `--onedir`

`--onefile` extracts the entire 2.6 GB payload to a temp directory on every launch, adding 10-30 seconds of startup time. With `--onedir`, the backend directory is placed directly in `extraResources/backend/` and launched without extraction.

**Files to change:**
- `.github/workflows/publish.yml` -- change `--onefile` to `--onedir` in build-backend
- `desktop/package.json` -- update `extraResources` from path to match new directory structure
- `desktop/main.js` `getBackendCommand()` -- update binary path if directory structure changes
- `cachibot-server.spec` -- remove `a.binaries + a.datas` from EXE (standard `--onedir` config)

**Effort:** 3 hours
**Risk:** Medium -- changes the artifact structure that electron-builder expects. Must test on all 3 platforms.
**Cross-ref:** [python-packaging.md](python-packaging.md) M1

### 6. Code Signing

Without code signing, macOS blocks the app outright (Gatekeeper), and Windows shows SmartScreen warnings. This is the single biggest barrier to professional distribution.

**Requirements:**
- **macOS:** Apple Developer Program ($99/year). Create a "Developer ID Application" certificate. Configure `electron-builder` with `CSC_LINK` (p12 file) and `CSC_KEY_PASSWORD`. Enable `hardenedRuntime: true` and reference `build/entitlements.mac.plist`. Set up Apple notarization via `afterSign` hook.
- **Windows:** Standard code signing certificate (DigiCert, Sectigo, ~$200-400/year for standard; $300-700/year for EV which removes SmartScreen immediately). Configure `WIN_CSC_LINK` and `WIN_CSC_KEY_PASSWORD` in CI secrets.

**Files to change:**
- `.github/workflows/publish.yml` -- add signing env vars, remove the `unset CSC_LINK` line
- `desktop/package.json` -- add `hardenedRuntime`, `entitlements`, `entitlementsInherit` under `mac`
- GitHub repo settings -- add secrets for CSC_LINK, CSC_KEY_PASSWORD, APPLE_ID, etc.

**Effort:** 2-3 days (includes certificate procurement, CI configuration, and testing)
**Cross-ref:** [electron-config.md](electron-config.md) C2, [update-system.md](update-system.md) Critical #2

### 7. Unify Spec File and CI Build

The `cachibot-server.spec` file (local builds) and the inline `pyinstaller` flags in CI are diverging. Changes to one are not reflected in the other.

**Recommendation:** Use the spec file in CI:
```yaml
- name: Build backend binary
  run: pyinstaller cachibot-server.spec
```

Update the spec file to be cross-platform (replace `\\` with `os.path.join()`). Remove the inline flags from `publish.yml`.

**Effort:** 2 hours
**Cross-ref:** [python-packaging.md](python-packaging.md) C3

### 8. CI Safety: Gate Release on Tests

The `publish.yml` workflow triggers on push to `main` without requiring CI to pass first. A broken commit could ship directly to PyPI.

**Fix options (pick one):**
- **Branch protection:** Require `ci.yml` status checks to pass before merging to `main` (GitHub repo settings).
- **Workflow dependency:** Add `lint` and `test` jobs to `publish.yml` with `needs: [lint, test]` on the `release` job.

**Also fix `dev.yml`:** The bot-ignore step uses `exit 0` which only exits that step, not the job. Change to job-level `if: github.actor != 'github-actions[bot]'` on the job itself.

**Effort:** 1 hour
**Cross-ref:** [ci-cd-review.md](ci-cd-review.md) Critical #2, Major #7

### 9. Add Frontend CI Validation

The frontend (React+TypeScript) has zero validation in CI. A broken frontend ships to users undetected.

**File:** `.github/workflows/ci.yml` -- add a new job:
```yaml
frontend:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with: { node-version: '20' }
    - name: Install
      working-directory: frontend
      run: npm ci
    - name: Lint
      working-directory: frontend
      run: npm run lint
    - name: Build
      working-directory: frontend
      run: npm run build
```

**Effort:** 1 hour
**Cross-ref:** [ci-cd-review.md](ci-cd-review.md) Critical #3

### 10. Disable Pip Self-Update in Desktop Mode

The pip update endpoints (`/api/update/apply`) are still accessible in Electron mode. Running `pip install` inside a PyInstaller binary would fail unpredictably.

**File:** `src/cachibot/api/routes/update.py`

Add a guard to `apply_update()`:
```python
import os
if os.environ.get("CACHIBOT_DESKTOP", "").lower() == "true":
    return UpdatePerformResponse(success=False, message="Updates are managed by the desktop app")
```

**Effort:** 1 hour
**Cross-ref:** [distribution-strategy.md](distribution-strategy.md) Section 3.4, [update-system.md](update-system.md) High #6

---

## P2: Fix Later (Quality & Hardening)

### 11. macOS Architecture

The `desktop/package.json` mac config does not specify `arch`. Since `macos-latest` is ARM64, builds are likely ARM64-only despite release notes claiming "Universal".

**Fix:** Add `"arch": ["universal"]` to mac targets in `desktop/package.json`. This also requires the PyInstaller backend to be built for both architectures (or as a universal binary).

**Effort:** 2 hours (may require separate macOS x64 and arm64 CI runners for PyInstaller)
**Cross-ref:** [electron-config.md](electron-config.md) M1

### 12. Electron Security Hardening

- Add Content-Security-Policy via `session.defaultSession.webRequest.onHeadersReceived`
- Add `will-navigate` handler to prevent navigation to external sites
- Fix `setWindowOpenHandler` URL check -- parse URL and compare hostname
- Set `sandbox: true` explicitly in webPreferences
- Add `setPermissionRequestHandler` to deny camera/mic/geolocation

**Effort:** 2 hours total
**Cross-ref:** [electron-config.md](electron-config.md) M2-M4

### 13. electron-updater Fixes

- Change `"repo": "cachibot"` to `"repo": "CachiBot"` in publish config to match actual GitHub repo name
- Surface update errors to the user via IPC (currently only logged to console)
- Add CI verification that `latest.yml` was uploaded after electron-builder
- Add auto-update disable toggle in Settings

**Effort:** 3 hours total
**Cross-ref:** [update-system.md](update-system.md) Critical #1, High #4

### 14. CI Optimizations

- Build frontend once, share as artifact (saves 3 redundant builds per release)
- Add npm caching via `actions/setup-node` with `cache: npm`
- Standardize all `actions/setup-python` to `@v5`
- Add concurrency groups to `publish.yml` and `dev.yml`
- Remove `npm ci || npm install` fallback -- use `npm ci` only
- Add `mypy src/cachibot` to ci.yml
- Add `--clean` flag to PyInstaller CI invocations
- Clean `__pycache__` before PyInstaller builds

**Effort:** 3 hours total
**Cross-ref:** [ci-cd-review.md](ci-cd-review.md) Sections 8-10

### 15. PyInstaller Size -- Additional Exclusions

Beyond the P0 torch exclusion, add:
- `--exclude-module fontTools` (if pymupdf works without it)
- `--strip` on Linux/macOS builds
- Disable UPX on Windows (causes antivirus false positives)

**Effort:** 1 hour
**Cross-ref:** [python-packaging.md](python-packaging.md) Section 5

---

## P3: Future Improvements

### 16. Process Management
- Use process groups on Linux/macOS to kill uvicorn workers cleanly
- Replace `sendSync` for app version with async approach
- Extract cache-clearing logic into shared function (duplicated 3 times)

### 17. Distribution Enhancements
- Add RPM target for Fedora/RHEL Linux users
- Add beta channel for Electron updates
- Add `cachibot://` protocol handler for deep linking
- Consider NSIS differential/web updates for smaller download size
- Port conflict detection -- Electron should detect if 5870 is already in use

### 18. Documentation
- Add "How to Install" section to README with two clear paths (pip vs desktop)
- Document the two update paths clearly in the app and on the website
- Add `distribution: "pip" | "desktop"` field to `/api/health`

---

## Distribution Decision

**Keep both pip and Electron**, with clear boundaries:

| Concern | pip | Electron |
|---------|-----|----------|
| **Audience** | Developers, servers, Docker, CI | End users, desktop |
| **Update path** | `pip install --upgrade` / built-in API | electron-updater (GitHub Releases) |
| **CLI** | Full CLI (`cachibot`, `cachi`) | None (internal `cachibot-server` binary) |
| **Self-update UI** | Pip update dialog + banner | Electron update section in Settings |
| **Backend runtime** | Native Python (user's interpreter) | PyInstaller frozen binary |

The maintenance cost of dual distribution is real but manageable. The build pipeline already handles both. The key changes needed to enforce separation are:
1. Disable pip update endpoints in desktop mode (P1 item #10)
2. Frontend detects distribution mode via health endpoint `desktop` flag (already works)
3. Document the two channels clearly

**Cross-ref:** [distribution-strategy.md](distribution-strategy.md) Sections 5-7

---

## Version Unification

**Single source of truth: git tags, materialized as the `VERSION` file.**

| Consumer | How It Gets the Version |
|----------|------------------------|
| `pyproject.toml` | Dynamic version via `[tool.hatch.version]` reading `VERSION` file |
| `desktop/package.json` | CI runs `npm version $(cat VERSION) --no-git-tag-version` |
| Python runtime | `importlib.metadata` (after `--copy-metadata`) or VERSION file fallback |
| PyInstaller binary | `--copy-metadata cachibot` + `--add-data VERSION:cachibot` |
| Electron `app.getVersion()` | Reads `desktop/package.json` (set by CI) |

**Stop committing VERSION back to main from CI** -- it creates race conditions and the `|| true` silently swallows failures. Instead, accept that the VERSION file in the repo represents the last-released version and CI overrides it at build time.

**Cross-ref:** [version-system.md](version-system.md), [distribution-strategy.md](distribution-strategy.md) Section 6

---

## Execution Order

```
Week 1 (P0):
  1. Fix PyInstaller hidden imports (tukuy, prompture, cachibot submodules)
  2. Add torch/scipy exclusions to shrink binary
  3. Fix version system (dynamic pyproject.toml + --copy-metadata)
  4. Ship daf1162 (Electron appVersion fallback already on dev)

Week 2 (P1 -- critical):
  5. Add single instance lock
  6. Switch to --onedir
  7. Unify spec file with CI
  8. Add CI gate + fix dev.yml bot logic
  9. Add frontend CI validation
  10. Disable pip update in desktop mode

Week 3-4 (P1 -- signing):
  11. Procure Apple Developer cert + Windows signing cert
  12. Configure code signing in CI
  13. Test signed builds on all platforms

Month 2 (P2):
  14. Electron security hardening
  15. electron-updater fixes
  16. CI optimizations
  17. macOS universal builds
  18. Additional PyInstaller size optimizations
```
