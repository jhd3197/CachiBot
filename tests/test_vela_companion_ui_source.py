"""Source assertions for the Vela companion settings section.

Hermetic: reads the source files only — no node, no build, no network.
Guards the pass's load-bearing rules:
- the settings section feature-detects: it renders only for admins and only
  while a local Vela is detected (and hides entirely when the status call
  fails — never a disabled placeholder);
- the status line strings are the real ones;
- status polling happens only while the settings view is mounted — nothing
  outside it references the hook;
- the maintainer's no-AI-tools rule holds in the new/changed UI files.
"""

from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "src"

SETTINGS_VIEW = "components/views/AppSettingsView.tsx"
HOOK = "hooks/useVelaCompanion.ts"
API = "api/vela-companion.ts"


def read(relative: str) -> str:
    return (FRONTEND / relative).read_text(encoding="utf-8")


class TestSettingsSectionGated:
    def test_section_hidden_without_admin_or_failed_status(self) -> None:
        src = read(SETTINGS_VIEW)
        assert "useVelaCompanionStatus" in src
        # Admins only, and a failed status call hides the whole section.
        assert "if (!isAdmin || failed) return null" in src

    def test_section_hidden_when_vela_not_detected(self) -> None:
        src = read(SETTINGS_VIEW)
        assert "if (!status || !status.detected) return null" in src

    def test_status_lines_are_the_real_ones(self) -> None:
        src = read(SETTINGS_VIEW)
        assert "Turned off" in src
        assert "Connected to Vela" in src
        assert (
            "Waiting for you to connect CachiBot in Vela > Marketplace > Found on this computer"
            in src
        )

    def test_section_uses_the_v2_toggle(self) -> None:
        src = read(SETTINGS_VIEW)
        assert 'v2-settings__sub">Vela<' in src
        assert "V2Toggle" in src


class TestNoPollingOutsideTheSettingsView:
    def test_only_the_settings_view_uses_the_hook(self) -> None:
        users = [
            path.relative_to(FRONTEND).as_posix()
            for path in FRONTEND.rglob("*.tsx")
            if "useVelaCompanionStatus" in path.read_text(encoding="utf-8")
        ]
        assert sorted(users) == sorted([SETTINGS_VIEW])

    def test_shell_does_not_reference_vela(self) -> None:
        for relative in (
            "components/layout/MainLayout.tsx",
            "App.tsx",
        ):
            assert "vela" not in read(relative).lower(), relative

    def test_hook_polls_on_an_interval(self) -> None:
        src = read(HOOK)
        assert "setInterval" in src
        assert "clearInterval" in src


class TestApiClient:
    def test_api_client_uses_the_companion_routes(self) -> None:
        src = read(API)
        assert "/vela-companion/status" in src
        assert "/vela-companion/settings" in src
        assert "lastSeenAt" in src


class TestNoAiToolMentions:
    def test_new_files_mention_no_ai_tool(self) -> None:
        # Case-sensitive: CSS `cursor:` and DOM `cursor` styles are unrelated
        # to the tool name.
        banned = ("Claude", "Cursor", "Kimi", "Copilot", "ChatGPT", "GPT-")
        for relative in (HOOK, API):
            src = read(relative)
            for word in banned:
                assert word not in src, f"{relative}: {word}"

    def test_vela_additions_in_touched_files_mention_no_ai_tool(self) -> None:
        # AppSettingsView.tsx predates this pass: scan only the lines the
        # Vela section added.
        banned = ("Claude", "Cursor", "Kimi", "Copilot", "ChatGPT", "GPT-")
        for line in read(SETTINGS_VIEW).splitlines():
            if "vela" not in line.lower():
                continue
            for word in banned:
                assert word not in line, f"{SETTINGS_VIEW}: {word}"
