# Python Backend Packaging Review (PyInstaller)

> **Reviewer:** Mariana (PyInstaller Specialist)
> **Date:** 2026-02-18
> **Scope:** How the CachiBot Python backend is bundled for the Electron desktop app

---

## 1. Packaging Method and Architecture

### Bundling Tool: PyInstaller (--onefile mode)

The Python backend is packaged into a **single self-extracting executable** (`cachibot-server.exe` / `cachibot-server`) using PyInstaller's `--onefile` mode. At runtime, PyInstaller extracts the entire Python runtime, all dependencies, and data files to a temporary directory (`_MEIPASS`), then executes the entry point.

### Entry Point

**File:** `desktop/pyinstaller-server.py`

This is a lightweight entry point that bypasses the Typer CLI. It uses `argparse` directly (to avoid bundling Typer/Rich) and imports only what's needed for the server:

```python
import uvicorn
from cachibot.api.server import create_app
app = create_app(workspace=Path.home())
uvicorn.run(app, host=args.host, port=args.port, log_level="info")
```

### Spec File

**File:** `cachibot-server.spec` (root of repo)

The spec file configures:
- **datas:** Bundles `cachibot` as `cachibot`, `frontend/dist` as `cachibot/frontend_dist`, and `VERSION` as `cachibot/VERSION`
- **hiddenimports:** `uvicorn.logging`, `uvicorn.loops.auto`, `uvicorn.protocols.http.auto`, `uvicorn.protocols.websockets.auto`, `uvicorn.lifespan.on`, `asyncpg`, `aiosqlite`, `sqlite_vec`, `fastembed`, `cachibot.api.routes`, `cachibot.plugins`, `cachibot.services`, `cachibot.storage`
- **UPX:** Enabled (`upx=True`) for compression
- **Console mode:** `console=True` (the binary is a headless server)

### Build Trigger

The spec file is **NOT used in CI**. The GitHub Actions workflow (`publish.yml`, job `build-backend`) invokes PyInstaller via command-line flags that mirror the spec file. The spec file appears to be for **local development builds only**.

---

## 2. Electron-Python Bridge Architecture

### How Electron Launches Python

**File:** `desktop/main.js`, `getBackendCommand()` (line 32-41)

| Mode | Command | Details |
|------|---------|---------|
| **Dev** | `cachibot server --port 5870` | Uses `shell: true` to resolve PATH; expects `pip install -e .` |
| **Production** | `{resourcesPath}/backend/cachibot-server[.exe] --port 5870` | PyInstaller binary from `extraResources` |

Electron spawns the backend as a **child process** via `child_process.spawn()`.

### Communication Protocol

- **HTTP REST + WebSocket** on `http://127.0.0.1:5870`
- No IPC or Unix sockets -- pure TCP/HTTP
- Electron loads the frontend from the backend URL (which serves both API and static files)

### Startup Sequence

1. Splash window shown
2. Backend process spawned
3. `waitForPort()` polls TCP port 5870 (up to 60 retries, 500ms delay = 30s max wait)
4. Detects early backend crash via `exit` event for fast-fail
5. On success: main window loads `http://127.0.0.1:5870`; splash closes
6. On failure: error dialog with last 10 lines of stderr

### Shutdown

