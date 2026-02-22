# Distribution Strategy: pip vs Electron

> Analysis of CachiBot's dual distribution model, version management, and recommended path forward.

---

## 1. Current State Analysis

CachiBot ships through **two active distribution channels** simultaneously:

### 1.1 PyPI (pip)

| Attribute | Value |
|-----------|-------|
| Package name | `cachibot` |
| Latest release | `0.2.56` (as of 2026-02-18) |
| Dev releases | `0.2.x.devN` published on every push to `dev` |
| Build system | Hatchling (`pyproject.toml`) |
| Entry points | `cachibot` and `cachi` CLI commands |
| Bundled assets | `frontend/dist` (pre-built React app), `VERSION` file |
| Install target | Any Python 3.10+ environment |
| CI workflow | `publish.yml` (release) + `dev.yml` (pre-release) |

The pip package is a **full-stack distribution**: it includes the Python backend AND the pre-built frontend, served by FastAPI's static file handling. Users can run `cachibot server` and get both API + UI.

### 1.2 Electron (Desktop App)

| Attribute | Value |
|-----------|-------|
| Package name | `cachibot-desktop` |
| Current `package.json` version | `0.2.23` (stale, updated at build time) |
| Build tool | electron-builder v25 |
| Platforms | Windows (NSIS), macOS (DMG/ZIP), Linux (AppImage/deb) |
| Backend delivery | PyInstaller-bundled `cachibot-server` binary in `extraResources` |
| Auto-update | electron-updater via GitHub Releases |
| CI workflow | `publish.yml` jobs `build-backend` + `build-desktop` |

The Electron app is a **wrapper**: it spawns the PyInstaller-compiled backend binary, waits for port 5870, then loads the UI from the backend's HTTP server. The Electron shell provides native window chrome, system tray, and auto-updates.

### 1.3 What Both Channels Deliver

Both distribution channels deliver the **exact same product**: the CachiBot API server + React frontend UI. The core difference is the runtime wrapper:

```
pip install cachibot          ->  Python process  ->  FastAPI + React UI
CachiBot-Setup.exe (Electron) ->  Electron shell  ->  PyInstaller binary -> FastAPI + React UI
```

---

## 2. Version Source of Truth Analysis

### 2.1 Where Versions Are Defined

There are currently **four** places where a version exists:

| Location | Current Value | Role |
|----------|---------------|------|
| `VERSION` (repo root) | `0.2.34` | Intended single source of truth |
| `pyproject.toml` `version` | `0.2.0` | Build-time value (overwritten by CI) |
| `desktop/package.json` `version` | `0.2.23` | Electron app version (overwritten by CI) |
| `frontend/package.json` `version` | `0.2.0` | Cosmetic; not used for distribution |

### 2.2 How CI Manages Versions

The release pipeline (`publish.yml`) uses **git tags** as the real source of truth:

1. `mathieudutour/github-tag-action` bumps the tag (e.g., `v0.2.56` -> `v0.2.57`)
2. CI writes the new version to `VERSION` and commits it
3. CI `sed`s the new version into `pyproject.toml` before `python -m build`
4. CI runs `npm version $NEW_VERSION` in `desktop/` before `electron-builder`
5. The dev pipeline (`dev.yml`) computes `.devN` versions independently from tags

### 2.3 Version Sync Problems

**Critical: The `VERSION` file, `pyproject.toml`, and `desktop/package.json` are always stale in the repo.**

- The `VERSION` file says `0.2.34`, but PyPI has `0.2.56`. This means the CI commit that updates `VERSION` is working, but it lags behind the latest tag (the commit writes the version *after* the tag is created, and only to `main`).
- `pyproject.toml` still says `0.2.0` because CI only `sed`s it during build -- it never commits the change back.
- `desktop/package.json` says `0.2.23` -- same issue, `npm version` runs during build but is never committed.
- A developer cloning the repo and running `pip install -e .` gets version `0.2.0` from `pyproject.toml`, not the current release version.

**The real source of truth is the git tag**, but three files pretend to be the source of truth and are all wrong.

### 2.4 How the Python Backend Resolves Its Version

The resolution chain in `cachibot/__init__.py` is:

1. `importlib.metadata.version("cachibot")` -- works for pip installs (reads from package metadata)
2. `cachibot/VERSION` file -- works for wheel installs (bundled by hatch) and PyInstaller (bundled via `--add-data`)
3. `../../VERSION` (repo root) -- works for editable installs if `VERSION` exists
4. `sys._MEIPASS/cachibot/VERSION` -- PyInstaller frozen binary
5. Fallback: `"0.0.0-unknown"`

### 2.5 How Electron Resolves Its Version

- `app.getVersion()` reads from `desktop/package.json` `version` field
- This is set by `npm version $NEW_VERSION` during CI build
- Exposed to the renderer via `preload.js` -> `window.electronAPI.appVersion`

---

## 3. Conflict Analysis

### 3.1 Port Conflicts

Both pip and Electron use **port 5870** for the backend server. If a user has:
- A pip-installed `cachibot server` running, AND
- Launches the Electron app

