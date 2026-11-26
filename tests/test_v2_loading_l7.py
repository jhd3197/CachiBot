"""Hermetic checks for the L7 remaining spinner migration (frontend source).

L7 moved the last one-off ``Loader2`` / ``animate-spin`` call sites outside
auth onto the L1 primitives (Spinner, PageLoading): the marketplace detail
panels and browser, the legacy Users/Plugins views, and the computer /
inspector activity lines. The repo has no frontend unit-test runner, so these
tests read the frontend sources and assert the migrated files no longer carry
the old loaders. Auth pages deliberately keep ``Loader2`` (sign-in work is on
hold) — they are the only allowed remaining importers. No server, no network.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
COMPONENTS = FRONTEND_SRC / "components"
COMPUTER_LESS = FRONTEND_SRC / "styles" / "v2" / "computer.less"
INSPECTOR_LESS = FRONTEND_SRC / "styles" / "v2" / "inspector.less"

# Files migrated in L7.
MIGRATED_FILES = [
    "marketplace/BotDetailDialog.tsx",
    "marketplace/BotDetailPanel.tsx",
    "marketplace/RoomDetailPanel.tsx",
    "marketplace/MarketplaceBrowser.tsx",
    "views/UsersView.tsx",
    "views/PluginsView.tsx",
    "computer/ComputerSection.tsx",
    "inspector/BotInspectorPanel.tsx",
]

# Classes deleted with the migration (hand-rolled spin rules and keyframes).
REMOVED_CLASSES = [
    "computer-activity__spin",
    "computer-activity-spin",
    "inspector__activity-spin",
    "inspector-spin",
    "inspector__run-icon--running",
]

# Auth surfaces keep Loader2 while sign-in work is on hold; every other
# frontend source must be Loader2-free after L7.
AUTH_DIR = COMPONENTS / "auth"


def _read(path: Path) -> str:
    assert path.is_file(), f"missing file: {path.relative_to(REPO_ROOT)}"
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("rel", MIGRATED_FILES)
def test_migrated_file_has_no_loader2_or_animate_spin(rel: str) -> None:
    src = _read(COMPONENTS / rel)
    assert "Loader2" not in src
    assert "animate-spin" not in src


@pytest.mark.parametrize("rel", MIGRATED_FILES)
def test_migrated_file_does_not_use_removed_classes(rel: str) -> None:
    src = _read(COMPONENTS / rel)
    for cls in REMOVED_CLASSES:
        assert cls not in src


def test_removed_spin_rules_and_keyframes_are_gone_from_less() -> None:
    computer = _read(COMPUTER_LESS)
    assert "computer-activity__spin" not in computer
    assert "computer-activity-spin" not in computer
    inspector = _read(INSPECTOR_LESS)
    assert "inspector__activity-spin" not in inspector
    assert "inspector-spin" not in inspector
    assert "run-icon--running" not in inspector


def test_only_auth_files_still_import_loader2() -> None:
    """The only remaining Loader2 importers in frontend/src live under
    components/auth/ (sign-in on hold)."""
    offenders = []
    auth_importers = []
    for path in sorted(FRONTEND_SRC.rglob("*.tsx")) + sorted(FRONTEND_SRC.rglob("*.ts")):
        if "Loader2" not in path.read_text(encoding="utf-8"):
            continue
        if AUTH_DIR in path.parents:
            auth_importers.append(path)
        else:
            offenders.append(path.relative_to(REPO_ROOT))
    assert not offenders, f"Loader2 outside components/auth: {offenders}"
    assert auth_importers, "expected at least one auth file to still use Loader2"


def test_run_row_uses_spinner_for_running_status() -> None:
    src = _read(COMPONENTS / "inspector" / "BotInspectorPanel.tsx")
    assert "Spinner" in src
    # The running branch renders a Spinner in the icon slot; other statuses
    # keep their CheckCircle2 / Ban / XCircle icons.
    assert "run.status === 'running' ? (" in src
    assert '<Spinner size="sm" label="" aria-hidden="true" />' in src
    assert "inspector__run-icon--ok" in src
    assert "inspector__run-icon--error" in src


def test_computer_section_activity_line_uses_spinner() -> None:
    src = _read(COMPONENTS / "computer" / "ComputerSection.tsx")
    assert '<Spinner size="sm" label="" aria-hidden="true" />' in src


def test_users_view_uses_page_loading_and_delayed_button_spinners() -> None:
    src = _read(COMPONENTS / "views" / "UsersView.tsx")
    assert "PageLoading" in src
    assert "text-blue-500" not in src
    assert src.count('<Spinner size="sm" delayMs={200} />') == 2


def test_plugins_view_uses_page_loading_and_idle_refresh_icon() -> None:
    src = _read(COMPONENTS / "views" / "PluginsView.tsx")
    assert "PageLoading" in src
    # Same pattern as SettingsView/KnowledgeStats: RefreshCw idle, Spinner
    # while reloading.
    needle = '{loading ? <Spinner size="sm" delayMs={200} /> : <RefreshCw className="h-4 w-4" />}'
    assert needle in src


def test_marketplace_browser_grid_loaders_are_spinner_lg() -> None:
    src = _read(COMPONENTS / "marketplace" / "MarketplaceBrowser.tsx")
    assert src.count('<Spinner size="lg" />') == 2
    # The centered wrapper is unchanged.
    assert "marketplace__loading" in src


@pytest.mark.parametrize(
    "rel",
    [
        "marketplace/BotDetailDialog.tsx",
        "marketplace/BotDetailPanel.tsx",
        "marketplace/RoomDetailPanel.tsx",
    ],
)
def test_marketplace_install_buttons_use_delayed_spinner(rel: str) -> None:
    src = _read(COMPONENTS / rel)
    assert '<Spinner size="sm" label="" aria-hidden="true" delayMs={200}' in src


@pytest.mark.parametrize("rel", MIGRATED_FILES)
def test_migrated_files_have_no_tailwind_color_literals(rel: str) -> None:
    """No text-blue-500 / text-accent-500 / text-cachi-* on migrated sites."""
    src = _read(COMPONENTS / rel)
    assert "text-blue-500" not in src
    assert "text-cachi-" not in src
    if not rel.endswith("PluginsView.tsx"):
        # PluginsView keeps pre-existing text-accent-500 toggle icons (not
        # loader sites); everywhere else the accent class is gone too.
        assert "text-accent-500" not in src
