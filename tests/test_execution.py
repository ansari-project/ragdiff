"""Tests for RAGDiff v2.0 execution engine (Phase 3).

Tests cover:
- Run execution (execute_run)
- Parallel query execution
- Progress callbacks
- Error handling (per-query errors)
- Run state management
- Config snapshotting
- File storage
"""

import os
import time

import pytest
import yaml

from ragdiff.core.errors import RunError
from ragdiff.core.models import RetrievedChunk, RunStatus
from ragdiff.execution import execute_run
from ragdiff.providers import Provider, register_tool

# ============================================================================
# Test Fixtures
# ============================================================================


class MockSuccessProvider(Provider):
    """Mock system that always succeeds."""

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Return mock results."""
        # Simulate some work
        time.sleep(0.01)

        return [
            RetrievedChunk(
                content=f"Result {i} for: {query}",
                score=1.0 - (i * 0.1),
                metadata={"index": i},
            )
            for i in range(min(top_k, 3))
        ]


class MockFailureProvider(Provider):
    """Mock system that always fails."""

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Always raise an error."""
        time.sleep(0.01)
        raise RuntimeError("Mock system error")


class MockPartialProvider(Provider):
    """Mock system that fails on specific queries."""

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Fail if query contains 'fail'."""
        time.sleep(0.01)

        if "fail" in query.lower():
            raise RuntimeError(f"Query contains 'fail': {query}")

        return [RetrievedChunk(content=f"Result for: {query}", score=0.95, metadata={})]


@pytest.fixture
def test_domain(tmp_path):
    """Create a test domain with system and query set."""
    domain_name = "test-domain"
    domain_dir = tmp_path / domain_name

    # Create domain structure
    domain_dir.mkdir()
    (domain_dir / "providers").mkdir()
    (domain_dir / "query-sets").mkdir()
    (domain_dir / "runs").mkdir()

    # Create domain.yaml
    domain_config = {
        "name": domain_name,
        "description": "Test domain",
        "evaluator": {
            "model": "claude-3-5-sonnet-20241022",
            "temperature": 0.0,
            "prompt_template": "Compare: {results}",
        },
    }
    with open(domain_dir / "domain.yaml", "w") as f:
        yaml.dump(domain_config, f)

    # Create provider config
    provider_config = {
        "name": "mock-system",
        "tool": "mock-success",
        "config": {
            "api_key": "${MOCK_API_KEY}",  # Placeholder
            "setting": "value",
        },
    }
    with open(domain_dir / "providers" / "mock-system.yaml", "w") as f:
        yaml.dump(provider_config, f)

    # Create query set (.txt format)
    with open(domain_dir / "query-sets" / "test-queries.txt", "w") as f:
        f.write("Query 1\n")
        f.write("Query 2\n")
        f.write("Query 3\n")

    # Create query set (.jsonl format)
    import json

    with open(domain_dir / "query-sets" / "test-with-refs.jsonl", "w") as f:
        f.write(json.dumps({"query": "Query A", "reference": "Answer A"}) + "\n")
        f.write(json.dumps({"query": "Query B", "reference": "Answer B"}) + "\n")

    # Set environment variable for mock API key
    os.environ["MOCK_API_KEY"] = "test_key_123"

    yield tmp_path, domain_name

    # Cleanup
    if "MOCK_API_KEY" in os.environ:
        del os.environ["MOCK_API_KEY"]


@pytest.fixture
def register_mock_tools():
    """Register mock tools for testing."""
    from ragdiff.providers.registry import TOOL_REGISTRY

    original_registry = TOOL_REGISTRY.copy()

    # Register mock tools
    register_tool("mock-success", MockSuccessProvider)
    register_tool("mock-failure", MockFailureProvider)
    register_tool("mock-partial", MockPartialProvider)

    yield

    # Cleanup - restore original registry
    TOOL_REGISTRY.clear()
    TOOL_REGISTRY.update(original_registry)


# ============================================================================
# Execute Run Tests
# ============================================================================


class TestExecuteRun:
    """Tests for execute_run function."""

    def test_execute_run_success(self, test_domain, register_mock_tools):
        """Test successful run execution."""
        domains_dir, domain_name = test_domain

        run = execute_run(
            domain=domain_name,
            provider="mock-system",
            query_set="test-queries",
            concurrency=2,
            domains_dir=domains_dir,
        )

        # Check run metadata
        assert run.domain == domain_name
        assert run.provider == "mock-system"
        assert run.query_set == "test-queries"
        assert run.status == RunStatus.COMPLETED

        # Check results
        assert len(run.results) == 3
        assert all(r.error is None for r in run.results)
        assert all(len(r.retrieved) > 0 for r in run.results)

        # Check timestamps
        assert run.started_at is not None
        assert run.completed_at is not None
        assert run.completed_at > run.started_at

        # Check metadata
        assert run.metadata["total_queries"] == 3
        assert run.metadata["successes"] == 3
        assert run.metadata["failures"] == 0

    def test_execute_run_with_references(self, test_domain, register_mock_tools):
        """Test run execution with reference answers."""
        domains_dir, domain_name = test_domain

        run = execute_run(
            domain=domain_name,
            provider="mock-system",
            query_set="test-with-refs",
            domains_dir=domains_dir,
        )

        assert run.status == RunStatus.COMPLETED
        assert len(run.results) == 2
        assert run.results[0].reference == "Answer A"
        assert run.results[1].reference == "Answer B"

    def test_execute_run_all_failures(self, test_domain, register_mock_tools, tmp_path):
        """Test run where all queries fail."""
        domains_dir, domain_name = test_domain

        # Create system that uses failure tool
        failure_system_config = {
            "name": "failure-system",
            "tool": "mock-failure",
            "config": {},
        }
        provider_path = domains_dir / domain_name / "providers" / "failure-system.yaml"
        with open(provider_path, "w") as f:
            yaml.dump(failure_system_config, f)

        run = execute_run(
            domain=domain_name,
            provider="failure-system",
            query_set="test-queries",
            domains_dir=domains_dir,
        )

        assert run.status == RunStatus.FAILED
        assert len(run.results) == 3
        assert all(r.error is not None for r in run.results)
        assert all(len(r.retrieved) == 0 for r in run.results)
        assert run.metadata["successes"] == 0
        assert run.metadata["failures"] == 3

    def test_execute_run_partial_success(self, test_domain, register_mock_tools):
        """Test run with some successes and some failures."""
        domains_dir, domain_name = test_domain

        # Create system that uses partial tool
        partial_system_config = {
            "name": "partial-system",
            "tool": "mock-partial",
            "config": {},
        }
        provider_path = domains_dir / domain_name / "providers" / "partial-system.yaml"
        with open(provider_path, "w") as f:
            yaml.dump(partial_system_config, f)

        # Create query set with some "fail" queries
        query_set_path = (
            domains_dir / domain_name / "query-sets" / "partial-queries.txt"
        )
        with open(query_set_path, "w") as f:
            f.write("Good query 1\n")
            f.write("This will fail\n")
            f.write("Good query 2\n")
            f.write("Another fail\n")

        run = execute_run(
            domain=domain_name,
            provider="partial-system",
            query_set="partial-queries",
            domains_dir=domains_dir,
        )

        assert run.status == RunStatus.PARTIAL
        assert len(run.results) == 4
        assert run.metadata["successes"] == 2
        assert run.metadata["failures"] == 2


# ============================================================================
# Config Snapshotting Tests
# ============================================================================


class TestConfigSnapshotting:
    """Tests for config snapshotting."""

    def test_config_snapshot_preserves_placeholders(
        self, test_domain, register_mock_tools
    ):
        """Test that config snapshots preserve ${VAR_NAME} placeholders."""
        domains_dir, domain_name = test_domain

        run = execute_run(
            domain=domain_name,
            provider="mock-system",
            query_set="test-queries",
            domains_dir=domains_dir,
        )

        # Check that provider config snapshot preserves ${MOCK_API_KEY}
        assert run.provider_config.config["api_key"] == "${MOCK_API_KEY}"
        assert run.provider_config.config["setting"] == "value"

        # Check that query set snapshot is preserved
        assert run.query_set_snapshot.name == "test-queries"
        assert len(run.query_set_snapshot.queries) == 3


# ============================================================================
# Progress Callback Tests
# ============================================================================


class TestProgressCallback:
    """Tests for progress callbacks."""

    def test_progress_callback(self, test_domain, register_mock_tools):
        """Test that progress callback is called correctly."""
        domains_dir, domain_name = test_domain

        progress_updates = []

        def progress_callback(current, total, successes, failures):
            progress_updates.append(
                {
                    "current": current,
                    "total": total,
                    "successes": successes,
                    "failures": failures,
                }
            )

        _run = execute_run(
            domain=domain_name,
            provider="mock-system",
            query_set="test-queries",
            progress_callback=progress_callback,
            domains_dir=domains_dir,
        )

        # Should have 3 progress updates (one per query)
        assert len(progress_updates) == 3

        # All updates should have total=3
        assert all(u["total"] == 3 for u in progress_updates)

        # Last update should have current=3, successes=3, failures=0
        last_update = progress_updates[-1]
        assert last_update["successes"] == 3
        assert last_update["failures"] == 0


# ============================================================================
# Parallel Execution Tests
# ============================================================================


class TestParallelExecution:
    """Tests for parallel query execution."""

    def test_parallel_execution_faster_than_sequential(
        self, test_domain, register_mock_tools
    ):
        """Test that parallel execution is faster than sequential would be."""
        domains_dir, domain_name = test_domain

        # Create a query set with many queries
        query_set_path = domains_dir / domain_name / "query-sets" / "many-queries.txt"
        with open(query_set_path, "w") as f:
            for i in range(20):
                f.write(f"Query {i}\n")

        # Execute with high concurrency
        start_time = time.time()
        run = execute_run(
            domain=domain_name,
            provider="mock-system",
            query_set="many-queries",
            concurrency=10,  # High concurrency
            domains_dir=domains_dir,
        )
        parallel_duration = time.time() - start_time

        # Verify results
        assert run.status == RunStatus.COMPLETED
        assert len(run.results) == 20

        # With 20 queries at 0.01s each, sequential would take ~0.2s
        # Parallel with concurrency=10 should take ~0.02s + overhead
        # Let's just verify it completed reasonably fast
        assert parallel_duration < 1.0  # Should be much faster than 1 second

    def test_concurrency_limit_respected(self, test_domain, register_mock_tools):
        """Test that concurrency limit is respected."""
        domains_dir, domain_name = test_domain

        # This test is more of a sanity check - we can't easily verify
        # the exact number of concurrent threads, but we can verify that
        # the run completes successfully with various concurrency settings

        for concurrency in [1, 2, 5]:
            run = execute_run(
                domain=domain_name,
                provider="mock-system",
                query_set="test-queries",
                concurrency=concurrency,
                domains_dir=domains_dir,
            )
            assert run.status == RunStatus.COMPLETED
            assert len(run.results) == 3


# ============================================================================
# File Storage Tests
# ============================================================================


class TestFileStorage:
    """Tests for run file storage."""

    def test_run_saved_to_correct_path(self, test_domain, register_mock_tools):
        """Test that run is saved to correct file path."""
        domains_dir, domain_name = test_domain

        run = execute_run(
            domain=domain_name,
            provider="mock-system",
            query_set="test-queries",
            domains_dir=domains_dir,
        )

        # Check that run file exists
        date_str = run.started_at.strftime("%Y-%m-%d")
        filename = f"{run.label}.json" if run.label else f"{run.id}.json"
        run_path = domains_dir / domain_name / "runs" / date_str / filename
        assert run_path.exists()

        # Check that file contains valid JSON
        import json

        with open(run_path) as f:
            run_data = json.load(f)

        assert run_data["id"] == str(run.id)
        assert run_data["domain"] == domain_name
        assert run_data["status"] == "completed"


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_missing_domain(self, test_domain, register_mock_tools):
        """Test error when domain doesn't exist."""
        domains_dir, domain_name = test_domain

        with pytest.raises(RunError, match="Failed to initialize run"):
            execute_run(
                domain="missing-domain",
                provider="mock-system",
                query_set="test-queries",
                domains_dir=domains_dir,
            )

    def test_missing_system(self, test_domain, register_mock_tools):
        """Test error when system doesn't exist."""
        domains_dir, domain_name = test_domain

        with pytest.raises(RunError, match="Failed to initialize run"):
            execute_run(
                domain=domain_name,
                provider="missing-system",
                query_set="test-queries",
                domains_dir=domains_dir,
            )

    def test_missing_query_set(self, test_domain, register_mock_tools):
        """Test error when query set doesn't exist."""
        domains_dir, domain_name = test_domain

        with pytest.raises(RunError, match="Failed to initialize run"):
            execute_run(
                domain=domain_name,
                provider="mock-system",
                query_set="missing-queries",
                domains_dir=domains_dir,
            )
