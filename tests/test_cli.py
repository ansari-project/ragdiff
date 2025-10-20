"""Tests for CLI interface."""

from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.core.models import ComparisonResult, RagResult


class TestCLI:
    """Test CLI functionality."""

    @pytest.fixture
    def runner(self):
        """Create CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = Mock()
        config.tools = {
            "tool1": Mock(api_key_env="TOOL1_KEY"),
            "tool2": Mock(api_key_env="TOOL2_KEY"),
        }
        config.llm = Mock(model="claude", api_key_env="CLAUDE_KEY")
        config.validate.return_value = None
        return config

    @pytest.fixture
    def mock_comparison_result(self):
        """Create mock comparison result."""
        return ComparisonResult(
            query="test query",
            tool_results={
                "tool1": [RagResult(id="1", text="Result 1", score=0.9)],
                "tool2": [RagResult(id="2", text="Result 2", score=0.8)],
            },
            errors={},
        )

    def test_list_tools_command(self, runner):
        """Test list-tools command."""
        with patch("src.cli.get_available_adapters") as mock_adapters:
            mock_adapters.return_value = ["mawsuah", "goodmem"]

            with patch("src.cli.Config") as mock_config_class:
                mock_config = Mock()
                mock_config.tools = {
                    "tool1": Mock(api_key_env="KEY1"),
                    "tool2": Mock(api_key_env="KEY2"),
                }
                mock_config.validate = Mock()
                mock_config_class.return_value = mock_config

                with patch("src.cli.Path.exists") as mock_exists:
                    mock_exists.return_value = True

                    result = runner.invoke(app, ["list-tools"])
                    assert result.exit_code == 0
                    assert "mawsuah" in result.stdout
                    assert "goodmem" in result.stdout
                    assert "tool1" in result.stdout

    def test_validate_config_success(self, runner, mock_config):
        """Test validate-config with valid configuration."""
        with patch("src.cli.Path.exists") as mock_exists:
            mock_exists.return_value = True

            with patch("src.cli.Config") as mock_config_class:
                mock_config_class.return_value = mock_config

                result = runner.invoke(app, ["validate-config"])
                assert result.exit_code == 0
                assert "Configuration is valid" in result.stdout

    def test_validate_config_missing_file(self, runner):
        """Test validate-config with missing file."""
        with patch("src.cli.Path.exists") as mock_exists:
            mock_exists.return_value = False

            result = runner.invoke(app, ["validate-config"])
            assert result.exit_code == 1
            assert "not found" in result.stdout

    @patch("src.cli.ComparisonEngine")
    @patch("src.cli.create_adapter")
    @patch("src.cli.Config")
    @patch("src.cli.Path.exists")
    def test_compare_basic(
        self,
        mock_exists,
        mock_config_class,
        mock_create_adapter,
        mock_engine_class,
        runner,
        mock_config,
        mock_comparison_result,
    ):
        """Test basic compare command."""
        # Setup mocks
        mock_exists.return_value = True
        mock_config_class.return_value = mock_config
        mock_create_adapter.return_value = Mock()

        mock_engine = Mock()
        mock_engine.run_comparison.return_value = mock_comparison_result
        mock_engine.get_summary_stats.return_value = {
            "tools_compared": ["tool1", "tool2"],
            "result_counts": {"tool1": 1, "tool2": 1},
            "average_scores": {"tool1": 0.9, "tool2": 0.8},
            "latencies_ms": {},
        }
        mock_engine_class.return_value = mock_engine

        # Run command
        result = runner.invoke(app, ["compare", "test query", "--top-k", "3"])

        assert result.exit_code == 0
        mock_engine.run_comparison.assert_called_once_with(
            "test query", top_k=3, parallel=True
        )

    @patch("src.cli.ComparisonEngine")
    @patch("src.cli.create_adapter")
    @patch("src.cli.Config")
    @patch("src.cli.Path")
    def test_compare_json_output(
        self,
        mock_path_class,
        mock_config_class,
        mock_create_adapter,
        mock_engine_class,
        runner,
        mock_config,
        mock_comparison_result,
    ):
        """Test compare with JSON output."""
        # Setup mocks
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_path_class.return_value = mock_path
        mock_path_class.exists = Mock(return_value=True)

        mock_config_class.return_value = mock_config
        mock_create_adapter.return_value = Mock()

        mock_engine = Mock()
        mock_engine.run_comparison.return_value = mock_comparison_result
        mock_engine.get_summary_stats.return_value = {
            "tools_compared": ["tool1", "tool2"],
            "result_counts": {"tool1": 1, "tool2": 1},
            "average_scores": {"tool1": 0.9, "tool2": 0.8},
            "latencies_ms": {},
        }
        mock_engine_class.return_value = mock_engine

        # Run command with JSON format
        result = runner.invoke(app, ["compare", "test query", "--format", "json"])

        assert result.exit_code == 0
        # Output should contain JSON - the CLI shows status messages before JSON
        # Just check that the query appears in the output
        assert "test query" in result.stdout
        assert "{" in result.stdout  # JSON output present

    @patch("src.cli.ComparisonEngine")
    @patch("src.cli.create_adapter")
    @patch("src.cli.Config")
    @patch("src.cli.Path")
    def test_compare_with_output_file(
        self,
        mock_path_class,
        mock_config_class,
        mock_create_adapter,
        mock_engine_class,
        runner,
        mock_config,
        mock_comparison_result,
        tmp_path,
    ):
        """Test compare with output file."""
        # Setup mocks
        mock_path_class.exists = Mock(return_value=True)
        mock_config_class.return_value = mock_config
        mock_create_adapter.return_value = Mock()

        mock_engine = Mock()
        mock_engine.run_comparison.return_value = mock_comparison_result
        mock_engine.get_summary_stats.return_value = {
            "tools_compared": ["tool1", "tool2"],
            "result_counts": {},
            "average_scores": {},
            "latencies_ms": {},
        }
        mock_engine_class.return_value = mock_engine

        output_file = tmp_path / "output.txt"

        # Mock Path write
        mock_write = Mock()
        mock_path_class.return_value.write_text = mock_write

        # Run command
        result = runner.invoke(
            app, ["compare", "test query", "--output", str(output_file)]
        )

        assert result.exit_code == 0
        mock_write.assert_called_once()

    @patch("src.cli.ComparisonEngine")
    @patch("src.cli.create_adapter")
    @patch("src.cli.Config")
    @patch("src.cli.Path.exists")
    def test_compare_specific_tools(
        self,
        mock_exists,
        mock_config_class,
        mock_create_adapter,
        mock_engine_class,
        runner,
        mock_config,
    ):
        """Test compare with specific tools."""
        mock_exists.return_value = True
        mock_config_class.return_value = mock_config
        mock_create_adapter.return_value = Mock()

        mock_engine = Mock()
        # Use the actual ComparisonResult for proper behavior
        from src.core.models import ComparisonResult

        mock_engine.run_comparison.return_value = ComparisonResult(
            query="test", tool_results={"tool1": []}, errors={}
        )
        mock_engine.get_summary_stats.return_value = {
            "tools_compared": ["tool1"],
            "result_counts": {},
            "average_scores": {},
            "latencies_ms": {},
        }
        mock_engine_class.return_value = mock_engine

        # Run with specific tool
        result = runner.invoke(app, ["compare", "test query", "--tool", "tool1"])

        assert result.exit_code == 0
        # Should only create adapter for tool1
        assert mock_create_adapter.call_count == 1
        mock_create_adapter.assert_called_with("tool1", mock_config.tools["tool1"])

    def test_compare_missing_config(self, runner):
        """Test compare with missing configuration."""
        with patch("src.cli.Path.exists") as mock_exists:
            mock_exists.return_value = False

            result = runner.invoke(app, ["compare", "test query"])
            assert result.exit_code == 1
            assert "not found" in result.stdout

    @patch("src.cli.compare")
    def test_quick_test_command(self, mock_compare, runner):
        """Test quick-test command."""
        mock_compare.return_value = None

        result = runner.invoke(app, ["quick-test"])

        # Should call compare with test query
        mock_compare.assert_called_once()
        call_kwargs = mock_compare.call_args.kwargs
        assert "What is the ruling on prayer times?" in call_kwargs["query"]
        assert call_kwargs["top_k"] == 2

    def test_cli_help(self, runner):
        """Test CLI help output."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Compare RAG tool results" in result.stdout
        assert "compare" in result.stdout
        assert "list-tools" in result.stdout
