"""Tests for the version-comparison logic in the update service.

Regression coverage for GitHub issue #81: a stable install of v0.3.0 showed an
update banner offering the already-installed v0.3.0. A dev pre-release
(0.3.1.devN) newer than the latest stable set ``prerelease_available`` even for
stable installs, and the frontend banner displays the latest stable version.
"""

import pytest

from cachibot.models.update import UpdateCheckResponse
from cachibot.services import update_service

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_check(
    monkeypatch: pytest.MonkeyPatch, current: str, *pypi_versions: str
) -> UpdateCheckResponse:
    """Run the update check against a fake PyPI with the given releases."""
    monkeypatch.setattr(update_service, "__version__", current)
    monkeypatch.setattr(
        update_service,
        "_fetch_pypi_json",
        lambda: {"releases": {v: [] for v in pypi_versions}},
    )
    monkeypatch.setattr(update_service, "_fetch_github_release_notes", lambda v: (None, None))
    return update_service._check_updates_sync()


# ---------------------------------------------------------------------------
# Same version -> no update
# ---------------------------------------------------------------------------


def test_same_version_no_update(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run_check(monkeypatch, "0.3.0", "0.2.34", "0.3.0")
    assert result.latest_stable == "0.3.0"
    assert result.update_available is False
    assert result.prerelease_available is False


def test_same_version_with_v_prefix_no_update(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run_check(monkeypatch, "v0.3.0", "0.3.0")
    assert result.current_version == "v0.3.0"
    assert result.update_available is False
    assert result.prerelease_available is False


# ---------------------------------------------------------------------------
# Newer / older latest stable
# ---------------------------------------------------------------------------


def test_newer_stable_update_available(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run_check(monkeypatch, "0.3.0", "0.3.0", "0.3.1")
    assert result.latest_stable == "0.3.1"
    assert result.update_available is True


def test_older_stable_no_update(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run_check(monkeypatch, "0.3.1", "0.3.0", "0.3.1")
    assert result.latest_stable == "0.3.1"
    assert result.update_available is False


# ---------------------------------------------------------------------------
# Pre-release handling (issue #81)
# ---------------------------------------------------------------------------


def test_dev_current_vs_stable_latest_no_update(monkeypatch: pytest.MonkeyPatch) -> None:
    """A dev build is newer than the preceding stable — never offer a downgrade."""
    result = _run_check(monkeypatch, "0.3.1.dev5", "0.3.0", "0.3.1.dev5")
    assert result.latest_stable == "0.3.0"
    assert result.update_available is False
    assert result.prerelease_available is False


def test_stable_user_not_offered_prerelease(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression for issue #81: a dev release on PyPI must not make a stable
    install advertise its own version as available."""
    result = _run_check(monkeypatch, "0.3.0", "0.3.0", "0.3.1.dev5")
    assert result.latest_stable == "0.3.0"
    assert result.latest_prerelease == "0.3.1.dev5"
    assert result.update_available is False
    assert result.prerelease_available is False


def test_dev_user_offered_newer_prerelease(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run_check(monkeypatch, "0.3.1.dev3", "0.3.0", "0.3.1.dev3", "0.3.1.dev5")
    assert result.update_available is False
    assert result.prerelease_available is True


def test_dev_user_offered_newer_stable(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run_check(monkeypatch, "0.3.1.dev3", "0.3.0", "0.3.1.dev3", "0.3.1")
    assert result.latest_stable == "0.3.1"
    assert result.update_available is True


def test_local_version_build_not_offered_same_release(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run_check(monkeypatch, "0.3.1.dev5+g1234", "0.3.0", "0.3.1.dev5")
    assert result.update_available is False
    assert result.prerelease_available is False


# ---------------------------------------------------------------------------
# Unparseable versions are handled safely
# ---------------------------------------------------------------------------


def test_unparseable_current_version_is_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run_check(monkeypatch, "0.0.0-unknown", "0.3.0")
    assert result.current_version == "0.0.0-unknown"
    assert result.update_available is False
    assert result.prerelease_available is False


def test_unparseable_pypi_versions_are_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(update_service, "__version__", "0.3.0")
    monkeypatch.setattr(
        update_service,
        "_fetch_pypi_json",
        lambda: {"releases": {"not-a-version": [], "0.3.0": [], "0.3.1": []}},
    )
    monkeypatch.setattr(update_service, "_fetch_github_release_notes", lambda v: (None, None))
    result = update_service._check_updates_sync()
    assert result.latest_stable == "0.3.1"
    assert result.update_available is True
