"""
Tests for Cachibot
"""

import tempfile
from pathlib import Path

import pytest

from cachibot.config import Config


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def config(temp_workspace):
    """Create a config with the temp workspace."""
    return Config.load(workspace=temp_workspace)


class TestConfig:
    """Tests for configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = Config()
        assert config.agent.max_iterations == 20

    def test_is_path_allowed(self, config, temp_workspace):
        """Test path validation."""
        # Path within workspace should be allowed
        assert config.is_path_allowed(temp_workspace / "test.txt")

        # Path outside workspace should not be allowed
        assert not config.is_path_allowed("/etc/passwd")
        assert not config.is_path_allowed("C:\\Windows\\System32")

    def test_should_ignore(self, config):
        """Test ignore patterns."""
        assert config.should_ignore("node_modules")
        assert config.should_ignore(".git")
        assert config.should_ignore("test.pyc")
        assert not config.should_ignore("test.py")