- **Windows:** `taskkill /pid {pid} /T /F` to kill entire process tree (critical for PyInstaller's temp extraction)
- **macOS/Linux:** `process.kill()` (SIGTERM)
- Graceful shutdown on `before-quit` and `window-all-closed` events
- Before auto-update install: backend stopped with 1s delay for SQLite flush

### No-Python Scenario

The production build is **fully self-contained**. The PyInstaller binary includes the Python 3.12 runtime. No system Python installation is required. In dev mode, the system Python with an editable install is expected.

---

## 3. Dependency Analysis

### Direct Dependencies (from pyproject.toml)

| Category | Packages | PyInstaller Impact |
|----------|----------|--------------------|
| **Core AI** | prompture, tukuy | MISSING from bundle (see Issues) |
| **API** | fastapi, uvicorn[standard], websockets | OK with hidden imports |
| **Database** | sqlalchemy[asyncio], aiosqlite, asyncpg, alembic, pgvector | aiosqlite/asyncpg hidden-imported |
| **Knowledge/ML** | fastembed, pymupdf, python-docx | fastembed pulls torch/scipy (see Issues) |
| **Platform SDKs** | aiogram, discord.py, slack-bolt/sdk, botbuilder-core/aiohttp, aiohttp | Heavy; all bundled |
| **Auth/Crypto** | bcrypt, PyJWT, cryptography | Native C extensions bundled |
| **Scheduling** | croniter | Pure Python, OK |
| **File handling** | aiofiles, python-multipart | Pure Python, OK |

### Transitive Heavy Dependencies (pulled by fastembed)

| Package | Approx. Size | Pulled By |
|---------|-------------|-----------|
| **torch + torchvision** | ~800MB-2GB | fastembed -> onnxruntime -> torch |
| **scipy** | ~100MB | fastembed |
| **numpy** | ~50MB | fastembed, scipy, torch |
| **onnxruntime** | ~150MB | fastembed |
| **huggingface_hub** | ~30MB | fastembed |
| **tokenizers** | ~10MB | fastembed |

### Hidden Import Coverage

The spec file and CI command include hidden imports for:
- uvicorn internals (5 modules)
- asyncpg, aiosqlite, sqlite_vec, fastembed
- cachibot.api.routes, cachibot.plugins, cachibot.services, cachibot.storage

**Missing hidden imports (not listed but needed):**
- `cachibot.telemetry` -- imported lazily in lifespan
- `cachibot.services.adapters` -- platform adapter subpackage
- `cachibot.storage.models` -- SQLAlchemy models subpackage
- `cachibot.storage.alembic` -- migration files (if DB migrations run at startup)
- `cachibot.scripts` -- scripts subpackage
- `cachibot.utils` -- utility subpackage

---

## 4. Issues Found

### CRITICAL

#### C1. Tukuy and Prompture Entirely Missing from Bundle

**Evidence:** `warn-cachibot-server.txt` lines 808-826, 850-851, 868

PyInstaller reports ALL tukuy submodules as missing:
- `tukuy.instruction`, `tukuy.plugins`, `tukuy.safety`, `tukuy.bridges`, `tukuy.skill`, `tukuy.manifest`, `tukuy.analysis`, `tukuy.sandbox`

And key prompture submodules:
- `prompture.skills`, `prompture.model_rates`

**Root Cause:** These are installed as editable packages (`pip install -e .`) in the local environment but PyInstaller cannot trace them because they are namespace packages or installed from local paths that PyInstaller does not follow.

**Impact:** The bundled binary will crash on any code path that imports tukuy or these prompture modules. Since `cachibot.plugins.base` imports `tukuy.plugins` at the top level, and `cachibot.agent` imports `tukuy` at the top level, the **server will fail to start at all** in the bundled binary.

**Fix:** Add `--hidden-import` entries for all tukuy and prompture submodules, OR use `--collect-all tukuy --collect-all prompture` in the PyInstaller command. Also ensure that CI installs both packages (not just cachibot's pip install which may resolve them from PyPI).

#### C2. Binary Size is 2.6 GB (Windows)

**Evidence:** `dist/cachibot-server.exe` = 2.6 GB; `build/cachibot-server/cachibot-server.pkg` = 2.7 GB

The `--onefile` binary is enormous due to:
1. **torch/torchvision** (~1-2 GB): Pulled transitively by `fastembed`
2. **scipy** (~100 MB): Pulled by fastembed
3. **onnxruntime** (~150 MB): Core fastembed dependency
4. **Platform SDKs** (discord.py, botbuilder, aiogram, slack): ~50 MB combined
5. **playwright** (PyInstaller hook detected): May pull browser binaries

This makes the Electron installer likely **3+ GB**, which is unacceptable for distribution.

#### C3. Spec File and CI Build Divergence

**Evidence:** `cachibot-server.spec` uses `pathex=[]`, `binaries=[]`, and references `desktop\pyinstaller-server.py` (backslash = Windows). The CI workflow in `publish.yml` uses inline `pyinstaller` flags, not the spec file.

- The spec file is only for local Windows builds
- CI builds use `pyinstaller --onefile ...` with similar but potentially divergent flags
- Changes to one are not automatically reflected in the other
- There is no test that validates the built binary works

### MAJOR

#### M1. `--onefile` Mode Causes Slow Startup

With `--onefile`, PyInstaller must extract the entire 2.6 GB payload to a temporary directory on every launch. This adds **10-30+ seconds** of startup time before the Python process even begins executing. Combined with Electron's 30-second port timeout (`waitForPort` with 60 retries at 500ms), the app may **time out and show an error dialog** on first launch or on slow disks.

**Recommendation:** Switch to `--onedir` mode. The backend directory would be placed in `extraResources/backend/` and launched directly. No extraction overhead.

#### M2. Incomplete Hidden Imports for cachibot Subpackages

The current hidden imports only list top-level packages:
```
--hidden-import=cachibot.api.routes
--hidden-import=cachibot.plugins
--hidden-import=cachibot.services
--hidden-import=cachibot.storage
```

This does NOT recursively include submodules. PyInstaller's `--hidden-import` only imports the named module, not its children. Missing:
- `cachibot.api.routes.webhooks.*` (5 webhook modules)
- `cachibot.services.adapters.*` (10 adapter modules)
- `cachibot.storage.models.*` (ORM models)
- `cachibot.telemetry.*` (3 modules)
- `cachibot.scripts.*`
- `cachibot.utils.*`
- All individual route modules (30+ files)

**Fix:** Use `--collect-submodules cachibot` or `--collect-all cachibot`.

#### M3. Both cpython-311 and cpython-312 .pyc Files Bundled

**Evidence:** The Analysis TOC shows both `.cpython-311.pyc` and `.cpython-312.pyc` files being included for every module in the `--add-data cachibot:cachibot` directive.

Since the CI builds with Python 3.12, the `.cpython-311.pyc` files are **dead weight**. The `--add-data` for `cachibot` copies the raw source tree, including all `__pycache__` directories.

**Fix:** Either clean `__pycache__` before building, or use a more targeted data inclusion that excludes `.pyc` files.

#### M4. No PyInstaller Excludes Configured

The spec file has `excludes=[]`. The CI command has no `--exclude-module` flags. This means PyInstaller bundles everything it can trace, including:
- **pytest** and test utilities (pulled by some packages)
- **setuptools** and **pip** (build tools not needed at runtime)
- **gunicorn** (pulled by uvicorn[standard], not needed since uvicorn runs directly)
- **playwright** (detected hook but not a CachiBot dependency)
- **fontTools** (pulled by pymupdf, significant size)

### MINOR

#### m1. UPX Compression on Windows Has Limited Effect

UPX is enabled (`upx=True`) but many Windows DLLs (especially from torch/numpy) cannot be compressed by UPX because they are signed or have specific PE characteristics. UPX on Python binaries can also cause false positives with antivirus software.

#### m2. No `--strip` on Linux/macOS Builds

The spec file has `strip=False`. On Linux/macOS, stripping debug symbols from shared libraries (`.so`/`.dylib`) can reduce binary size by 10-30%.

#### m3. Local Build Uses Python 3.11.7, CI Uses 3.12

The local build environment (evidenced by `pyenv` paths in `Analysis-00.toc`) uses Python 3.11.7, while CI uses Python 3.12. This version mismatch could cause:
- Different behavior in bundled binaries
- Missing modules if packages have version-specific code paths

#### m4. No `--clean` Flag in CI Build

Without `--clean`, PyInstaller may use cached analysis from previous builds, leading to stale module detection if dependencies change between releases.

#### m5. macOS Entitlements Not Referenced in electron-builder Config

The `build/entitlements.mac.plist` file exists but is not referenced in `desktop/package.json`'s build config under the `mac` section. Without explicit `entitlements` and `hardenedRuntime` config, macOS builds may:
- Fail Gatekeeper on Apple Silicon
- Be rejected by notarization

---

## 5. Size Optimization Opportunities

### Tier 1: Massive Impact (save 1-2 GB)

| Action | Est. Savings | Effort |
|--------|-------------|--------|
| **Exclude torch completely** via `--exclude-module torch --exclude-module torchvision` | ~1-2 GB | Low |
| **Replace fastembed with lighter alternative** (e.g., use API-based embeddings only, or fastembed CPU-only without torch) | ~1-2 GB | Medium |
| **Use `fastembed[cpu]` or pin onnxruntime-cpu** to avoid torch dependency | ~1-2 GB | Low |

### Tier 2: Significant Impact (save 100-300 MB)

| Action | Est. Savings | Effort |
|--------|-------------|--------|
| **Exclude playwright** | ~50-200 MB | Low |
| **Exclude scipy if not directly used** | ~100 MB | Low |
| **Switch to `--onedir`** (no self-extraction overhead, smaller download due to deduplication) | Variable | Low |
| **Use `--exclude-module gunicorn`** | ~10 MB | Low |
| **Use `--exclude-module setuptools --exclude-module pip`** | ~20 MB | Low |

### Tier 3: Moderate Impact (save 10-50 MB)

| Action | Est. Savings | Effort |
|--------|-------------|--------|
| **Clean __pycache__ before build** | ~5-10 MB | Low |
| **Exclude test modules** (pytest, _pytest) | ~10 MB | Low |
| **Use `--strip` on Linux/macOS** | ~20-50 MB | Low |
| **Remove fontTools if not needed** (or use pymupdf lightweight) | ~20 MB | Medium |

### Realistic Target

With Tier 1 + Tier 2 optimizations, the binary could realistically shrink from **2.6 GB to 200-400 MB**, which is a reasonable size for an Electron + Python desktop app.

---

## 6. Build Pipeline Flow

```
publish.yml (on push to main)
  |
  v
[Job 1: release]
  - Bump version tag
  - Build & publish to PyPI
  |
  v
[Job 2: build-backend] (3 platforms in parallel)
  - Checkout at version tag
  - Build frontend (npm ci && npm run build)
  - pip install -e . && pip install pyinstaller
  - pyinstaller --onefile ... desktop/pyinstaller-server.py
  - Upload artifact: dist/cachibot-server*
  |
  v
[Job 3: build-desktop] (3 platforms in parallel)
  - Download backend artifact to build/backend/
  - chmod +x (non-Windows)
  - electron-builder --{platform} --publish always
    -> Bundles backend binary into extraResources/backend/
    -> Uploads installer to GitHub Release
  |
  v
[Job 4: update-release]
  - Patch release body with actual asset sizes
```

### Platform Coverage

| Platform | Runner | Backend Binary | Installer Format |
|----------|--------|----------------|-----------------|
| Windows | windows-latest | `cachibot-server.exe` | NSIS `.exe` |
| macOS | macos-latest | `cachibot-server` | `.dmg` + `.zip` |
| Linux | ubuntu-latest | `cachibot-server` | `.AppImage` + `.deb` |

---

## 7. Recommendations

### P0 (Blockers -- must fix before shipping)

1. **Add `--collect-all tukuy --collect-all prompture`** to both the spec file and CI pyinstaller command. Without these, the bundled app will crash immediately on startup.

2. **Add `--collect-submodules cachibot`** to ensure all subpackages (adapters, webhooks, telemetry, etc.) are included recursively.

3. **Add exclusions to shed torch/torchvision**: `--exclude-module torch --exclude-module torchvision --exclude-module scipy`. Verify fastembed works with `onnxruntime` alone (it should for CPU inference).

### P1 (High priority -- significantly improves quality)

4. **Switch from `--onefile` to `--onedir`** to eliminate the 10-30s extraction penalty on startup. Adjust `desktop/package.json` `extraResources` to point to the directory instead of a single binary. Update `getBackendCommand()` in `main.js` accordingly.

5. **Unify spec file and CI command**. Either use the spec file in CI (`pyinstaller cachibot-server.spec`) or remove the spec file entirely and keep a single source of truth (the CI command). Recommend using the spec file since it's more maintainable.

6. **Add `--exclude-module` entries** for: `gunicorn`, `playwright`, `setuptools`, `pip`, `pytest`, `_pytest`, `fontTools` (if pymupdf doesn't need it at runtime).

7. **Add `--clean` flag** to CI PyInstaller invocation to prevent stale caches.

### P2 (Medium priority -- nice to have)

8. **Clean `__pycache__`** from `cachibot` before building to avoid bundling stale `.pyc` files.

9. **Enable `--strip`** on Linux and macOS builds for smaller binaries.

10. **Add a smoke test** in CI after the PyInstaller build: `./dist/cachibot-server --help` or a quick HTTP health check to verify the binary actually starts.

11. **Reference macOS entitlements** in electron-builder config:
    ```json
    "mac": {
      "hardenedRuntime": true,
      "entitlements": "../build/entitlements.mac.plist",
      "entitlementsInherit": "../build/entitlements.mac.plist"
    }
    ```

12. **Standardize Python version** between local dev (3.11.7) and CI (3.12).

### P3 (Low priority -- optimization)

13. **Investigate fastembed alternatives** that don't pull in the full ML stack (torch, scipy). For a desktop app, API-based embeddings or a lighter local model may be more appropriate.

14. **Consider `--onedir` with NSIS directory packaging** instead of `--onefile` to avoid the temp-extraction overhead entirely while keeping a clean install.

15. **Disable UPX on Windows** to avoid antivirus false positives. Keep it for Linux/macOS only.

---

## 8. Summary of Current State

| Aspect | Status | Notes |
|--------|--------|-------|
| Bundling method | PyInstaller --onefile | Works but has major size/startup issues |
| Python runtime | Bundled (no system Python needed) | Correct approach |
| Core dependencies | Partially captured | tukuy/prompture MISSING (critical) |
| Submodule coverage | Incomplete | Many cachibot subpackages not hidden-imported |
| Binary size | 2.6 GB (Windows) | Unacceptable; torch is main culprit |
| Startup time | 10-30s extraction + 3-5s server boot | --onedir would fix extraction delay |
| CI/local parity | Diverged | Spec file vs CLI flags; Python 3.11 vs 3.12 |
| Platform support | Win/Mac/Linux | macOS entitlements not wired into builder |
| Smoke test | None | No validation that built binary actually works |
