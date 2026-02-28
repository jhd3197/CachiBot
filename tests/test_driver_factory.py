"""Tests for the driver factory — builds Prompture async drivers with explicit API keys.

Covers:
- build_driver_with_key delegates to get_async_driver_for_model
- api_key and extra kwargs are forwarded
- No api_key falls back to registry defaults
"""

from unittest.mock import MagicMock, patch

from cachibot.services.driver_factory import build_driver_with_key


class TestBuildDriverWithKey:
    """Tests for the build_driver_with_key factory function."""

    def test_delegates_to_registry(self):
        """Calls get_async_driver_for_model with the model string."""
        mock_fn = MagicMock(return_value="mock-driver")

        with patch(
            "cachibot.services.driver_factory.get_async_driver_for_model",
            mock_fn,
        ):
            result = build_driver_with_key("openai/gpt-4o")

        mock_fn.assert_called_once_with("openai/gpt-4o", api_key=None)
        assert result == "mock-driver"

    def test_forwards_api_key(self):
        """Explicit api_key is forwarded to the registry function."""
        mock_fn = MagicMock(return_value="keyed-driver")

        with patch(
            "cachibot.services.driver_factory.get_async_driver_for_model",
            mock_fn,
        ):
            result = build_driver_with_key("openai/gpt-4o", api_key="sk-test")

        mock_fn.assert_called_once_with("openai/gpt-4o", api_key="sk-test")
        assert result == "keyed-driver"

    def test_forwards_extra_kwargs(self):
        """Extra kwargs (e.g. endpoint) are forwarded."""
        mock_fn = MagicMock(return_value="extra-driver")

        with patch(
            "cachibot.services.driver_factory.get_async_driver_for_model",
            mock_fn,
        ):
            build_driver_with_key(
                "azure/gpt-4o",
                api_key="sk-azure",
                endpoint="https://myresource.openai.azure.com",
            )

        mock_fn.assert_called_once_with(
            "azure/gpt-4o",
            api_key="sk-azure",
            endpoint="https://myresource.openai.azure.com",
        )

    def test_two_drivers_get_different_keys(self):
        """Two calls with different keys produce independent drivers."""
        mock_fn = MagicMock(side_effect=["driver-A", "driver-B"])

        with patch(
            "cachibot.services.driver_factory.get_async_driver_for_model",
            mock_fn,
        ):
            a = build_driver_with_key("openai/gpt-4o", api_key="sk-AAA")
            b = build_driver_with_key("openai/gpt-4o", api_key="sk-BBB")

        assert a == "driver-A"
        assert b == "driver-B"
        calls = mock_fn.call_args_list
        assert calls[0][1]["api_key"] == "sk-AAA"
        assert calls[1][1]["api_key"] == "sk-BBB"
