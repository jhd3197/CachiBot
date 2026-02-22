# Version System Analysis: Why the App Shows "0.0.0-unknown"

## Summary of Root Cause

The version displayed in the Settings page of the desktop app comes from the **Python backend's `/health` endpoint**, which reads `cachibot.__version__`. In a PyInstaller-frozen binary, `importlib.metadata.version("cachibot")` fails (metadata not bundled), and the VERSION file fallback depends on the file being correctly placed at `_MEIPASS/cachibot/VERSION`. There are **two compounding issues**:

1. **The VERSION file inside the git tag is stale.** The CI creates the git tag BEFORE committing the updated VERSION file. When `build-backend` checks out the tag, the VERSION file contains the PREVIOUS release version. The job patches this by writing the correct version before building, so this alone does not cause "0.0.0-unknown" -- but it creates fragility.

2. **`importlib.metadata` does not work in PyInstaller one-file binaries.** The editable install's `.dist-info` metadata is not bundled by PyInstaller. The VERSION file fallback is the only path that works, and any failure in the file bundling chain causes the final `"0.0.0-unknown"` fallback to trigger.

3. **Until commit `daf1162` (unreleased, on `dev`), the Settings page only showed `healthInfo?.version`** -- the backend version. The recently added `window.electronAPI?.appVersion` fallback has never been in a released build. So for every shipped desktop release, the version on-screen was whatever the PyInstaller backend reported.

## Full Version Flow Trace

### 1. Source of Truth: `VERSION` file (repo root)

- **File**: `/VERSION` (repo root)
- **Current value**: `0.2.34` (on `dev` branch), `0.2.56` (on `main`)
- **Updated by**: GitHub Actions `publish.yml`, step "Update VERSION file" (line 38-45)
- **Also in**: `/pyproject.toml` line 7 (hardcoded `"0.2.0"`, only updated in CI memory)

### 2. Build Step: CI Tag + PyInstaller

**`publish.yml` `release` job** (lines 26-45):
1. `mathieudutour/github-tag-action` creates tag `v0.2.X` on the current merge commit
2. A NEW commit is pushed to `main` with the updated VERSION file
3. **The tag points to the commit BEFORE the VERSION update**

**`publish.yml` `build-backend` job** (lines 157-237):
1. Checks out `ref: v${{ needs.release.outputs.new_version }}` -- the tag (stale VERSION)
2. Writes `echo "$VERSION" > VERSION` -- fixes the VERSION file locally (line 198)
3. Updates `pyproject.toml` with correct version via `sed` (lines 199-207)
4. Runs `pip install -e .` -- creates editable install with correct version in metadata
5. Runs PyInstaller with `--add-data "VERSION:cachibot"` (line 230)
6. PyInstaller bundles the corrected VERSION file into `_MEIPASS/cachibot/VERSION`

**`publish.yml` `build-desktop` job** (lines 242-295):
1. Checks out at tag (same as build-backend)
2. Runs `npm version $VERSION` to set `desktop/package.json` version (line 270)
3. Downloads backend binary from `build-backend` artifact
4. Builds Electron app with `electron-builder`

### 3. Bundled Artifact: PyInstaller Binary

The frozen binary (`cachibot-server.exe` / `cachibot-server`) contains:
- `/cachibot/__init__.py` (from `--add-data "cachibot:cachibot"`)
- `/cachibot/VERSION` (from `--add-data "VERSION:cachibot"`)
- `/cachibot/frontend_dist/` (from `--add-data "frontend/dist:cachibot/frontend_dist"`)

### 4. Runtime Read: `_get_version()` in `__init__.py`

**File**: `cachibot/__init__.py` (lines 15-38)

```python
def _get_version() -> str:
    try:
        return _pkg_version("cachibot")          # Step A: importlib.metadata
    except PackageNotFoundError:
        pass
    candidates = [
        Path(__file__).parent / "VERSION",        # Step B: _MEIPASS/cachibot/VERSION
        Path(__file__).parent.parent.parent / "VERSION",  # Step C: repo root
    ]
    if getattr(sys, "_MEIPASS", None):
        candidates.insert(0, Path(sys._MEIPASS) / "cachibot" / "VERSION")  # Step B': same as B
    for candidate in candidates:
        if candidate.exists():
            return candidate.read_text().strip()
    return "0.0.0-unknown"                        # Step D: fallback
```

