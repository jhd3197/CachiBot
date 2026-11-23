"""Hermetic checks for the L2 v2 boot screens.

Reads the desktop splash, the in-app AppLoader (TSX + LESS) and the
frontend ``index.html`` first paint and asserts they use the v2 palette,
kept the JS API the Electron main process drives, and that the warm-start
path no longer forces a 400ms fade. No server, no network.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND = REPO_ROOT / "frontend"

SPLASH = REPO_ROOT / "desktop" / "splash.html"
APP_LOADER = FRONTEND / "src" / "components" / "common" / "AppLoader.tsx"
APP_LOADER_LESS = FRONTEND / "src" / "styles" / "components" / "app-loader.less"
MOTION_LESS = FRONTEND / "src" / "styles" / "v2" / "motion.less"
INDEX_HTML = FRONTEND / "index.html"
PLAN = REPO_ROOT / "docs" / "design" / "UI_V2_PLAN.md"

LEGACY_TOKENS = ["#00E676", "#00e676", "Segoe UI", "Scanline", "scanline"]

DARK_BG = "#0b0c0e"
DARK_PANEL = "#131417"
DARK_GREEN = "#4ade80"
LIGHT_BG = "#f4f4f5"
LIGHT_GREEN = "#16a34a"


def _read(path: Path) -> str:
    assert path.is_file(), f"missing file: {path.relative_to(REPO_ROOT)}"
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "path",
    [SPLASH, APP_LOADER_LESS],
    ids=["splash.html", "app-loader.less"],
)
def test_no_legacy_neon_font_or_scanlines(path: Path) -> None:
    """The old #00E676 accent, Segoe UI lockup and scanline overlay are gone."""
    src = _read(path)
    for token in LEGACY_TOKENS:
        assert token not in src


def test_splash_uses_v2_palette() -> None:
    src = _read(SPLASH).lower()
    for color in [DARK_PANEL, DARK_BG, DARK_GREEN, LIGHT_BG, LIGHT_GREEN]:
        assert color in src


def test_app_loader_uses_v2_palette_and_dark_class() -> None:
    src = _read(APP_LOADER_LESS).lower()
    for color in [DARK_BG, DARK_PANEL, DARK_GREEN, LIGHT_BG, LIGHT_GREEN]:
        assert color in src
    assert ".dark &" in _read(APP_LOADER_LESS)


def test_splash_keeps_main_js_progress_api() -> None:
    src = _read(SPLASH)
    for name in [
        "window.updateStatus",
        "window.showDeterminateProgress",
        "window.showIndeterminateProgress",
        "window.updateProgress",
    ]:
        assert name in src
    # version query param still surfaced in the UI
    assert "params.get('version')" in src


def test_splash_has_reduced_motion_rule() -> None:
    src = _read(SPLASH)
    assert "prefers-reduced-motion" in src


def test_splash_supports_light_and_dark() -> None:
    src = _read(SPLASH)
    assert "prefers-color-scheme" in src
    assert "data-theme" in src  # optional ?theme=dark|light override


def test_app_loader_warm_start_skips_forced_fade() -> None:
    """The 400ms setTimeout must only run when the server had to be waited on."""
    src = _read(APP_LOADER)
    assert "waitedRef" in src
    assert "if (waitedRef.current)" in src
    # warm path swaps immediately; waited path keeps the short fade
    assert "setTimeout(() => setVisible(false), 400)" in src
    assert src.count("setVisible(false)") >= 2


def test_motion_kill_switch_still_covers_app_loader() -> None:
    src = _read(MOTION_LESS)
    assert "prefers-reduced-motion" in src
    for cls in [".app-loader__ring", ".app-loader__core-dot", ".app-loader__bar"]:
        assert cls in src


def test_index_html_first_paint_v2_background() -> None:
    src = _read(INDEX_HTML)
    assert DARK_BG in src
    assert LIGHT_BG in src
    assert "boot-first-paint" in src


def test_plan_documents_l2_boot_screens() -> None:
    src = _read(PLAN)
    assert "L2: v2 boot screens" in src
    assert "prefers-color-scheme" in src