...the Electron app's backend will fail to bind to 5870. The Electron app will show a "Backend Error" dialog.

**Severity: High.** This is the most likely real-world conflict.

### 3.2 Shared Config Files

Both distributions read from:
- `~/.cachibot.toml` (user config)
- `./cachibot.toml` (workspace config)
- `CACHIBOT_*` environment variables

**Severity: Low.** Config sharing is actually desirable -- users expect their settings to persist.

### 3.3 Shared Database

Both distributions use the same SQLite database at `~/.cachibot/cachibot.db`.

**Severity: Medium.** If both are running simultaneously, SQLite will handle concurrent reads but may have write contention. However, aiosqlite with WAL mode should handle this reasonably. The real risk is schema migrations -- if the pip install is at version N and the Electron install is at version N+1, the first one to run migrations wins, potentially breaking the other.

### 3.4 Self-Update Conflicts

The pip distribution has a **built-in self-update mechanism** (`/api/update/apply` endpoint) that runs `pip install --upgrade cachibot`. This makes sense for pip installs but is **dangerous for Electron**: the Electron app bundles a PyInstaller binary, not a pip package. Running `pip install` from inside the Electron app would install packages into a non-existent venv.

The Electron app has its own update mechanism via `electron-updater` (GitHub Releases). The two update paths should never cross, but the update UI in the frontend does not clearly differentiate which update path is active.

**Severity: Medium.** The backend's `/api/update/apply` endpoint should be disabled when `CACHIBOT_DESKTOP=true`.

### 3.5 CLI Entry Points

pip install creates `cachibot` and `cachi` CLI commands. The Electron app does not expose CLI commands -- it bundles a PyInstaller binary named `cachibot-server` that only runs the server (no CLI subcommands).

**Severity: None.** These do not conflict.

---

## 4. Audience Analysis

### 4.1 Who Uses pip

| Persona | Use Case |
|---------|----------|
| Python developers | `pip install cachibot` in a venv, run from terminal |
| Server/headless deployments | `cachibot server` on a VPS, Docker, etc. |
| Contributors | `pip install -e ".[dev]"` for development |
| CI/CD pipelines | Programmatic use of CachiBot as a Python library |

### 4.2 Who Uses Electron

| Persona | Use Case |
|---------|----------|
| End users | Download installer, double-click, use the GUI |
| Non-technical users | No Python knowledge required |
| Desktop-first users | System tray, native notifications, auto-updates |

### 4.3 Is the Split Clear?

**No.** The split is muddled because:

1. The pip install also serves the full GUI (React frontend) -- it is NOT just a CLI/library package.
2. Both deliver the exact same UI experience.
3. The only differentiator is the runtime wrapper (native Python vs Electron+PyInstaller).
4. The self-update mechanism in the pip version makes it feel like a desktop app.
5. There is no messaging on the website, README, or installer that explains when to use which.

---

## 5. Recommended Strategy

### Keep Both, With Clear Separation

**Recommendation: Option (a) -- Keep both distribution channels, but enforce clear boundaries.**

#### Rationale

1. **pip is essential for developers and servers.** Killing pip would alienate the Python developer audience and make server deployments impossible. CachiBot is fundamentally a Python library+server.

2. **Electron is essential for end users.** Expecting non-technical users to install Python, create a venv, and run `pip install cachibot && cachibot server` is unrealistic.

3. **The overlap is manageable.** The conflicts identified above are all solvable with modest engineering effort.

#### Separation Rules

