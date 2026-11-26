"""Hermetic checks for the L6 v2 loading hardening (frontend source).

L6 applied one delay rule across the desktop/web loading states, re-verified
the reduced-motion kill-switch and cleaned up leftovers. The repo has no
frontend unit-test runner, so these tests read the frontend sources and
assert the rules hold. No server, no network.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND = REPO_ROOT / "frontend"
COMPONENTS = FRONTEND / "src" / "components"

BUTTON = COMPONENTS / "common" / "Button.tsx"
PAGE_LOADING = COMPONENTS / "common" / "PageLoading.tsx"
USE_DELAYED_FLAG = FRONTEND / "src" / "hooks" / "useDelayedFlag.ts"
MOTION_LESS = FRONTEND / "src" / "styles" / "v2" / "motion.less"
BASE_LESS = FRONTEND / "src" / "styles" / "base.less"
SPLASH = REPO_ROOT / "desktop" / "splash.html"
INDEX_HTML = FRONTEND / "index.html"

# Auth surfaces keep their own loaders while sign-in work is on hold. They
# may still contain Loader2 / animate-spin — nothing here may fail on that.
# (Users, Plugins and the Marketplace left this list in L7.)
LEAVE_ALONE_FILES = [
    "auth/LoginPage.tsx",
    "auth/SetupPage.tsx",
    "auth/ConsentPage.tsx",
    "auth/AuthCallback.tsx",
    "auth/UpgradePage.tsx",
    "auth/ProtectedRoute.tsx",
]


def _read(path: Path) -> str:
    assert path.is_file(), f"missing file: {path.relative_to(REPO_ROOT)}"
    return path.read_text(encoding="utf-8")


def _reduced_motion_block(src: str) -> str:
    """Return the body of the first prefers-reduced-motion media block."""
    start = src.find("prefers-reduced-motion")
    assert start != -1, "missing @media (prefers-reduced-motion: reduce) rule"
    brace = src.find("{", start)
    assert brace != -1, "unbalanced braces in reduced-motion rule"
    depth = 0
    for i in range(brace, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[brace : i + 1]
    raise AssertionError("unbalanced braces in reduced-motion rule")


def test_motion_less_kill_switch_covers_loading_animations() -> None:
    block = _reduced_motion_block(_read(MOTION_LESS))
    for selector in [
        ".spinner",
        ".v2-skeleton",
        ".v2-status-line__mark",
        ".app-loader__ring",
        ".app-loader__core-dot",
        ".app-loader__bar",
        "animate-spin",
        "animate-pulse",
    ]:
        assert selector in block, f"motion.less kill-switch lost {selector}"


def test_splash_reduced_motion_names_animated_elements() -> None:
    src = _read(SPLASH)
    assert "prefers-reduced-motion" in src
    block = _reduced_motion_block(src)
    for selector in [".ring1", ".ring2", ".dot", ".bottom", ".progress-bar", ".status-text"]:
        assert selector in block, f"splash reduced-motion rule lost {selector}"


def test_index_first_paint_reduced_motion() -> None:
    src = _read(INDEX_HTML)
    assert "prefers-reduced-motion" in src
    assert ".boot-first-paint__mark" in _reduced_motion_block(src)


def test_use_delayed_flag_still_defaults_to_200ms() -> None:
    src = _read(USE_DELAYED_FLAG)
    assert "export function useDelayedFlag" in src
    assert "delayMs = 200" in src


def test_button_pending_disables_immediately_and_delays_spinner() -> None:
    """One delay only: the overlaid spinner waits 200ms; disabling never does."""
    src = _read(BUTTON)
    assert "disabled={disabled || pending}" in src
    assert "delayMs={200}" in src or "useDelayedFlag" in src


def test_page_loading_inner_spinner_has_no_delay() -> None:
    """PageLoading delays via its pending flag; a delayMs on the inner
    Spinner would double-delay."""
    src = _read(PAGE_LOADING)
    tags = re.findall(r"<Spinner\b[^>]*>", src, flags=re.DOTALL)
    assert tags, "expected a Spinner inside PageLoading"
    for tag in tags:
        assert "delayMs" not in tag


def test_dashboard_cards_spinner_uses_token_color() -> None:
    """The active-bot mark falls back to the Spinner's token default."""
    assert "accent-500" not in _read(COMPONENTS / "rooms" / "DashboardCardsView.tsx")


def test_qr_placeholder_spinner_is_delayed() -> None:
    """QR generation resolves in milliseconds; an immediate ring would flash."""
    assert '<Spinner size="lg" delayMs={200} />' in _read(
        COMPONENTS / "views" / "AppSettingsView.tsx"
    )


def test_dead_pulse_slow_keyframes_removed() -> None:
    assert "pulse-slow" not in _read(BASE_LESS)


def test_leave_alone_files_may_keep_loader2() -> None:
    """Auth pages keep Loader2 while sign-in work is on hold — their presence
    here must not fail, and the motion kill-switch still covers their
    animate-spin/animate-pulse utilities."""
    for rel in LEAVE_ALONE_FILES:
        assert (COMPONENTS / rel).is_file(), f"missing file: {rel}"
