"""Tests for configuration management."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from ragdiff.core.config import Config
from ragdiff.core.models import ToolConfig


class TestConfig:
    """Test configuration management."""

    @pytest.fixture
    def temp_config_file(self):
        """Create temporary configuration file."""
        config_data = {
            "tools": {
                "goodmem": {
                    "name": "goodmem",
                    "api_key_env": "GOODMEM_KEY",
                    "timeout": 30,
                    "default_top_k": 5,
                },
                "mawsuah": {
                    "name": "mawsuah",
                    "api_key_env": "VECTARA_KEY",
                    "corpus_id": "corpus123",
                    "timeout": 45,
                },
            },
            "llm": {
                "model": "claude-opus-4-1",
                "api_key_env": "ANTHROPIC_KEY",
                "temperature": 0.3,
            },
            "output": {"formats": ["console", "jsonl"], "output_dir": "outputs"},
            "display": {"max_text_length": 500, "highlight_differences": True},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = Path(f.name)

        yield temp_path

        # Cleanup
        temp_path.unlink()

    def test_load_config(self, temp_config_file):
        """Test loading configuration from file."""
        config = Config(temp_config_file)
        assert config.config_path == temp_config_file
        assert "goodmem" in config.tools
        assert "mawsuah" in config.tools

    def test_missing_config_file(self):
        """Test error when config file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            Config(Path("/nonexistent/config.yaml"))

    @patch.dict(os.environ, {"VECTARA_CORPUS": "corpus456"})
    def test_env_var_substitution(self, temp_config_file):
        """Test environment variable substitution."""
        # First update the config to use env var for corpus_id
        config_data = {
            "tools": {
                "goodmem": {
                    "name": "goodmem",
                    "api_key_env": "GOODMEM_KEY",
                    "timeout": 30,
                    "default_top_k": 5,
                },
                "mawsuah": {
                    "name": "mawsuah",
                    "api_key_env": "VECTARA_KEY",
                    "corpus_id": "${VECTARA_CORPUS}",
                    "timeout": 45,
                },
            },
            "llm": {
                "model": "claude-opus-4-1",
                "api_key_env": "ANTHROPIC_KEY",
                "temperature": 0.3,
            },
        }
        import tempfile
        from pathlib import Path

        import yaml

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = Path(f.name)

        try:
            config = Config(temp_path)
            mawsuah_config = config.get_tool_config("mawsuah")
            assert mawsuah_config.corpus_id == "corpus456"
        finally:
            temp_path.unlink()

    def test_env_var_not_set(self, temp_config_file):
        """Test behavior when environment variable is not set."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config(temp_config_file)
            mawsuah_config = config.get_tool_config("mawsuah")
            # corpus_id should be present
            assert mawsuah_config.corpus_id == "corpus123"

    def test_get_tool_config(self, temp_config_file):
        """Test getting tool configuration."""
        config = Config(temp_config_file)

        goodmem = config.get_tool_config("goodmem")
        assert isinstance(goodmem, ToolConfig)
        assert goodmem.name == "goodmem"
        assert goodmem.api_key_env == "GOODMEM_KEY"
        assert goodmem.timeout == 30
        assert goodmem.default_top_k == 5

        mawsuah = config.get_tool_config("mawsuah")
        assert mawsuah.name == "mawsuah"
        assert mawsuah.timeout == 45

    def test_unknown_tool(self, temp_config_file):
        """Test error for unknown tool."""
        config = Config(temp_config_file)
        with pytest.raises(ValueError, match="Unknown tool"):
            config.get_tool_config("nonexistent")

    def test_get_llm_config(self, temp_config_file):
        """Test getting LLM configuration."""
        config = Config(temp_config_file)
        llm = config.get_llm_config()

        assert llm["model"] == "claude-opus-4-1"
        assert llm["api_key_env"] == "ANTHROPIC_KEY"
        assert llm["temperature"] == 0.3

    def test_get_output_config(self, temp_config_file):
        """Test getting output configuration."""
        config = Config(temp_config_file)
        output = config.get_output_config()

        assert "console" in output["formats"]
        assert "jsonl" in output["formats"]
        assert output["output_dir"] == "outputs"

    def test_get_display_config(self, temp_config_file):
        """Test getting display configuration."""
        config = Config(temp_config_file)
        display = config.get_display_config()

        assert display["max_text_length"] == 500
        assert display["highlight_differences"] is True

    @patch.dict(
        os.environ,
        {
            "ANTHROPIC_KEY": "test_key",
            "GOODMEM_KEY": "test_key",
            "VECTARA_KEY": "test_key",
        },
    )
    def test_validate_success(self, temp_config_file):
        """Test successful validation."""
        config = Config(temp_config_file)
        config.validate()  # Should not raise

    @patch.dict(os.environ, {"KEY": "test"})
    def test_validate_missing_tool(self):
        """Test validation with missing required tool."""
        config_data = {
            "tools": {"goodmem": {"name": "goodmem", "api_key_env": "KEY"}},
            "llm": {"api_key_env": "ANTHROPIC_KEY"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = Path(f.name)

        try:
            config = Config(temp_path)
            with pytest.raises(ValueError, match="Missing required tool.*mawsuah"):
                config.validate()
        finally:
            temp_path.unlink()

    @patch.dict(os.environ, {"GOODMEM_KEY": "test", "VECTARA_KEY": "test"}, clear=False)
    def test_validate_missing_llm_key(self, temp_config_file):
        """Test validation with missing LLM API key."""
        config = Config(temp_config_file)
        with pytest.raises(ValueError, match="Missing LLM API key environment"):
            config.validate()
