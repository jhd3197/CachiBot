"""Hermetic checks for the L8 single boot screen on desktop.

On Electron the splash is the only boot screen: the main window stays
hidden until the renderer reports its first real frame over the
``app:ready`` IPC, and the in-app AppLoader renders nothing on desktop.
The repo has no frontend/Electron test runner, so these tests read the
sources and assert the handoff holds. No server, no network.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

MAIN = REPO_ROOT / "desktop" / "main.js"
PRELOAD = REPO_ROOT / "desktop" / "preload.js"
APP_LOADER = REPO_ROOT / "frontend" / "src" / "components" / "common" / "AppLoader.tsx"
VITE_ENV = REPO_ROOT / "frontend" / "src" / "vite-env.d.ts"
PLAN = REPO_ROOT / "docs" / "design" / "UI_V2_PLAN.md"


def _read(path: Path) -> str:
    assert path.is_file(), f"missing file: {path.relative_to(REPO_ROOT)}"
    return path.read_text(encoding="utf-8")


def _block_after(src: str, marker: str) -> str:
    """Return the brace-balanced block that starts after ``marker``."""
    start = src.find(marker)
    assert start != -1, f"missing marker: {marker}"
    brace = src.find("{", start)
    assert brace != -1, f"no block after marker: {marker}"
    depth = 0
    for i in range(brace, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[brace : i + 1]
    raise AssertionError(f"unbalanced braces after marker: {marker}")


def test_preload_exposes_app_ready() -> None:
    src = _read(PRELOAD)
    assert "appReady" in src
    assert "ipcRenderer.send('app:ready')" in src


def test_vite_env_types_app_ready() -> None:
    assert "appReady?: () => void" in _read(VITE_ENV)


def test_main_handles_app_ready_ipc() -> None:
    src = _read(MAIN)
    block = _block_after(src, "ipcMain.on('app:ready'")
    assert "revealMainWindow()" in block


def test_main_ready_to_show_does_not_close_splash_when_present() -> None:
    """With a splash up, ready-to-show must not show the window or close the
    splash directly — that handoff belongs to app:ready / the fallback."""
    block = _block_after(_read(MAIN), "once('ready-to-show'")
    assert "splash.close(" not in block
    assert ".show()" not in block
    assert "setTimeout(revealMainWindow" in block  # fallback arms here
    assert "if (!splashWindow)" in block  # no-splash path still shows immediately


def test_main_reveal_is_idempotent_and_destroy_safe() -> None:
    block = _block_after(_read(MAIN), "function revealMainWindow")
    assert "clearTimeout(revealFallbackTimer)" in block
    assert "isDestroyed()" in block
    assert "isVisible()" in block
    assert "mainWindow.show()" in block
    assert "splashWindow.close()" in block


def test_main_fallback_timer_is_bounded_and_cleared() -> None:
    src = _read(MAIN)
    assert "setTimeout(revealMainWindow, 12000)" in src
    # cleared when the window closes before ready arrives
    closed = _block_after(src, "mainWindow.on('closed'")
    assert "clearTimeout(revealFallbackTimer)" in closed


def test_main_reveals_window_on_load_failure() -> None:
    """A hidden window must never swallow an error: load failure or a
    renderer crash reveals the window so the user sees something."""
    src = _read(MAIN)
    fail_load = _block_after(src, "'did-fail-load'")
    assert "revealMainWindow()" in fail_load
    gone = _block_after(src, "'render-process-gone'")
    assert "revealMainWindow()" in gone


def test_app_loader_desktop_guard_and_handoff() -> None:
    src = _read(APP_LOADER)
    assert "window.electronAPI" in src
    assert "isDesktop" in src
    # children are committed when `ready` flips; the effect calls appReady
    # directly — rAF would never fire in the hidden window
    assert "api?.appReady?.()" in src
    assert "requestAnimationFrame" not in src
    # desktop renders no overlay: nothing while initializing, children once ready
    assert "ready ? <>{children}</> : null" in src


def test_app_loader_web_path_unchanged() -> None:
    """The web boot screen keeps the overlay + fade behavior."""
    src = _read(APP_LOADER)
    assert "app-loader--fade" in src
    assert "setTimeout(() => setVisible(false), 400)" in src


def test_plan_documents_l8() -> None:
    src = _read(PLAN)
    assert "L8: single boot screen on desktop" in src
    assert "app:ready" in src
    # the L2 paragraph no longer leaves the two screens as the final word
    assert "AppLoader remains the web boot screen" in src
