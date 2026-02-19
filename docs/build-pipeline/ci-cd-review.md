# CI/CD Pipeline Review

**Date:** 2026-02-18
**Reviewer:** Rafael (CI/CD Engineer)
**Repository:** CachiBot

---

## 1. Workflow Inventory

| File | Name | Trigger | Purpose | Status |
|------|------|---------|---------|--------|
| `ci.yml` | CI | Push to `dev`, PR to `dev` | Lint (ruff, bandit) + pytest across Python 3.10/3.11/3.12 | Active |
| `dev.yml` | Publish Dev Version to PyPI | Push to `dev` | Compute dev version, tag, build frontend+Python package, publish to PyPI | Active |
| `publish.yml` | Release -- PyPI + Desktop | Push to `main` | Full release: tag, GitHub Release, PyPI publish, PyInstaller backend (3 OS), Electron desktop (3 OS), update release asset sizes | Active |

All three workflows are active. There are no disabled, stale, or orphaned workflows.

---

## 2. Build Matrix

### CI (`ci.yml`)
- **Platforms:** Ubuntu only (no Windows/macOS CI)
- **Python versions:** 3.10, 3.11, 3.12 (matrix)
- **Frontend:** NOT tested in CI (no npm build, no eslint, no TypeScript check)

### PyInstaller backend (`publish.yml` -- `build-backend` job)
- **Platforms:** ubuntu-latest, macos-latest, windows-latest
- **Architectures:** Default (x64 on all three; no arm64)
- **Python:** 3.12 only

### Electron desktop (`publish.yml` -- `build-desktop` job)
- **Platforms:** ubuntu-latest, macos-latest, windows-latest
- **Architectures:** Per `desktop/package.json`:
  - Windows: x64 only (NSIS installer)
  - macOS: Default (universal via dmg+zip, but no explicit `arch` set so it depends on electron-builder defaults)
  - Linux: x64 only (AppImage + .deb)

### Artifacts produced per release
| Platform | Format | Naming pattern |
|----------|--------|---------------|
| Windows | `.exe` (NSIS) | `CachiBot-Setup-${version}-win.exe` |
| macOS | `.dmg`, `.zip` | `CachiBot-${version}-mac.dmg` |
| Linux | `.AppImage`, `.deb` | `CachiBot-${version}-linux.AppImage`, `CachiBot-${version}-linux.deb` |

---

## 3. Release Pipeline Analysis

The release pipeline (`publish.yml`) executes a 4-job chain:

```
release --> build-backend (3 OS) --> build-desktop (3 OS) --> update-release
```

### Job 1: `release`
1. Skips if actor is `github-actions[bot]` (prevents infinite loop from VERSION commit)
2. Uses `mathieudutour/github-tag-action@v6.0` to auto-bump version (default: patch)
3. Writes VERSION file, commits, and pushes back to `main` with `[skip ci]`
4. Fetches the latest closed PR from `dev->main` for release notes
5. Creates a GitHub Release with a download table (placeholder sizes)
6. Builds the frontend (`npm ci && npm run build`)
7. Patches `pyproject.toml` with the new version via `sed`
8. Builds Python package and publishes to PyPI

### Job 2: `build-backend`
1. Checks out at the release tag (`ref: v${new_version}`)
2. Builds frontend again (redundant but necessary since each job is a fresh runner)
3. Writes VERSION file and patches `pyproject.toml` with new version
4. Installs CachiBot + PyInstaller
5. Bundles the backend as a single-file binary with `--onefile`
6. Uploads artifact for each platform

### Job 3: `build-desktop`
1. Checks out at the release tag
2. **Sets desktop/package.json version** via `npm version ${new_version} --no-git-tag-version`
3. Downloads the backend binary artifact
4. Builds Electron app with `--publish always` (uploads to GitHub Release)
5. Unsigned builds (CSC_IDENTITY_AUTO_DISCOVERY=false, CSC_LINK/CSC_KEY_PASSWORD unset)

