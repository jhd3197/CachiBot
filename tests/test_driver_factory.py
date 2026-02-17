"""Tests for the driver factory — builds Prompture async drivers with explicit API keys.

Covers:
- build_driver_with_key creates correct driver type for each provider
- Falls back to registry when no api_key provided
- Unknown provider raises ValueError
- Extra kwargs forwarded to driver constructor
"""

from unittest.mock import MagicMock, patch

import pytest

from cachibot.services.driver_factory import DRIVER_MAP, build_driver_with_key


# ---------------------------------------------------------------------------
# Driver Type Tests
# ---------------------------------------------------------------------------


class TestDriverTypeMapping:
    """Verify that each provider in DRIVER_MAP resolves to the correct driver class."""

    @pytest.mark.parametrize(
        "provider,expected_class",
        [
            ("openai", "AsyncOpenAIDriver"),
            ("claude", "AsyncClaudeDriver"),
            ("anthropic", "AsyncClaudeDriver"),
            ("google", "AsyncGoogleDriver"),
            ("gemini", "AsyncGoogleDriver"),
            ("groq", "AsyncGroqDriver"),
            ("grok", "AsyncGrokDriver"),
            ("xai", "AsyncGrokDriver"),
            ("openrouter", "AsyncOpenRouterDriver"),
            ("moonshot", "AsyncMoonshotDriver"),
        ],
    )
    def test_driver_map_entries(self, provider, expected_class):
        """Each provider maps to the expected driver class name."""
        module_path, class_name = DRIVER_MAP[provider]
        assert class_name == expected_class
        assert "prompture.drivers." in module_path

    def test_all_known_providers_in_map(self):
        """All major providers have entries in DRIVER_MAP."""
        required = {"openai", "claude", "google", "groq", "grok", "openrouter", "moonshot"}
        assert required.issubset(DRIVER_MAP.keys())


class TestBuildDriverWithKey:
    """Tests for the build_driver_with_key factory function."""

    def test_with_explicit_key_creates_driver(self):
        """Providing an api_key creates a driver directly (bypasses registry)."""
        mock_cls = MagicMock()
        mock_module = MagicMock()
        mock_module.AsyncOpenAIDriver = mock_cls

        with patch("cachibot.services.driver_factory.importlib") as mock_importlib:
            mock_importlib.import_module.return_value = mock_module
            driver = build_driver_with_key("openai/gpt-4o", api_key="sk-test-key")

        mock_cls.assert_called_once_with(api_key="sk-test-key", model="gpt-4o")
        assert driver == mock_cls.return_value

    def test_without_key_falls_to_registry(self):
        """When no api_key is provided, falls back to get_async_driver_for_model."""
        mock_registry_fn = MagicMock(return_value="registry-driver")

        with patch(
            "cachibot.services.driver_factory.get_async_driver_for_model",
            mock_registry_fn,
            create=True,
        ):
            # We need to patch at the call site — the function imports lazily
            with patch(
                "prompture.drivers.async_registry.get_async_driver_for_model",
                mock_registry_fn,
            ):
                driver = build_driver_with_key("openai/gpt-4o")

        mock_registry_fn.assert_called_once_with("openai/gpt-4o")
        assert driver == "registry-driver"

    def test_unknown_provider_raises_value_error(self):
        """Unknown provider in model string raises ValueError."""
        with pytest.raises(ValueError, match="Unknown provider"):
            build_driver_with_key("unknownprovider/some-model", api_key="sk-test")

    def test_extra_kwargs_forwarded(self):
        """Extra kwargs (e.g., endpoint) are forwarded to the driver constructor."""
        mock_cls = MagicMock()
        mock_module = MagicMock()
        mock_module.AsyncAzureDriver = mock_cls

        with patch("cachibot.services.driver_factory.importlib") as mock_importlib:
            mock_importlib.import_module.return_value = mock_module
            build_driver_with_key(
                "azure/gpt-4o",
                api_key="sk-azure-key",
                endpoint="https://myresource.openai.azure.com",
            )

        mock_cls.assert_called_once_with(
            api_key="sk-azure-key",
            model="gpt-4o",
            endpoint="https://myresource.openai.azure.com",
        )

    def test_model_without_slash(self):
        """Model string without a slash uses the provider with no model_id."""
        mock_cls = MagicMock()
        mock_module = MagicMock()
        mock_module.AsyncOllamaDriver = mock_cls

        with patch("cachibot.services.driver_factory.importlib") as mock_importlib:
            mock_importlib.import_module.return_value = mock_module
            build_driver_with_key("ollama", api_key="dummy", endpoint="http://localhost:11434")

        # model should not be passed when there's no slash
        call_kwargs = mock_cls.call_args[1]
        assert "model" not in call_kwargs or call_kwargs.get("model") is None

    def test_case_insensitive_provider(self):
        """Provider name matching is case-insensitive."""
        mock_cls = MagicMock()
        mock_module = MagicMock()
        mock_module.AsyncOpenAIDriver = mock_cls

        with patch("cachibot.services.driver_factory.importlib") as mock_importlib:
            mock_importlib.import_module.return_value = mock_module
            build_driver_with_key("OpenAI/gpt-4o", api_key="sk-test")

        mock_cls.assert_called_once()


# ---------------------------------------------------------------------------
# API Key Isolation via Driver
# ---------------------------------------------------------------------------


class TestDriverKeyIsolation:
    """Verify that each driver instance gets its own api_key."""

    def test_two_drivers_different_keys(self):
        """Two drivers created for the same provider get different api_keys."""
        mock_cls = MagicMock()
        mock_module = MagicMock()
        mock_module.AsyncOpenAIDriver = mock_cls

        with patch("cachibot.services.driver_factory.importlib") as mock_importlib:
            mock_importlib.import_module.return_value = mock_module

            driver_a = build_driver_with_key("openai/gpt-4o", api_key="sk-AAA")
            driver_b = build_driver_with_key("openai/gpt-4o", api_key="sk-BBB")

        calls = mock_cls.call_args_list
        assert len(calls) == 2
        assert calls[0][1]["api_key"] == "sk-AAA"
        assert calls[1][1]["api_key"] == "sk-BBB"

    def test_driver_key_not_in_environ(self):
        """Building a driver with an explicit key should NOT set os.environ."""
        import os

        mock_cls = MagicMock()
        mock_module = MagicMock()
        mock_module.AsyncOpenAIDriver = mock_cls

        original = os.environ.get("OPENAI_API_KEY")

        with patch("cachibot.services.driver_factory.importlib") as mock_importlib:
            mock_importlib.import_module.return_value = mock_module
            build_driver_with_key("openai/gpt-4o", api_key="sk-SHOULD-NOT-BE-IN-ENV")

        assert os.environ.get("OPENAI_API_KEY") != "sk-SHOULD-NOT-BE-IN-ENV"