**In the PyInstaller binary:**
- **Step A** fails: `importlib.metadata` cannot find `cachibot` because PyInstaller does not bundle `.dist-info` directories by default.
- **Step B/B'** should succeed: `_MEIPASS/cachibot/VERSION` exists from `--add-data`.
- **Step D** triggers only if Step B also fails.

### 5. Settings Page Render

**File**: `frontend/src/components/views/AppSettingsView.tsx` (line 285)

```tsx
// CURRENT (dev, unreleased):
{window.electronAPI?.appVersion ?? healthInfo?.version ?? '...'}

// PREVIOUS (all released versions):
{healthInfo?.version ?? '...'}
```

The backend's `/health` endpoint (`cachibot/api/routes/health.py`, line 28) returns:
```python
version: str = __version__
```

## All Version Definitions (with Conflicts)

| Location | Value | Updated By | Notes |
|---|---|---|---|
| `VERSION` (repo root) | `0.2.34` (dev) / `0.2.56` (main) | CI `publish.yml` | Source of truth for Python builds |
| `pyproject.toml` line 7 | `"0.2.0"` | CI (in memory only) | **STALE** -- never committed back, always `0.2.0` in git |
| `desktop/package.json` line 3 | `"0.2.23"` | CI `npm version` (in memory) | **STALE** -- never committed back, hardcoded at `0.2.23` in git |
| `frontend/package.json` line 4 | `"0.2.0"` | Manual | Not used for display, purely cosmetic |
| `importlib.metadata` (editable) | Matches `pyproject.toml` at install time | `pip install -e .` | Only works when not frozen |
| `app.getVersion()` (Electron) | Reads `desktop/package.json` version | `npm version` in CI | Correct in built artifacts |

**Key conflict**: `pyproject.toml` says `0.2.0`, `VERSION` says `0.2.34/0.2.56`, `desktop/package.json` says `0.2.23`. These never get synchronized in git -- they're only patched during CI builds.

## What's Broken and Why

### Primary Failure: PyInstaller `importlib.metadata` Gap

When `pip install -e .` is used during the `build-backend` CI job, Python creates a `.dist-info` directory in `site-packages` with the package metadata. However, PyInstaller does **not** automatically include this metadata in `--onefile` builds.

The fix was intended to be the VERSION file fallback, and it was added with `--add-data "VERSION:cachibot"` in the publish workflow. **If the VERSION file is correctly bundled, the fallback works and the version is correct.**

Possible scenarios where it still breaks:

1. **Early releases before the `--add-data "VERSION:cachibot"` was added** (commit `daf1162` added it to CI on 2026-02-18, but it was already present in the `.spec` file). Releases before the VERSION file was added to the PyInstaller command would always show "0.0.0-unknown".

2. **PyInstaller `--add-data` ordering**: The command adds `"cachibot:cachibot"` first, then `"VERSION:cachibot"`. If `cachibot/` somehow contained a conflicting file, it could be overwritten. Currently `cachibot/VERSION` does not exist in git, so this is not an issue.

3. **`_MEIPASS` temporary directory issues**: On some Windows antivirus configurations, PyInstaller's `_MEIPASS` extraction can be incomplete or delayed. The VERSION file might not be extracted before `_get_version()` runs (unlikely but possible).

### Secondary Issue: Version Display Only Used Backend

Until the unreleased `daf1162` commit, the Settings "About" section only displayed `healthInfo?.version` -- the backend `/health` response. Even though `app.getVersion()` returns the correct version from Electron's `desktop/package.json`, this was never shown to the user. The `ElectronUpdatesSection` also used only `healthInfo?.version` (line 368).

### Tertiary Issue: `pyproject.toml` Version is Permanently Stale