### Job 4: `update-release`
1. After all desktop builds complete, fetches the release assets
2. Updates the release body to replace `-- |` size placeholders with actual file sizes
3. Removes the "downloads become available" note

---

## 4. Version Injection Analysis (Root Cause of 0.0.0-unknown)

This is the critical section. There are **multiple version sources** and **multiple injection points** that can fall out of sync.

### Version sources
| Source | Location | Value (dev branch) | Value (main) |
|--------|----------|-------------------|--------------|
| `pyproject.toml` | `version = "..."` | `"0.2.0"` (hardcoded) | `"0.2.0"` (hardcoded) |
| `VERSION` file | repo root | `0.2.34` (committed) | `0.2.56` (committed) |
| `desktop/package.json` | `"version"` | `"0.2.23"` (hardcoded) | `"0.2.23"` (hardcoded) |
| `frontend/package.json` | `"version"` | `"0.2.0"` (never updated) | `"0.2.0"` (never updated) |
| Git tags | `v0.2.56` | Latest release tag | Latest release tag |

### How the Python backend resolves its version (`src/cachibot/__init__.py`)
1. Try `importlib.metadata.version("cachibot")` -- works for pip-installed packages
2. Fallback: read `VERSION` file from multiple candidate paths
3. If PyInstaller frozen: check `_MEIPASS/cachibot/VERSION`
4. Ultimate fallback: `"0.0.0-unknown"`

### How the Electron app resolves its version
- `app.getVersion()` reads from `desktop/package.json` `"version"` field
- This is the version electron-builder bakes into the app metadata

### CI version injection during release
| Step | What gets patched | How |
|------|-------------------|-----|
| `release` job | `pyproject.toml` | `sed` replaces version line |
| `release` job | `VERSION` file | `echo $VERSION > VERSION` |
| `build-backend` job | `pyproject.toml` | Python script + `re.sub` |
| `build-backend` job | `VERSION` file | `echo $VERSION > VERSION` |
| `build-desktop` job | `desktop/package.json` | `npm version $VERSION --no-git-tag-version` |

### The 0.0.0-unknown problem -- likely causes

**Scenario A: Local development**
When running locally from an editable install (`pip install -e .`), `importlib.metadata` reports the version from the _installed_ package metadata. Since `pyproject.toml` hardcodes `version = "0.2.0"`, that is what gets returned. The `VERSION` file at the repo root (currently `0.2.34`) is only used as fallback and may be stale on the dev branch.

**Scenario B: PyInstaller binary without VERSION file**
If the PyInstaller build step writes the VERSION file but the `--add-data "VERSION:cachibot"` path does not resolve correctly, the frozen binary falls through to `"0.0.0-unknown"`. The CI workflow _does_ create VERSION and add it via `--add-data`, so this should work in CI. But a _local_ PyInstaller build would fail if VERSION is missing or empty.

**Scenario C: The `build-backend` checkout is at the tag ref**
The `build-backend` job checks out `ref: v${new_version}`. However, the VERSION commit is pushed to `main` _after_ the tag is created. Sequence:
1. `mathieudutour/github-tag-action` creates tag `v0.2.57` on the current commit
2. The next step writes VERSION file and commits/pushes to main
3. `build-backend` checks out tag `v0.2.57` -- this is the commit BEFORE the VERSION update

This means the checked-out code has the OLD VERSION file (e.g., `0.2.56` instead of `0.2.57`). The `build-backend` job mitigates this by writing VERSION again in its own step, so the binary gets the correct version. But if that step were skipped or failed, you would get a stale version.

**Scenario D: Electron app version when built locally**
The `desktop/package.json` hardcodes `"version": "0.2.23"`. In CI, the `build-desktop` job patches this with `npm version`. But when building locally (e.g., `npm run build` from the desktop directory), the app ships with version `0.2.23` baked in. Since `app.getVersion()` reads from `package.json`, the Electron app version and the backend version will disagree.

