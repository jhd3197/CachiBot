"""Source assertions for the mobile computer surface (mobile/lib).

Hermetic: reads the Dart sources only — no Flutter SDK, no build, no
network (the mobile CI job runs ``flutter analyze``). Guards the
load-bearing rules of the pass:
- every computer entry point and the screen itself gate on the Docker probe
  (``status.available``) — no dead Computer button when Docker is off;
- the client calls the documented C2 computer routes, frames go out as raw
  bytes with the ETag/304 contract, and a preview never wakes the computer;
- take-over touch gestures map to the documented input kinds (tap = click,
  long-press = right click, drag = scroll, keyboard = type/key) and input
  goes out only while the signed-in user holds the take-over;
- watching heartbeats run only while the screen is mounted and visible;
- no placeholder frames, invented window titles or cloud-computer CTAs;
- the maintainer's no-AI-tools rule holds in the new/changed mobile files.
"""

from pathlib import Path

MOBILE = Path(__file__).resolve().parent.parent / "mobile" / "lib"

NEW_FILES = [
    "models/computer.dart",
    "services/api/computer_service.dart",
    "providers/computer_provider.dart",
    "screens/bot/computer_screen.dart",
]

TOUCHED_FILES = [
    "core/router.dart",
    "screens/bot/bot_detail_screen.dart",
    "screens/chat/chat_screen.dart",
    "models/ws_message.dart",
    "models/bot.dart",
]


def read(relative: str) -> str:
    return (MOBILE / relative).read_text(encoding="utf-8")


class TestAvailabilityGates:
    """No computer UI renders while the Docker probe says unavailable."""

    def test_bot_detail_entry_is_gated(self) -> None:
        src = read("screens/bot/bot_detail_screen.dart")
        assert "computerAvailable" in src
        assert "status?.available == true" in src
        # The entry only renders inside the availability gate.
        assert "if (computerAvailable)" in src
        assert "/computer" in src

    def test_chat_entry_is_gated(self) -> None:
        src = read("screens/chat/chat_screen.dart")
        assert "status?.available == true" in src
        assert "/computer" in src

    def test_screen_renders_nothing_when_unavailable(self) -> None:
        src = read("screens/bot/computer_screen.dart")
        assert "status?.available == true" in src
        assert "SizedBox.shrink()" in src

    def test_store_treats_failed_probe_as_unavailable(self) -> None:
        src = read("providers/computer_provider.dart")
        assert "DockerProbeStatus.unavailable" in src

    def test_router_entry_is_full_screen(self) -> None:
        src = read("core/router.dart")
        assert "path: 'computer'" in src
        after = src.split("path: 'computer'", 1)[1]
        assert "parentNavigatorKey: _rootNavigatorKey" in after[:300]
        assert "ComputerScreen" in after[:300]


class TestDocumentedRoutes:
    """The client calls exactly the C2 computer routes."""

    def test_all_routes_present(self) -> None:
        src = read("services/api/computer_service.dart")
        for route in (
            "'/api/computer/status'",
            "'/api/bots/$botId/computer'",
            "'/api/bots/$botId/computer/wake'",
            "'/api/bots/$botId/computer/preview'",
            "'/api/bots/$botId/computer/views'",
            "'/api/bots/$botId/computer/views/$viewId/frame'",
            "'/api/bots/$botId/computer/watch'",
            "'/api/bots/$botId/computer/takeover'",
            "'/api/bots/$botId/computer/handback'",
            "'/api/bots/$botId/computer/input'",
            "'/api/bots/$botId/computer/needs-you/respond'",
        ):
            assert route in src, route

    def test_frames_are_bytes_with_the_etag_contract(self) -> None:
        src = read("services/api/computer_service.dart")
        assert "ResponseType.bytes" in src
        assert "'If-None-Match'" in src
        assert "status == 304" in src

    def test_client_uses_the_authenticated_api_client(self) -> None:
        src = read("providers/computer_provider.dart")
        assert "ref.watch(apiClientProvider)" in src

    def test_needs_you_respond_sends_the_action(self) -> None:
        src = read("services/api/computer_service.dart")
        assert "{'action': action}" in src

    def test_ws_computer_update_constant_and_handling(self) -> None:
        ws = read("models/ws_message.dart")
        assert "static const String computerUpdate = 'computer_update';" in ws
        provider = read("providers/computer_provider.dart")
        assert "WSEvent.computerUpdate" in provider
        assert "applyUpdate" in provider


