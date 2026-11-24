"""Hermetic checks for the L4 v2 loading migration (frontend source).

L4 moved the remaining desktop/web loading call sites onto the v2 primitives
(Spinner, PageLoading, Skeleton, Button ``pending``, useDelayedFlag). The repo
has no frontend unit-test runner, so these tests read the frontend sources and
assert the in-scope files no longer carry the old loaders. Legacy pages
(Users, Plugins, Marketplace, auth) keep ``Loader2`` until their own v2
redesign and are deliberately not asserted on. No server, no network.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPONENTS = REPO_ROOT / "frontend" / "src" / "components"
SPINNER = COMPONENTS / "common" / "Spinner.tsx"
WORKSPACE_LESS = REPO_ROOT / "frontend" / "src" / "styles" / "v2" / "workspace.less"
RUNS_LESS = REPO_ROOT / "frontend" / "src" / "styles" / "v2" / "runs.less"

# Desktop/web call sites migrated in L4. Legacy pages are intentionally
# absent — they may still contain Loader2 and must not fail this suite.
MIGRATED_FILES = [
    "views/RoutineEditorView.tsx",
    "views/RoomsView.tsx",
    "rooms/RoomPanel.tsx",
    "views/ToolsView.tsx",
    "views/ScriptEditorView.tsx",
    "views/SettingsView.tsx",
    "views/GlobalLogView.tsx",
    "views/AppSettingsView.tsx",
    "views/RunsView.tsx",
    "views/WorkspaceView.tsx",
    "views/BotSettingsView.tsx",
    "settings/DeveloperPanel.tsx",
    "settings/BotEnvironmentPanel.tsx",
    "settings/BotConnectionsPanel.tsx",
    "knowledge/NotesManager.tsx",
    "knowledge/KnowledgeStats.tsx",
    "knowledge/DocumentUploader.tsx",
    "knowledge/DocumentChunksDialog.tsx",
    "knowledge/DocumentList.tsx",
    "knowledge/KnowledgeSearch.tsx",
    "knowledge/InstructionsEditor.tsx",
    "automations/ScheduleTimeline.tsx",
    "automations/TimelineTab.tsx",
    "dialogs/SettingsDialog.tsx",
    "dialogs/CreateBotWizard/steps/NamePickerStep.tsx",
    "dialogs/CreateBotWizard/steps/DetailsStep.tsx",
    "dialogs/CreateBotWizard/steps/ClassificationStep.tsx",
    "dialogs/CreateBotWizard/steps/PreviewStep.tsx",
    "dialogs/CreateBotWizard/steps/ProjectDetailsStep.tsx",
    "dialogs/CreateBotWizard/steps/ProjectProposalStep.tsx",
    "dialogs/CreateBotWizard/steps/PromptReviewStep.tsx",
    "dialogs/CreateBotWizard/steps/SetupStep.tsx",
    "dialogs/OnboardingWizard/steps/DatabaseStep.tsx",
    "dialogs/OnboardingWizard/steps/SmtpStep.tsx",
    "dialogs/OnboardingWizard/steps/ProviderStep.tsx",
    "common/ModelSelect.tsx",
    "chat/ModelPill.tsx",
]

# Legacy surfaces that keep their own loaders until their v2 redesign.
LEAVE_ALONE_FILES = [
    "views/UsersView.tsx",
    "views/PluginsView.tsx",
    "marketplace/MarketplaceBrowser.tsx",
    "marketplace/BotDetailPanel.tsx",
    "marketplace/BotDetailDialog.tsx",
    "marketplace/RoomDetailPanel.tsx",
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


def test_migrated_and_leave_alone_lists_do_not_overlap() -> None:
    assert not set(MIGRATED_FILES) & set(LEAVE_ALONE_FILES)


@pytest.mark.parametrize("rel", MIGRATED_FILES)
def test_migrated_file_has_no_loader2(rel: str) -> None:
    assert "Loader2" not in _read(COMPONENTS / rel)


@pytest.mark.parametrize("rel", MIGRATED_FILES)
def test_migrated_file_has_no_css_spin_loaders(rel: str) -> None:
    """No animate-spin utilities and no hand-rolled CSS border rings."""
    src = _read(COMPONENTS / rel)
    assert "animate-spin" not in src
    assert "border-green-500 border-t-transparent" not in src
    assert "border-t-transparent" not in src


def test_leave_alone_files_still_exist_and_are_not_asserted_on() -> None:
    """Legacy pages keep Loader2 for now — presence here must not fail."""
    for rel in LEAVE_ALONE_FILES:
        assert (COMPONENTS / rel).is_file(), f"missing file: {rel}"


def test_spinner_supports_delay_ms_via_use_delayed_flag() -> None:
    src = _read(SPINNER)
    assert "delayMs" in src
    assert "useDelayedFlag" in src


def test_workspace_bots_loading_uses_skeleton_not_opacity_hook() -> None:
    src = _read(COMPONENTS / "views" / "WorkspaceView.tsx")
    assert "Skeleton" in src
    assert "workspace__bots--loading" not in src
    assert "workspace__bots--loading" not in _read(WORKSPACE_LESS)


def test_knowledge_lists_and_stats_use_skeleton_primitive() -> None:
    assert "Skeleton" in _read(COMPONENTS / "knowledge" / "DocumentList.tsx")
    assert "Skeleton" in _read(COMPONENTS / "knowledge" / "NotesManager.tsx")
    stats = _read(COMPONENTS / "knowledge" / "KnowledgeStats.tsx")
    assert 'variant="card"' in stats
    assert "SkeletonCard" not in stats


@pytest.mark.parametrize(
    "rel", ["common/ModelSelect.tsx", "chat/ModelPill.tsx"], ids=["ModelSelect", "ModelPill"]
)
def test_model_pickers_discovering_state_shows_spinner_with_same_copy(rel: str) -> None:
    src = _read(COMPONENTS / rel)
    assert "Discovering models..." in src
    assert "Spinner" in src


def test_runs_spin_class_fully_removed() -> None:
    """The legacy runs__spin animation class is gone from code and styles."""
    assert "runs__spin" not in _read(COMPONENTS / "views" / "RunsView.tsx")
    assert "runs__spin" not in _read(COMPONENTS / "views" / "GlobalLogView.tsx")
    assert "runs__spin" not in _read(RUNS_LESS)


def test_room_panel_initial_load_uses_page_loading() -> None:
    src = _read(COMPONENTS / "rooms" / "RoomPanel.tsx")
    assert "PageLoading" in src
