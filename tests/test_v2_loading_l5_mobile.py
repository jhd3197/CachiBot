"""Source assertions for the L5 mobile loading pass (mobile/).

Hermetic: reads the source files only — no flutter, no node, no build,
no network, no server. Guards the load-bearing rules of the pass:
- no raw CircularProgressIndicator / LinearProgressIndicator remains under
  mobile/lib outside widgets/common/loading.dart (the shared widgets);
- the quiet boot exists: BootScreen widget, a /boot route, and an
  AuthState.isRestoring flag that every restoreSession path clears, so the
  router redirect can never deadlock on the boot screen;
- the v2 boot palette lives in AppColors as named constants;
- the Android and iOS launch backgrounds no longer use plain white and
  carry the v2 boot background (light #F4F4F5, dark #0B0C0E).
"""

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MOBILE = REPO / "mobile"
MOBILE_LIB = MOBILE / "lib"
LOADING_DART = MOBILE_LIB / "widgets" / "common" / "loading.dart"

RAW_INDICATOR_TOKENS = ("CircularProgressIndicator", "LinearProgressIndicator")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_lib(relative: str) -> str:
    return read(MOBILE_LIB / relative)


class TestNoRawMaterialIndicators:
    """Every loading state goes through the shared widgets."""

    def test_only_loading_dart_mentions_raw_indicators(self) -> None:
        offenders = []
        for path in sorted(MOBILE_LIB.rglob("*.dart")):
            if path == LOADING_DART:
                continue
            text = read(path)
            for token in RAW_INDICATOR_TOKENS:
                if token in text:
                    offenders.append(f"{path.relative_to(MOBILE_LIB)}: {token}")
        assert not offenders, "\n".join(offenders)

    def test_shared_widgets_exist(self) -> None:
        src = read(LOADING_DART)
        for name in (
            "CachiSpinner",
            "CachiPageLoading",
            "CachiSkeleton",
            "CachiSkeletonList",
            "CachiProgressBar",
        ):
            assert f"class {name}" in src, name

    def test_spinner_respects_disabled_animations_and_cancels_timer(self) -> None:
        src = read(LOADING_DART)
        assert "MediaQuery.disableAnimationsOf" in src
        assert "_delayTimer?.cancel()" in src
        assert "Semantics(" in src


class TestQuietBoot:
    def test_boot_screen_exists_with_wordmark(self) -> None:
        src = read_lib("widgets/common/boot_screen.dart")
        assert "class BootScreen" in src
        assert "'Cachi'" in src
        assert "'Bot'" in src

    def test_v2_boot_colors_are_named_constants(self) -> None:
        src = read_lib("core/theme/app_colors.dart")
        assert "v2BootBackgroundDark = Color(0xFF0B0C0E)" in src
        assert "v2BootBackgroundLight = Color(0xFFF4F4F5)" in src
        assert "v2BootGreenDark = Color(0xFF4ADE80)" in src
        assert "v2BootGreenLight = Color(0xFF16A34A)" in src

    def test_auth_state_has_is_restoring(self) -> None:
        src = read_lib("providers/auth_provider.dart")
        assert "this.isRestoring = true" in src
        assert "final bool isRestoring;" in src

    def test_every_restore_path_clears_is_restoring(self) -> None:
        src = read_lib("providers/auth_provider.dart")
        restore = src.split("Future<void> restoreSession()")[1]
        restore_body = restore.split("/// Clear biometric requirement")[0]
        assert "isRestoring: false" in restore_body
        assert "isRestoring: false" in restore_body.split("catch")[1]
        # No path may leave isRestoring unset in the failure state.
        assert "const AuthState(isRestoring: false)" in restore_body

    def test_router_holds_on_boot_route(self) -> None:
        src = read_lib("core/router.dart")
        assert "path: '/boot'" in src
        assert "BootScreen" in src
        assert "authState.isRestoring" in src


class TestLaunchBackgrounds:
    def test_android_launch_background_not_white(self) -> None:
        res = MOBILE / "android" / "app" / "src" / "main" / "res"
        for variant in (
            res / "drawable" / "launch_background.xml",
            res / "drawable-v21" / "launch_background.xml",
            res / "drawable-night" / "launch_background.xml",
        ):
            text = read(variant)
            assert "@android:color/white" not in text, variant
            assert "@color/boot_background" in text, variant

    def test_android_boot_colors_defined(self) -> None:
        text = read(MOBILE / "android" / "app" / "src" / "main" / "res" / "values" / "colors.xml")
        assert "#F4F4F5" in text
        assert "#0B0C0E" in text

    def test_android_night_variant_uses_dark_color(self) -> None:
        text = read(
            MOBILE
            / "android"
            / "app"
            / "src"
            / "main"
            / "res"
            / "drawable-night"
            / "launch_background.xml"
        )
        assert "@color/boot_background_dark" in text

    def test_ios_launch_background_not_white(self) -> None:
        storyboard = read(MOBILE / "ios" / "Runner" / "Base.lproj" / "LaunchScreen.storyboard")
        assert 'red="1" green="1" blue="1"' not in storyboard
        assert 'name="BootBackground"' in storyboard
        # The existing launch image is kept.
        assert 'image="LaunchImage"' in storyboard

    def test_ios_boot_background_color_asset(self) -> None:
        asset = read(
            MOBILE
            / "ios"
            / "Runner"
            / "Assets.xcassets"
            / "BootBackground.colorset"
            / "Contents.json"
        )
        assert '"0.957"' in asset  # 244/255 (light)
        assert '"0.043"' in asset  # 11/255 (dark)
        assert '"luminosity"' in asset