class TestTakeOverGestures:
    """Tap = click, long-press = right click, drag = scroll, keyboard =
    type/key — only while the signed-in user holds the take-over."""

    def test_tap_is_a_left_click(self) -> None:
        src = read("screens/bot/computer_screen.dart")
        assert "onTapUp" in src
        assert "'kind': 'click'" in src
        assert "'button': 'left'" in src

    def test_long_press_is_a_right_click(self) -> None:
        src = read("screens/bot/computer_screen.dart")
        assert "onLongPressStart" in src
        assert "'button': 'right'" in src

    def test_drag_is_a_scroll(self) -> None:
        src = read("screens/bot/computer_screen.dart")
        assert "onPanUpdate" in src
        assert "'kind': 'scroll'" in src

    def test_keyboard_sends_type_and_key(self) -> None:
        src = read("screens/bot/computer_screen.dart")
        assert "'kind': 'type'" in src
        assert "'kind': 'key'" in src

    def test_input_only_while_this_user_drives(self) -> None:
        src = read("screens/bot/computer_screen.dart")
        assert "if (!_drivingMe) return;" in src
        # "You're driving" is compared against the signed-in user's id.
        assert "computer!.driver!.userId == user?.id" in src

    def test_coordinates_map_through_the_natural_size(self) -> None:
        src = read("screens/bot/computer_screen.dart")
        assert "_pointFor" in src
        assert "natural.width" in src
        # A zero size means there is no honest mapping — skip the input.
        assert "size.width == 0" in src

    def test_zoom_and_pan_via_interactive_viewer(self) -> None:
        src = read("screens/bot/computer_screen.dart")
        assert "InteractiveViewer" in src
        assert "Image.memory" in src


class TestWatchAndStates:
    def test_heartbeat_while_mounted_and_visible(self) -> None:
        src = read("screens/bot/computer_screen.dart")
        assert "Timer.periodic(_heartbeatInterval" in src
        assert ".watch(widget.botId)" in src
        # Hidden (backgrounded) and unmounted both stop the timers.
        assert "didChangeAppLifecycleState" in src
        assert "_stopTimers()" in src

    def test_control_buttons_require_operator(self) -> None:
        src = read("screens/bot/computer_screen.dart")
        assert "canOperate" in src
        bot = read("models/bot.dart")
        assert "json['access_level']" in bot

    def test_a_403_hides_the_control_that_failed(self) -> None:
        src = read("providers/computer_provider.dart")
        assert "controlDenied" in src
        assert "isForbidden" in src or "403" in src

    def test_off_and_asleep_offer_the_real_wake(self) -> None:
        src = read("screens/bot/computer_screen.dart")
        assert "'Turn on'" in src
        assert "'Wake'" in src
        assert ".wake(widget.botId)" in src

    def test_needs_you_shows_the_reason_with_takeover_and_skip(self) -> None:
        src = read("screens/bot/computer_screen.dart")
        assert "respondNeedsYou(widget.botId, 'takeover')" in src
        assert "respondNeedsYou(widget.botId, 'skip')" in src

    def test_build_progress_uses_only_real_build_fields(self) -> None:
        src = read("screens/bot/computer_screen.dart")
        assert "build?.step" in src
        assert "build?.total" in src
        assert "build?.line" in src

    def test_window_switcher_comes_from_the_real_views_list(self) -> None:
        src = read("screens/bot/computer_screen.dart")
        assert "windowsByBot" in src
        assert "_WindowSwitcher" in src


class TestNoFakeData:
    """No placeholder frames, invented content or cloud-computer CTAs."""

    PLACEHOLDER_TOKENS = (
        "placehold.co",
        "via.placeholder",
        "picsum",
        "dummyimage",
        "loremflickr",
        "unsplash",
        "lorem ipsum",
    )

    def test_no_placeholder_urls_or_network_images(self) -> None:
        for relative in NEW_FILES:
            src = read(relative).lower()
            for token in self.PLACEHOLDER_TOKENS:
                assert token not in src, f"{relative}: {token}"
            # Frames come from the authenticated API as bytes — never from
            # a URL the widget fetched on its own.
            assert "image.network" not in src, relative

    def test_no_cloud_computer_cta(self) -> None:
        for relative in NEW_FILES:
            assert "cloud" not in read(relative).lower(), relative

    def test_no_hard_coded_frame_or_window_data(self) -> None:
        # Window titles, apps and activity come from the views/status
        # payloads; the screen must not ship invented ones.
        src = read("screens/bot/computer_screen.dart")
        assert "ComputerWindow(" not in src


class TestNoAiToolMentions:
    def test_new_files_mention_no_ai_tool(self) -> None:
        banned = ("Claude", "Cursor", "Kimi", "Copilot", "ChatGPT", "GPT-")
        for relative in NEW_FILES:
            src = read(relative)
            for word in banned:
                assert word not in src, f"{relative}: {word}"

    def test_computer_additions_in_touched_files_mention_no_ai_tool(self) -> None:
        # In pre-existing files the scan covers only the computer-related
        # lines added in this pass (the rest of those files predates it).
        banned = ("Claude", "Cursor", "Kimi", "Copilot", "ChatGPT", "GPT-")
        for relative in TOUCHED_FILES:
            for line in read(relative).splitlines():
                if "computer" not in line.lower():
                    continue
                for word in banned:
                    assert word not in line, f"{relative}: {word}"