**Most likely root cause for "0.0.0-unknown" at runtime:**
The version shows `0.0.0-unknown` when the Python backend cannot find its version. This happens when:
1. Running from a local editable install AND `importlib.metadata` fails (unlikely unless the package is not properly installed), AND the VERSION file at the repo root is missing or empty.
2. Running a PyInstaller binary built locally without creating the VERSION file first.
3. The `touch VERSION` in `ci.yml` creates an **empty** VERSION file -- if that empty file gets bundled, it would parse as empty string, and `_get_version()` would skip it (it only returns if the file exists, and `"".strip()` is falsy... actually the code returns `candidate.read_text().strip()` which would return `""`, which is falsy in Python but `return ""` is still truthy as a return value -- the function returns it regardless). Wait, let me re-read: the code says `return candidate.read_text().strip()` unconditionally if the file exists. So an empty VERSION file would return `""`, not `"0.0.0-unknown"`. That empty string would then become `__version__ = ""`.

**The real root cause is most likely a local development / packaging issue, not a CI issue.** The CI pipeline correctly injects versions at each stage. The problem manifests when:
- Building the desktop app locally without running the version injection steps
- The VERSION file on the dev branch is stale (shows `0.2.34` while main is at `0.2.56`)

---

## 5. Testing Coverage

### What CI tests (`ci.yml`)
| Check | Status | Notes |
|-------|--------|-------|
| Ruff lint | Yes | `ruff check src/cachibot` |
| Ruff format | Yes | `ruff format --check src/cachibot` |
| Bandit security scan | Yes | With configured skip list in `pyproject.toml` |
| pytest | Yes | Across Python 3.10, 3.11, 3.12 |
| mypy type checking | **No** | Listed in dev deps, has config in `pyproject.toml`, but not run in CI |
| Frontend lint (eslint) | **No** | Not run in any workflow |
| Frontend type check (tsc) | **No** | Not run in any workflow |
| Frontend tests | **No** | No test framework configured for frontend |
| Integration tests | **No** | No end-to-end or integration testing |

### Critical gap
The release workflow (`publish.yml`) does NOT run CI checks before releasing. A push to `main` (typically a merge from `dev`) triggers the release directly. There is no gate that ensures tests pass before publishing.

However, since `dev` has CI checks on push and PR, and releases come from merging `dev` into `main`, this provides indirect protection. The gap is that direct pushes to `main` (if branch protection allows them) would skip all testing.

---

## 6. Secrets Referenced

| Secret | Used in | Purpose |
|--------|---------|---------|
| `secrets.GITHUB_TOKEN` | `publish.yml` | Tag creation (mathieudutour action), Electron builder publish to GitHub Releases |
| `secrets.PYPI_TOKEN` | `publish.yml`, `dev.yml` | Publishing to PyPI via twine |

### Not referenced (notable absences)
- No code signing secrets (CSC_LINK, CSC_KEY_PASSWORD) -- signing is explicitly disabled
- No Apple notarization credentials (APPLE_ID, APPLE_APP_SPECIFIC_PASSWORD)
- No Windows signing certificates (WIN_CSC_LINK, WIN_CSC_KEY_PASSWORD)
- No Snapcraft / Flatpak tokens
- No staging/test PyPI tokens

---

## 7. Website vs App

- No separate website deployment workflow exists in `.github/workflows/`
- The `.gitignore` includes `website/*`, suggesting a website directory exists or existed
- The `publish.yml` workflow handles both PyPI and desktop app in one pipeline
- The `dev.yml` workflow handles only PyPI pre-releases (no desktop builds for dev)
- There is no confusion between website and app workflows

---

## 8. Caching

| Cache type | Configured | Where |
|------------|-----------|-------|
| pip cache | Yes (partial) | `publish.yml` `release` job uses `actions/cache@v4` for `~/.cache/pip` |
| pip cache (build-backend) | Yes | `actions/setup-python@v5` with `cache: pip` |
| npm cache | **No** | None of the workflows cache `node_modules` or the npm cache |
| Frontend build cache | **No** | Frontend is rebuilt from scratch in every job that needs it |
| PyInstaller cache | **No** | No caching for PyInstaller intermediates |

