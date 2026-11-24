"""Source assertions for the C4 computer UI (frontend/src).

Hermetic: reads the source files only — no node, no build, no network.
Guards the load-bearing rules of the pass:
- every computer surface gates on the Docker probe (`status.available`) and
  hides when the computer is off/unavailable;
- the inspector's Computer card is conditional on the feature being on;
- the design's "Use a cloud computer instead" CTA does not exist anywhere;
- Files-sheet "Open on computer" is conditional (computer live + operator);
- the explainer facts are the true ones, and no other idle number is
  hard-coded in copy;
- the maintainer's no-AI-tools rule holds in the new/changed UI files.
"""

from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "src"

COMPUTER_COMPONENTS = [
    "components/computer/ComputerStateCard.tsx",
    "components/computer/ComputerSection.tsx",
    "components/computer/ComputerOpenView.tsx",
    "components/computer/BotSettingsComputerSection.tsx",
    "components/computer/utils.ts",
]

UI_FILES = COMPUTER_COMPONENTS + [
    "components/inspector/BotInspectorPanel.tsx",
    "components/layout/MainLayout.tsx",
    "components/views/ChatView.tsx",
    "components/views/BotSettingsView.tsx",
    "components/chat/FilesSheet.tsx",
    "components/chat/ChatCards.tsx",
    "hooks/useComputerPreview.ts",
    "stores/computer.ts",
    "api/computer.ts",
    "styles/v2/computer.less",
    "styles/v2/inspector.less",
]


def read(relative: str) -> str:
    return (FRONTEND / relative).read_text(encoding="utf-8")


class TestGatesOnAvailable:
    """No computer UI renders while the Docker probe says unavailable."""

    def test_store_treats_failed_probe_as_unavailable(self) -> None:
        src = read("stores/computer.ts")
        assert "available: false" in src
        assert "Treat an unreachable probe" in src

    def test_shell_fetches_the_probe_on_mount(self) -> None:
        src = read("components/layout/MainLayout.tsx")
        assert "useComputerStore" in src
        assert "fetchStatus" in src

    def test_computer_section_hides_when_unavailable(self) -> None:
        src = read("components/computer/ComputerSection.tsx")
        assert "if (!status?.available) return null" in src

    def test_open_view_hides_when_unavailable(self) -> None:
        src = read("components/computer/ComputerOpenView.tsx")
        assert "if (!bot || !status?.available) return null" in src

    def test_chat_computer_button_is_gated(self) -> None:
        src = read("components/views/ChatView.tsx")
        assert "computerAvailable" in src
        assert "s.status?.available === true" in src
        # The toggle only renders inside the availability gate.
        assert "{computerAvailable && (" in src

    def test_settings_section_is_gated(self) -> None:
        src = read("components/views/BotSettingsView.tsx")
        assert "computerAvailable" in src
        assert "s.id !== 'computer' || computerAvailable" in src

    def test_files_workspace_is_gated(self) -> None:
        src = read("components/chat/FilesSheet.tsx")
        assert "computerAvailable" in src
        assert "computerLive" in src


class TestInspectorComputerCard:
    def test_computer_card_is_conditional(self) -> None:
        src = read("components/inspector/BotInspectorPanel.tsx")
        # The whole Computer block is behind the probe summary.
        assert "{computerStatus?.available && (" in src
        assert '<section className="inspector__block" aria-label="Computer">' in src

    def test_computer_card_states_are_real(self) -> None:
        src = read("components/inspector/BotInspectorPanel.tsx")
        # The card comes from the real per-bot record, not a stub.
        assert "s.byBot[bot.id]" in src
        src_card = read("components/computer/ComputerStateCard.tsx")
        for state in ("off", "asleep", "building", "starting", "awake", "needs_you"):
            assert f"'{state}'" in src_card, state

    def test_voice_rows_use_real_settings(self) -> None:
        src = read("components/inspector/BotInspectorPanel.tsx")
        assert "useVoiceStore" in src
        assert "voiceSettings.ttsVoice" in src


