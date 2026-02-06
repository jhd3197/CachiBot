"""
Tests for Cachibot
"""

import tempfile
from pathlib import Path

import pytest

from cachibot.config import Config
from cachibot.tools import ToolResult
from cachibot.tools.filesystem import (
    FileEditTool,
    FileListTool,
    FileReadTool,
    FileWriteTool,
)


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
        assert config.agent.model == "claude-sonnet-4-20250514"
        assert config.agent.max_iterations == 20
        assert config.tools.powershell is True
        assert config.tools.filesystem is True
    
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


class TestToolResult:
    """Tests for ToolResult."""
    
    def test_ok_result(self):
        """Test successful result creation."""
        result = ToolResult.ok("output")
        assert result.success is True
        assert result.output == "output"
        assert result.error == ""
    
    def test_fail_result(self):
        """Test failed result creation."""
        result = ToolResult.fail("error message")
        assert result.success is False
        assert result.output == ""
        assert result.error == "error message"


class TestFileReadTool:
    """Tests for file read tool."""
    
    def test_read_existing_file(self, config, temp_workspace):
        """Test reading an existing file."""
        # Create a test file
        test_file = temp_workspace / "test.txt"
        test_file.write_text("Hello, World!")
        
        tool = FileReadTool(config)
        result = tool.execute(path="test.txt")
        
        assert result.success is True
        assert result.output == "Hello, World!"
    
    def test_read_nonexistent_file(self, config):
        """Test reading a file that doesn't exist."""
        tool = FileReadTool(config)
        result = tool.execute(path="nonexistent.txt")
        
        assert result.success is False
        assert "not found" in result.error.lower()
    
    def test_read_outside_workspace(self, config):
        """Test reading a file outside workspace."""
        tool = FileReadTool(config)
        result = tool.execute(path="/etc/passwd")
        
        assert result.success is False
        assert "outside" in result.error.lower()


class TestFileWriteTool:
    """Tests for file write tool."""
    
    def test_write_new_file(self, config, temp_workspace):
        """Test writing a new file."""
        tool = FileWriteTool(config)
        result = tool.execute(path="new_file.txt", content="Test content")
        
        assert result.success is True
        
        # Verify file was created
        created_file = temp_workspace / "new_file.txt"
        assert created_file.exists()
        assert created_file.read_text() == "Test content"
    
    def test_write_with_directories(self, config, temp_workspace):
        """Test writing a file with directory creation."""
        tool = FileWriteTool(config)
        result = tool.execute(
            path="subdir/nested/file.txt",
            content="Nested content",
            create_directories=True,
        )
        
        assert result.success is True
        
        created_file = temp_workspace / "subdir/nested/file.txt"
        assert created_file.exists()


class TestFileEditTool:
    """Tests for file edit tool."""
    
    def test_edit_file(self, config, temp_workspace):
        """Test editing a file."""
        # Create a test file
        test_file = temp_workspace / "edit_me.txt"
        test_file.write_text("Hello, World!")
        
        tool = FileEditTool(config)
        result = tool.execute(
            path="edit_me.txt",
            old_text="World",
            new_text="Cachibot",
        )
        
        assert result.success is True
        assert test_file.read_text() == "Hello, Cachibot!"
    
    def test_edit_text_not_found(self, config, temp_workspace):
        """Test editing with text that doesn't exist."""
        test_file = temp_workspace / "edit_me.txt"
        test_file.write_text("Hello, World!")
        
        tool = FileEditTool(config)
        result = tool.execute(
            path="edit_me.txt",
            old_text="Nonexistent",
            new_text="Replacement",
        )
        
        assert result.success is False
        assert "not find" in result.error.lower()


class TestFileListTool:
    """Tests for file list tool."""
    
    def test_list_directory(self, config, temp_workspace):
        """Test listing a directory."""
        # Create some files
        (temp_workspace / "file1.txt").touch()
        (temp_workspace / "file2.py").touch()
        (temp_workspace / "subdir").mkdir()
        
        tool = FileListTool(config)
        result = tool.execute(path=".")
        
        assert result.success is True
        assert "file1.txt" in result.output
        assert "file2.py" in result.output
        assert "subdir" in result.output
    
    def test_list_with_pattern(self, config, temp_workspace):
        """Test listing with glob pattern."""
        (temp_workspace / "file1.txt").touch()
        (temp_workspace / "file2.py").touch()
        
        tool = FileListTool(config)
        result = tool.execute(path=".", pattern="*.py")
        
        assert result.success is True
        # Pattern filtering happens at the tool level