### Impact
The frontend is built 3 separate times in the `publish.yml` workflow:
1. In the `release` job (for PyPI sdist/wheel)
2. In each of the 3 `build-backend` jobs (for PyInstaller bundles)

That is 4 total frontend builds per release. Caching or using artifacts could reduce this to 1.

---

## 9. Release Channels

| Channel | Mechanism | Trigger |
|---------|-----------|---------|
| **Stable** | PyPI + GitHub Release + Desktop builds | Push to `main` |
| **Dev/Pre-release** | PyPI only (`.devN` suffix) | Push to `dev` |

- There is no beta/canary channel
- Dev releases are PyPI-only (no desktop builds for dev)
- Desktop builds are only produced for stable releases
- The auto-updater checks the `release` type on GitHub (configured in `desktop/package.json` publish config: `"releaseType": "release"`)

---

## 10. Issues Found

### Critical

1. **VERSION file divergence between branches**
   - `dev` branch VERSION: `0.2.34`
   - `main` branch VERSION: `0.2.56`
   - `pyproject.toml` on both branches: `0.2.0` (never updated in source)
   - `desktop/package.json` on both branches: `0.2.23` (never updated in source)
   - CI patches these at build time, but local development sees stale/wrong versions
   - This is the root cause of `0.0.0-unknown` during local dev if VERSION file is missing

2. **No CI gate before release**
   - `publish.yml` triggers on push to `main` without requiring CI to pass
   - A broken commit merged to main would still trigger a release and publish to PyPI
   - Fix: Add `needs: [ci]` or use branch protection rules requiring status checks

3. **Frontend is completely untested in CI**
   - No ESLint, no TypeScript check, no build verification in `ci.yml`
   - A broken frontend could be released without detection

### Major

4. **`ci.yml` creates empty VERSION file**
   - `touch VERSION` creates an empty file, which means `_get_version()` would return an empty string
   - This silently succeeds but produces a package with `__version__ = ""`
   - Should write a real version or use the same version computation as `dev.yml`

5. **mypy not run in CI despite being configured**
   - `pyproject.toml` has `[tool.mypy]` config with `strict = true`
   - Dev dependencies include `mypy>=1.10.0`
   - But CI does not run `mypy src/cachibot`

6. **Redundant frontend builds**
   - Frontend is built 4 times per release (once in `release`, once per `build-backend` platform)
   - Could build once and share via artifact

7. **`dev.yml` "Ignore bot" step has a bug**
   - The step runs `exit 0` but this only exits that step, not the job
   - All subsequent steps still execute even when the actor is `github-actions[bot]`
   - Should use `if` conditions on subsequent steps or fail the job early

8. **macOS architecture not explicitly set**
   - No explicit `arch` in `desktop/package.json` mac config
   - electron-builder may produce x64-only or universal depending on version and runner
   - Should explicitly set `"arch": ["universal"]` or `["x64", "arm64"]`

### Minor

9. **Inconsistent `actions/setup-python` versions**
   - `ci.yml` uses `@v4`
   - `publish.yml` uses `@v5`
   - `dev.yml` uses `@v4`
   - All should use `@v5` for consistency and latest features

10. **`npm ci || npm install` fallback pattern**
    - Used in `dev.yml` and `publish.yml`
    - `npm ci` failing and falling back to `npm install` masks lockfile issues
    - Should use `npm ci` only and fix any lockfile problems

11. **No concurrency control on `publish.yml` or `dev.yml`**
    - Only `ci.yml` has concurrency group/cancel-in-progress
    - Rapid pushes to `main` or `dev` could trigger overlapping releases
    - Especially dangerous for `dev.yml` which creates tags -- concurrent runs could create duplicate tags

12. **`release` job pushes VERSION commit back to main**
    - The `git push origin main` in the release job creates a new commit on main
    - This could conflict if another PR is merged simultaneously
    - The `|| true` silently swallows push failures

13. **`build-backend` checkout uses tag ref, but tag was created before VERSION commit**
    - The tag points to the pre-VERSION-update commit
    - The `build-backend` job compensates by writing VERSION again
    - But the source code at that ref still has `pyproject.toml version = "0.2.0"`
    - The job patches this, but it is fragile