The hardcoded `version = "0.2.0"` in `pyproject.toml` is never committed back after CI patches it. This means:
- Local `pip install -e .` installs report version `0.2.0`
- Any developer running the backend locally sees `0.2.0` in Settings
- If the VERSION file fallback ever fails in CI, the PyInstaller binary would also report `0.2.0` (not `0.0.0-unknown`, because `importlib.metadata` would find the stale version from the editable install)

Wait -- actually, `importlib.metadata` in the PyInstaller binary does NOT work (no bundled metadata). So the VERSION file is the only path. If it's missing, we get `0.0.0-unknown`.

## Recommended Fix

### Fix 1: Ensure PyInstaller bundles package metadata (belt)

Add a `--copy-metadata cachibot` flag to the PyInstaller command so that `importlib.metadata.version("cachibot")` works in the frozen binary:

**File**: `.github/workflows/publish.yml`, `build-backend` job, "Build backend binary" step

Add `--copy-metadata cachibot` to the PyInstaller invocation (around line 213).

### Fix 2: Use dynamic versioning from VERSION file in pyproject.toml (suspenders)

Instead of hardcoding `version = "0.2.0"` in `pyproject.toml`, use hatchling's dynamic version support:

**File**: `pyproject.toml`

```toml
[project]
name = "cachibot"
dynamic = ["version"]

[tool.hatch.version]
path = "VERSION"
pattern = "(?P<version>.+)"
```

This way, `pip install -e .` always reads the correct version from the VERSION file, and `importlib.metadata.version("cachibot")` always returns the right value.

### Fix 3: Synchronize all version sources in CI (cleanup)

Instead of patching `pyproject.toml` and `desktop/package.json` independently, create a single "stamp versions" step that updates all files consistently.

### Fix 4: Commit version updates to tracked files (long-term)

Currently, the CI writes the VERSION file and commits it to `main`, but `pyproject.toml` and `desktop/package.json` are only patched in memory during CI. Consider committing all three, or better yet, make all of them read from the single `VERSION` file at build time.

### Fix 5: The already-started Electron `appVersion` fallback (immediate)

Commit `daf1162` (currently on `dev`) adds `window.electronAPI?.appVersion` as the primary source in the UI. Once this is released, the Settings page will show the correct Electron app version even if the backend reports "0.0.0-unknown". This is a good immediate fix but doesn't address the backend version being wrong.

## Appendix: Version at Each Stage

```
pyproject.toml (git)    -->  "0.2.0"  (stale, never updated in git)
VERSION (git, main)     -->  "0.2.56" (updated by CI after each release)
VERSION (git, dev)      -->  "0.2.34" (updated by past release, not current)
desktop/package.json    -->  "0.2.23" (stale, never updated in git)

CI release job:
  tag v0.2.57 created   -->  points to merge commit (VERSION = "0.2.56")
  VERSION updated        -->  new commit with "0.2.57" pushed to main

CI build-backend job:
  checkout at v0.2.57    -->  VERSION = "0.2.56" (stale, tag is pre-commit)
  echo "0.2.57" > VERSION   --> fixed locally
  sed pyproject.toml     -->  version = "0.2.57" locally
  pip install -e .       -->  importlib.metadata says "0.2.57"
  pyinstaller bundle     -->  _MEIPASS/cachibot/VERSION = "0.2.57" (if bundled correctly)

CI build-desktop job:
  npm version 0.2.57     -->  desktop/package.json = "0.2.57"
  electron-builder       -->  app.getVersion() = "0.2.57"

Runtime (PyInstaller binary):
  importlib.metadata     -->  FAILS (no .dist-info bundled)
  VERSION file fallback  -->  "0.2.57" (if file exists at _MEIPASS/cachibot/VERSION)
  final fallback         -->  "0.0.0-unknown" (if file not found)

Runtime (Electron):
  app.getVersion()       -->  "0.2.57" (correct)
  /health response       -->  depends on backend ^

Settings page (released versions):
  healthInfo?.version    -->  whatever backend reports ("0.0.0-unknown" if fallback fails)

Settings page (after daf1162 ships):
  electronAPI.appVersion -->  "0.2.57" (correct, shown first)
  healthInfo?.version    -->  fallback only
```
