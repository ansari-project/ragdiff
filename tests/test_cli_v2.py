"""Tests for RAGDiff v2.0 CLI commands (Phase 5).

Tests cover:
- v2 run command
- v2 compare command
- Output formatting (table, json, markdown)
- Error handling
"""

import json
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import yaml
from typer.testing import CliRunner

from ragdiff.cli_v2 import app
from ragdiff.core.models_v2 import (
    Query,
    QueryResult,
    QuerySet,
    RetrievedChunk,
    Run,
    RunStatus,
    SystemConfig,
)
from ragdiff.core.storage import save_run
from ragdiff.providers import System, register_tool

runner = CliRunner()


# ============================================================================
# Test Fixtures
# ============================================================================


class MockCLISystem(System):
    """Mock system for CLI testing."""

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Return mock results."""
        return [RetrievedChunk(content=f"Result for: {query}", score=0.9, metadata={})]


@pytest.fixture
def test_domain_for_cli(tmp_path):
    """Create a test domain for CLI testing."""
    domain_name = "test-cli-domain"
    domain_dir = tmp_path / domain_name

    # Create domain structure
    domain_dir.mkdir()
    (domain_dir / "systems").mkdir()
    (domain_dir / "query-sets").mkdir()
    (domain_dir / "runs").mkdir()
    (domain_dir / "comparisons").mkdir()

    # Create domain.yaml
    domain_config = {
        "name": domain_name,
        "description": "Test domain for CLI",
        "evaluator": {
            "model": "gpt-3.5-turbo",
            "temperature": 0.0,
            "prompt_template": "Compare: {results}",
        },
    }
    with open(domain_dir / "domain.yaml", "w") as f:
        yaml.dump(domain_config, f)

    # Create system config
    system_config = {
        "name": "mock-cli-system",
        "tool": "mock-cli",
        "config": {"setting": "value"},
    }
    with open(domain_dir / "systems" / "mock-cli-system.yaml", "w") as f:
        yaml.dump(system_config, f)

    # Create query set
    with open(domain_dir / "query-sets" / "test-queries.txt", "w") as f:
        f.write("Query 1\n")
        f.write("Query 2\n")
        f.write("Query 3\n")

    # Register mock tool
    from ragdiff.providers.registry import TOOL_REGISTRY

    original_registry = TOOL_REGISTRY.copy()
    register_tool("mock-cli", MockCLISystem)

    yield tmp_path, domain_name

    # Cleanup - restore original registry
    TOOL_REGISTRY.clear()
    TOOL_REGISTRY.update(original_registry)


# ============================================================================
# CLI Run Command Tests
# ============================================================================


class TestCLIRunCommand:
    """Tests for v2 run command."""

    def test_run_command_help(self):
        """Test that run command help is displayed."""
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "Execute a query set against a system" in result.stdout
        assert "DOMAIN" in result.stdout
        assert "SYSTEM" in result.stdout
        assert "QUERY_SET" in result.stdout

    def test_run_command_success(self, test_domain_for_cli):
        """Test successful run command execution."""
        domains_dir, domain_name = test_domain_for_cli

        result = runner.invoke(
            app,
            [
                "run",
                domain_name,
                "mock-cli-system",
                "test-queries",
                "--domains-dir",
                str(domains_dir),
                "--quiet",  # Suppress progress output for testing
            ],
        )

        assert result.exit_code == 0
        assert "Run completed" in result.stdout
        assert "Run Summary" in result.stdout
        assert "Status" in result.stdout
        assert "completed" in result.stdout.lower()
        assert "Successes" in result.stdout
        assert "3" in result.stdout  # 3 queries

    def test_run_command_missing_domain(self, test_domain_for_cli):
        """Test run command with missing domain."""
        domains_dir, _ = test_domain_for_cli

        result = runner.invoke(
            app,
            [
                "run",
                "missing-domain",
                "mock-cli-system",
                "test-queries",
                "--domains-dir",
                str(domains_dir),
                "--quiet",
            ],
        )

        assert result.exit_code == 1
        assert "Error" in result.stdout

    def test_run_command_missing_system(self, test_domain_for_cli):
        """Test run command with missing system."""
        domains_dir, domain_name = test_domain_for_cli

        result = runner.invoke(
            app,
            [
                "run",
                domain_name,
                "missing-system",
                "test-queries",
                "--domains-dir",
                str(domains_dir),
                "--quiet",
            ],
        )

        assert result.exit_code == 1
        assert "Error" in result.stdout


# ============================================================================
# CLI Compare Command Tests
# ============================================================================


class TestCLICompareCommand:
    """Tests for v2 compare command."""

    def test_compare_command_help(self):
        """Test that compare command help is displayed."""
        result = runner.invoke(app, ["compare", "--help"])
        assert result.exit_code == 0
        assert "Compare multiple runs using LLM evaluation" in result.stdout
        assert "DOMAIN" in result.stdout
        assert "RUN_IDS" in result.stdout

    def test_compare_command_missing_litellm(self, test_domain_for_cli):
        """Test compare command when LiteLLM is not available."""
        # This test only runs if LiteLLM is not installed
        try:
            import litellm  # noqa: F401

            pytest.skip("LiteLLM is installed")
        except ImportError:
            domains_dir, domain_name = test_domain_for_cli

            result = runner.invoke(
                app,
                [
                    "compare",
                    domain_name,
                    "run1",
                    "run2",
                    "--domains-dir",
                    str(domains_dir),
                ],
            )

            assert result.exit_code == 1
            assert "LiteLLM is required" in result.stdout

    def test_compare_command_with_runs(self, test_domain_for_cli):
        """Test compare command with actual runs."""
        try:
            import litellm  # noqa: F401
        except ImportError:
            pytest.skip("LiteLLM not installed")

        if "OPENAI_API_KEY" not in os.environ:
            pytest.skip("OPENAI_API_KEY not set")

        domains_dir, domain_name = test_domain_for_cli

        # Create two runs
        query_set = QuerySet(
            name="test-queries",
            domain=domain_name,
            queries=[Query(text="Query 1"), Query(text="Query 2")],
        )

        run1 = Run(
            id=uuid4(),
            domain=domain_name,
            system="system-a",
            query_set="test-queries",
            status=RunStatus.COMPLETED,
            results=[
                QueryResult(
                    query="Query 1",
                    retrieved=[RetrievedChunk(content="Result A1", score=0.9)],
                    reference=None,
                    duration_ms=100.0,
                    error=None,
                ),
                QueryResult(
                    query="Query 2",
                    retrieved=[RetrievedChunk(content="Result A2", score=0.85)],
                    reference=None,
                    duration_ms=110.0,
                    error=None,
                ),
            ],
            system_config=SystemConfig(name="system-a", tool="mock", config={}),
            query_set_snapshot=query_set,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )

        run2 = Run(
            id=uuid4(),
            domain=domain_name,
            system="system-b",
            query_set="test-queries",
            status=RunStatus.COMPLETED,
            results=[
                QueryResult(
                    query="Query 1",
                    retrieved=[RetrievedChunk(content="Result B1", score=0.95)],
                    reference=None,
                    duration_ms=105.0,
                    error=None,
                ),
                QueryResult(
                    query="Query 2",
                    retrieved=[RetrievedChunk(content="Result B2", score=0.80)],
                    reference=None,
                    duration_ms=115.0,
                    error=None,
                ),
            ],
            system_config=SystemConfig(name="system-b", tool="mock", config={}),
            query_set_snapshot=query_set,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )

        save_run(run1, domains_dir=domains_dir)
        save_run(run2, domains_dir=domains_dir)

        # Run compare command
        result = runner.invoke(
            app,
            [
                "compare",
                domain_name,
                str(run1.id)[:8],  # Short prefix
                str(run2.id)[:8],
                "--domains-dir",
                str(domains_dir),
                "--model",
                "gpt-3.5-turbo",
            ],
        )

        assert result.exit_code == 0
        assert "Comparison" in result.stdout
        assert "Summary" in result.stdout


# ============================================================================
# Output Format Tests
# ============================================================================


class TestOutputFormats:
    """Tests for different output formats."""

    def test_json_output_format(self, test_domain_for_cli, tmp_path):
        """Test JSON output format."""
        try:
            import litellm  # noqa: F401
        except ImportError:
            pytest.skip("LiteLLM not installed")

        if "OPENAI_API_KEY" not in os.environ:
            pytest.skip("OPENAI_API_KEY not set")

        domains_dir, domain_name = test_domain_for_cli

        # Create runs (same as above)
        query_set = QuerySet(
            name="test-queries",
            domain=domain_name,
            queries=[Query(text="Query 1")],
        )

        run1 = Run(
            id=uuid4(),
            domain=domain_name,
            system="system-a",
            query_set="test-queries",
            status=RunStatus.COMPLETED,
            results=[
                QueryResult(
                    query="Query 1",
                    retrieved=[RetrievedChunk(content="Result A1", score=0.9)],
                    reference=None,
                    duration_ms=100.0,
                    error=None,
                ),
            ],
            system_config=SystemConfig(name="system-a", tool="mock", config={}),
            query_set_snapshot=query_set,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )

        run2 = Run(
            id=uuid4(),
            domain=domain_name,
            system="system-b",
            query_set="test-queries",
            status=RunStatus.COMPLETED,
            results=[
                QueryResult(
                    query="Query 1",
                    retrieved=[RetrievedChunk(content="Result B1", score=0.95)],
                    reference=None,
                    duration_ms=105.0,
                    error=None,
                ),
            ],
            system_config=SystemConfig(name="system-b", tool="mock", config={}),
            query_set_snapshot=query_set,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )

        save_run(run1, domains_dir=domains_dir)
        save_run(run2, domains_dir=domains_dir)

        # Test JSON output to file
        output_file = tmp_path / "comparison.json"
        result = runner.invoke(
            app,
            [
                "compare",
                domain_name,
                str(run1.id),
                str(run2.id),
                "--domains-dir",
                str(domains_dir),
                "--format",
                "json",
                "--output",
                str(output_file),
                "--model",
                "gpt-3.5-turbo",
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()

        # Verify JSON is valid
        with open(output_file) as f:
            data = json.load(f)
        assert "id" in data
        assert "domain" in data
        assert data["domain"] == domain_name

    def test_markdown_output_format(self, test_domain_for_cli, tmp_path):
        """Test Markdown output format."""
        try:
            import litellm  # noqa: F401
        except ImportError:
            pytest.skip("LiteLLM not installed")

        if "OPENAI_API_KEY" not in os.environ:
            pytest.skip("OPENAI_API_KEY not set")

        domains_dir, domain_name = test_domain_for_cli

        # Create runs (reuse from above)
        query_set = QuerySet(
            name="test-queries",
            domain=domain_name,
            queries=[Query(text="Query 1")],
        )

        run1 = Run(
            id=uuid4(),
            domain=domain_name,
            system="system-a",
            query_set="test-queries",
            status=RunStatus.COMPLETED,
            results=[
                QueryResult(
                    query="Query 1",
                    retrieved=[RetrievedChunk(content="Result A1", score=0.9)],
                    reference=None,
                    duration_ms=100.0,
                    error=None,
                ),
            ],
            system_config=SystemConfig(name="system-a", tool="mock", config={}),
            query_set_snapshot=query_set,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )

        run2 = Run(
            id=uuid4(),
            domain=domain_name,
            system="system-b",
            query_set="test-queries",
            status=RunStatus.COMPLETED,
            results=[
                QueryResult(
                    query="Query 1",
                    retrieved=[RetrievedChunk(content="Result B1", score=0.95)],
                    reference=None,
                    duration_ms=105.0,
                    error=None,
                ),
            ],
            system_config=SystemConfig(name="system-b", tool="mock", config={}),
            query_set_snapshot=query_set,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )

        save_run(run1, domains_dir=domains_dir)
        save_run(run2, domains_dir=domains_dir)

        # Test Markdown output to file
        output_file = tmp_path / "comparison.md"
        result = runner.invoke(
            app,
            [
                "compare",
                domain_name,
                str(run1.id),
                str(run2.id),
                "--domains-dir",
                str(domains_dir),
                "--format",
                "markdown",
                "--output",
                str(output_file),
                "--model",
                "gpt-3.5-turbo",
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()

        # Verify Markdown contains expected sections
        with open(output_file) as f:
            content = f.read()
        assert "# Comparison" in content
        assert "## Summary" in content
        assert "## Evaluations" in content