---

## 11. Recommendations

### Immediate (fix now)

1. **Add concurrency groups to `publish.yml` and `dev.yml`** to prevent overlapping releases
2. **Fix the `dev.yml` bot-ignore logic** -- use job-level `if` or step-level `if` on all subsequent steps
3. **Add frontend checks to `ci.yml`** -- at minimum `npm run build` and `npm run lint`
4. **Standardize action versions** -- upgrade all `setup-python` to `@v5`

### Short-term (this sprint)

5. **Add a CI status gate before release** -- either via branch protection on `main` or by adding a `ci` job dependency in `publish.yml`
6. **Add mypy to CI** -- it is configured but not run
7. **Cache npm dependencies** -- add `actions/cache@v4` for `~/.npm` or use `actions/setup-node@v4` with `cache: npm`
8. **Build frontend once and share as artifact** -- avoid 4 redundant builds per release
9. **Remove `npm ci || npm install` fallback** -- use `npm ci` only

### Medium-term (next milestone)

10. **Unify version management** -- consider a single source of truth (e.g., git tags + `setuptools_scm` or a shared VERSION file that all package.json files read from)
11. **Add code signing** -- at minimum for macOS (required for Gatekeeper) and Windows (SmartScreen warnings)
12. **Add desktop builds to dev workflow** -- allow testing pre-release desktop builds before merging to main
13. **Add integration/E2E tests** -- verify the full backend+frontend stack works before release
14. **Consider using `actions/create-release` or `softprops/action-gh-release` with proper asset uploads** instead of the `--publish always` approach in electron-builder, which can race with the release creation

---

## 12. Workflow Diagrams

### CI Pipeline (dev branch)
```
Push/PR to dev
    |
    +--> lint (ubuntu, py3.12)
    |      |- ruff check
    |      |- ruff format --check
    |      |- bandit security scan
    |
    +--> test (ubuntu, py3.10/3.11/3.12)
           |- pytest -v
```

### Dev Pre-release Pipeline
```
Push to dev
    |
    v
dev-pre-release (ubuntu)
    |- Compute next .devN version
    |- Create + push git tag
    |- Build frontend (npm)
    |- Set version in pyproject.toml + VERSION
    |- Build Python sdist+wheel
    |- Publish to PyPI
```

### Release Pipeline (main branch)
```
Push to main
    |
    v
release (ubuntu)                          # Job 1
    |- Auto-bump version tag
    |- Write VERSION, commit, push
    |- Create GitHub Release
    |- Build frontend + Python package
    |- Publish to PyPI
    |
    v
build-backend (ubuntu/mac/win)           # Job 2 (3 parallel)
    |- Checkout at tag ref
    |- Build frontend (again)
    |- Patch version
    |- PyInstaller --onefile
    |- Upload artifact
    |
    v
build-desktop (ubuntu/mac/win)           # Job 3 (3 parallel)
    |- Checkout at tag ref
    |- npm version (inject version)
    |- Download backend artifact
    |- electron-builder --publish always
    |
    v
update-release (ubuntu)                   # Job 4
    |- Update release body with asset sizes
```

---

## 13. Summary

The CI/CD pipeline is functional and well-structured with a clear progression from dev pre-releases to stable releases across 3 platforms. The main weaknesses are:

1. **Version management is fragmented** across 4 different files, patched at build time by CI. This works for CI-produced artifacts but breaks for local development, which is the likely root cause of the `0.0.0-unknown` issue.
2. **No safety gates** between CI checks and release publishing.
3. **Frontend is a blind spot** -- zero testing or validation in CI.
4. **No code signing** makes the desktop app trigger OS security warnings on all platforms.
5. **The `dev.yml` bot-ignore logic is broken** -- it does not actually skip subsequent steps.

The pipeline produces correct artifacts when run through CI. The `0.0.0-unknown` version issue is primarily a local development problem, not a CI defect.