| Concern | pip Distribution | Electron Distribution |
|---------|-----------------|----------------------|
| Target audience | Developers, servers, Docker | End users, desktop |
| Update mechanism | `pip install --upgrade` / built-in `/api/update` | electron-updater (GitHub Releases) |
| CLI commands | `cachibot`, `cachi` -- full CLI | None exposed (internal `cachibot-server` binary only) |
| Version display | `/api/health` returns Python package version | `app.getVersion()` returns Electron app version |
| Self-update UI | Show pip-based update dialog | Show Electron-based update dialog |
| Backend runtime | Native Python (user's interpreter) | PyInstaller frozen binary |

#### Key Changes Needed

1. **Disable pip self-update when running as desktop app.** When `CACHIBOT_DESKTOP=true`, the `/api/update/check` and `/api/update/apply` endpoints should return a response indicating that updates are managed by the desktop app, not pip.

2. **Frontend should detect distribution mode.** The health endpoint already returns `desktop: true/false`. The update UI should switch between Electron-updater flow and pip-update flow based on this flag.

3. **Document the two channels clearly.** README and website should have a "Download" section with two clear paths: "Desktop App" (download installer) vs "Python Package" (pip install).

---

## 6. Version Unification Plan

### 6.1 Single Source of Truth: The `VERSION` File

The `VERSION` file at the repo root should be the **sole canonical version**. Everything else should read from it.

### 6.2 How Each Consumer Reads It

| Consumer | How It Gets the Version |
|----------|------------------------|
| `pyproject.toml` | Use `hatch-vcs` or a dynamic version plugin that reads `VERSION` |
| `desktop/package.json` | CI runs `npm version $(cat VERSION)` (already happening) |
| `frontend/package.json` | Not important; keep in sync or remove `version` field |
| Python runtime | `__init__.py` already has the fallback chain; works as-is |
| PyInstaller binary | `--add-data VERSION:cachibot` (already happening) |
| Electron `app.getVersion()` | Reads from `desktop/package.json` (set by CI) |

### 6.3 Recommended Flow

```
[Git tag created]
       |
       v
[CI extracts version from tag]
       |
       +---> Writes to VERSION file (committed back to main)
       +---> sed into pyproject.toml (build-time only, not committed)
       +---> npm version in desktop/package.json (build-time only, not committed)
       |
       v
[All artifacts built with consistent version]
```

### 6.4 Dynamic Version in pyproject.toml

Replace the static `version = "0.2.0"` with a dynamic version read from `VERSION`:

```toml
[project]
dynamic = ["version"]

[tool.hatch.version]
path = "VERSION"
pattern = "(?P<version>.+)"
```

This way, `pip install -e .` in a dev checkout will read the `VERSION` file and get a real version number instead of a stale `0.2.0`.

### 6.5 Stop Committing Version Back

The CI step that commits the updated `VERSION` file back to `main` creates noise and race conditions. Instead:

- The `VERSION` file in the repo should contain the **last released version** and be updated as part of the PR merge process (or by the developer before merging).
- OR: Accept that `VERSION` in the repo is always the "next development" version and CI overrides it at build time.

The current approach (CI commits back) is fragile because:
- It can fail silently (`|| true`)
- It creates commits by `github-actions[bot]` that trigger the `if: github.actor != 'github-actions[bot]'` guard
- The `VERSION` file in the repo is often stale (currently `0.2.34` vs `0.2.56` on PyPI)

---

## 7. Migration Plan

### 7.1 For Existing pip Users

No breaking changes. `pip install --upgrade cachibot` continues to work. The only visible change would be:
- More accurate version display (fixing the `0.0.0-unknown` issue)
- Self-update UI disabled when running under Electron

### 7.2 For Existing Electron Users

No breaking changes. Auto-update via electron-updater continues to work. Changes:
- More accurate version in the title bar / settings
- Update UI will use the Electron-native update flow instead of showing pip-related options

### 7.3 Communication

1. Add a "How to Install" section to the README with two clear paths
2. Release notes should mention both distribution channels
3. Consider adding a `/api/health` field like `distribution: "pip" | "desktop"` to make it programmatically clear

### 7.4 Implementation Order

1. **Fix version single source of truth** -- Make `pyproject.toml` read dynamically from `VERSION`
2. **Gate pip self-update behind desktop flag** -- Disable `/api/update/apply` when `CACHIBOT_DESKTOP=true`
3. **Frontend update UI branching** -- Show correct update path based on `desktop` flag from health endpoint
4. **Port conflict handling** -- Electron should detect if port 5870 is already in use and either warn or use a different port
5. **Document the two channels** -- README, website, installer welcome screen

---

## 8. Decision Matrix

| Factor | pip Only | Electron Only | Both (Recommended) |
|--------|----------|---------------|-------------------|
| Developer experience | Excellent | Poor (no CLI, no venv) | Excellent |
| End-user experience | Poor (requires Python) | Excellent | Excellent |
| Server deployments | Supported | Not possible | Supported |
| Docker/CI | Supported | Not possible | Supported |
| Auto-updates | Via pip (manual or self-update API) | Native (electron-updater) | Both paths available |
| Maintenance burden | Low | Medium (PyInstaller + Electron) | Medium-High |
| Version management | Simple (one artifact) | Simple (one artifact) | Moderate (must sync) |
| Build pipeline complexity | Simple | Complex (3-platform matrix) | Complex (already exists) |
| Distribution size | ~50 MB (pip, no binary) | ~150-200 MB (Electron + PyInstaller) | Both |
| Offline install | `pip install cachibot.whl` | Installer exe/dmg/AppImage | Both |
| Cross-platform | Anywhere Python runs | Win/Mac/Linux (built binaries) | Both |

### Trade-off Summary

The **maintenance cost of dual distribution** is real but manageable. The build pipeline already handles both channels. The main risks (version drift, port conflicts, update path confusion) are all solvable with the changes outlined above.

Dropping pip would lose the developer/server audience. Dropping Electron would lose the desktop/end-user audience. **CachiBot serves both audiences, so it should ship to both.**

---

## 9. Open Questions

1. **Should the Electron app bundle its own Python?** Currently it bundles a PyInstaller binary, which avoids this. But if CachiBot ever needs runtime plugin installation (pip install inside the app), this becomes relevant.

2. **Should pip installs serve the frontend?** Currently they do. An argument could be made that the pip package should be CLI/API-only, with the frontend only in Electron. But this would break the "pip install and go" experience that server users expect.

3. **Should there be a separate `cachibot-server` PyPI package?** A lighter package without frontend assets for headless/Docker deployments. This is a future optimization, not urgent.

4. **Port conflict resolution.** Should the Electron app auto-detect a running instance and connect to it instead of spawning a new backend? This would turn it into a thin client for an existing pip-installed server.
