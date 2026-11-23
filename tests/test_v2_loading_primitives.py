"""Hermetic checks for the L1 v2 loading primitives (frontend source).

The repo has no frontend unit-test runner — CI runs ``npm run lint`` and
``npm run build`` — so these tests only read the frontend sources and assert
the primitives exist with the expected shape. No server, no network.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"

RUNS_VIEW = FRONTEND_SRC / "components" / "views" / "RunsView.tsx"
BUTTON = FRONTEND_SRC / "components" / "common" / "Button.tsx"
SPINNER = FRONTEND_SRC / "components" / "common" / "Spinner.tsx"
SKELETON = FRONTEND_SRC / "components" / "common" / "Skeleton.tsx"
PAGE_LOADING = FRONTEND_SRC / "components" / "common" / "PageLoading.tsx"
STATUS_LINE = FRONTEND_SRC / "components" / "common" / "StatusLine.tsx"
USE_DELAYED_FLAG = FRONTEND_SRC / "hooks" / "useDelayedFlag.ts"


def _read(path: Path) -> str:
    assert path.is_file(), f"missing file: {path.relative_to(REPO_ROOT)}"
    return path.read_text(encoding="utf-8")


def test_runs_view_spinner_typo_gone() -> None:
    """RunsView must use the real runs__spin class / the Spinner primitive."""
    assert "runs__spinner" not in _read(RUNS_VIEW)


def test_button_defines_pending_prop() -> None:
    assert "pending?: boolean" in _read(BUTTON)


@pytest.mark.parametrize(
    ("path", "export_name"),
    [
        (SPINNER, "Spinner"),
        (SKELETON, "Skeleton"),
        (PAGE_LOADING, "PageLoading"),
        (STATUS_LINE, "StatusLine"),
    ],
)
def test_primitive_module_exists_and_exports(path: Path, export_name: str) -> None:
    assert f"export function {export_name}" in _read(path)


def test_use_delayed_flag_exists_with_200ms_default() -> None:
    src = _read(USE_DELAYED_FLAG)
    assert "export function useDelayedFlag" in src
    assert "delayMs = 200" in src