class TestNoCloudComputer:
    """Design 09's "Use a cloud computer instead" has no real backend."""

    def test_no_cloud_cta_anywhere_in_the_ui(self) -> None:
        for relative in UI_FILES:
            assert "cloud" not in read(relative).lower(), relative

    def test_no_cloud_route_in_the_backend(self) -> None:
        routes = Path(__file__).resolve().parent.parent / "cachibot" / "api" / "routes"
        src = (routes / "computer.py").read_text(encoding="utf-8")
        assert "cloud" not in src.lower()


class TestOpenOnComputer:
    def test_action_is_conditional(self) -> None:
        src = read("components/chat/FilesSheet.tsx")
        assert "Open on computer" in src
        # Only for a live computer (awake/needs_you), bot scope, feature on.
        assert "computerState === 'awake' || computerState === 'needs_you'" in src
        # Operator-only (the API enforces operator+).
        assert "canOperate && (" in src

    def test_backend_route_is_operator_gated(self) -> None:
        src = (
            Path(__file__).resolve().parent.parent / "cachibot" / "api" / "routes" / "computer.py"
        ).read_text(encoding="utf-8")
        assert "editor/open" in src
        assert "BotAccessLevel.OPERATOR" in src

    def test_listing_route_never_wakes_the_computer(self) -> None:
        src = (
            Path(__file__).resolve().parent.parent
            / "cachibot"
            / "services"
            / "computer"
            / "service.py"
        ).read_text(encoding="utf-8")
        assert "Browsing never boots the computer" in src
        assert "allow_wake=False" in src


class TestTakeOverAndNeedsYou:
    def test_skip_uses_the_needs_you_respond_api(self) -> None:
        src = read("components/computer/ComputerOpenView.tsx")
        assert "respondNeedsYou(bot.id, 'skip')" in src
        assert "respondNeedsYou(bot.id, 'takeover')" in src

    def test_input_only_while_driving(self) -> None:
        src = read("components/computer/ComputerOpenView.tsx")
        assert "if (!driving) return" in src
        assert "sendComputerInput" in src
        # Right click is forwarded as a right-button click.
        assert "button: 'right'" in src

    def test_control_buttons_require_operator(self) -> None:
        src = read("components/computer/ComputerOpenView.tsx")
        assert "access.canOperate" in src
        panel = read("components/computer/ComputerSection.tsx")
        assert "canOperate" in panel


class TestExplainerFacts:
    def test_facts_are_the_true_ones(self) -> None:
        src = read("components/computer/utils.ts")
        assert "This PC · Docker" in src
        assert "The internet, not your network" in src
        assert "/workspace between runs" in src
        assert "After 10 min idle" in src

    def test_no_other_idle_number_in_copy(self) -> None:
        # The configured idle value is not exposed to the UI; 10 minutes is
        # the shipped default. No other number may appear in copy.
        for relative in UI_FILES:
            src = read(relative).lower()
            for token in ("5 min", "15 min", "20 min", "30 min", "60 min"):
                assert token not in src, f"{relative}: {token}"


class TestNoAiToolMentions:
    def test_new_files_mention_no_ai_tool(self) -> None:
        # Case-sensitive: CSS `cursor:` and DOM `cursor` styles are unrelated
        # to the tool name.
        banned = ("Claude", "Cursor", "Kimi", "Copilot", "ChatGPT", "GPT-")
        new_files = COMPUTER_COMPONENTS + [
            "components/inspector/BotInspectorPanel.tsx",
            "styles/v2/computer.less",
            "styles/v2/inspector.less",
        ]
        for relative in new_files:
            src = read(relative)
            for word in banned:
                assert word not in src, f"{relative}: {word}"

    def test_computer_additions_in_touched_files_mention_no_ai_tool(self) -> None:
        # In pre-existing files the scan covers only the computer-related
        # lines added in this pass (the rest of those files predates it).
        banned = ("Claude", "Cursor", "Kimi", "Copilot", "ChatGPT", "GPT-")
        touched = [
            "components/views/ChatView.tsx",
            "components/views/BotSettingsView.tsx",
            "components/chat/FilesSheet.tsx",
            "components/chat/ChatCards.tsx",
        ]
        for relative in touched:
            for line in read(relative).splitlines():
                if "computer" not in line.lower():
                    continue
                for word in banned:
                    assert word not in line, f"{relative}: {word}"
