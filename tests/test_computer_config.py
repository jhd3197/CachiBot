"""Tests for the [computer] config keys: shipped defaults, environment
overrides and cachibot.toml overrides (C5 resource caps)."""

import pytest

from cachibot.config import ComputerConfig, Config


class TestComputerConfigDefaults:
    def test_shipped_defaults(self) -> None:
        config = ComputerConfig()
        assert config.enabled is True
        assert config.idle_minutes == 10
        assert config.memory == "2g"
        assert config.cpus == 2.0
        assert config.pids_limit == 1024


class TestComputerConfigEnv:
    def test_env_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CACHIBOT_COMPUTER_MEMORY", "4g")
        monkeypatch.setenv("CACHIBOT_COMPUTER_CPUS", "1.5")
        monkeypatch.setenv("CACHIBOT_COMPUTER_PIDS_LIMIT", "256")
        config = Config()
        config._load_from_env()
        assert config.computer.memory == "4g"
        assert config.computer.cpus == 1.5
        assert config.computer.pids_limit == 256

    def test_invalid_env_values_are_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CACHIBOT_COMPUTER_CPUS", "lots")
        monkeypatch.setenv("CACHIBOT_COMPUTER_PIDS_LIMIT", "many")
        config = Config()
        config._load_from_env()
        assert config.computer.cpus == 2.0
        assert config.computer.pids_limit == 1024


class TestComputerConfigToml:
    def test_toml_overrides(self, tmp_path) -> None:
        toml = tmp_path / "cachibot.toml"
        toml.write_text(
            '[computer]\nmemory = "8g"\ncpus = 4.0\npids_limit = 2048\n',
            encoding="utf-8",
        )
        config = Config()
        config._load_from_file(toml)
        assert config.computer.memory == "8g"
        assert config.computer.cpus == 4.0
        assert config.computer.pids_limit == 2048

    def test_toml_can_uncap(self, tmp_path) -> None:
        toml = tmp_path / "cachibot.toml"
        toml.write_text('[computer]\nmemory = ""\ncpus = 0\npids_limit = 0\n', encoding="utf-8")
        config = Config()
        config._load_from_file(toml)
        assert config.computer.memory == ""
        assert config.computer.cpus == 0
        assert config.computer.pids_limit == 0
