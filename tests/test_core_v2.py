"""Tests for RAGDiff v2.0 core components.

Tests cover:
- Data models (models_v2.py)
- Environment variable substitution (env_vars.py)
- File loaders (loaders.py)
- Path utilities (paths.py)
- Storage (storage.py)
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import yaml

from ragdiff.core.env_vars import (
    check_required_vars,
    substitute_env_vars,
    validate_env_vars,
)
from ragdiff.core.errors import ConfigError, RunError, ValidationError
from ragdiff.core.loaders import (
    load_domain,
    load_query_set,
    load_system,
    load_system_for_snapshot,
)
from ragdiff.core.models_v2 import (
    Comparison,
    Domain,
    EvaluationResult,
    EvaluatorConfig,
    Query,
    QueryResult,
    QuerySet,
    RetrievedChunk,
    Run,
    RunStatus,
    SystemConfig,
)
from ragdiff.core.paths import (
    ensure_domain_structure,
    find_run_by_prefix,
    get_comparison_path,
    get_run_path,
    list_query_sets,
    list_systems,
)
from ragdiff.core.storage import (
    list_comparisons,
    list_runs,
    load_comparison,
    load_run,
    save_comparison,
    save_run,
)


# ============================================================================
# Model Tests
# ============================================================================


class TestModels:
    """Tests for Pydantic data models."""

    def test_retrieved_chunk(self):
        """Test RetrievedChunk model."""
        chunk = RetrievedChunk(
            content="This is a test chunk",
            score=0.95,
            metadata={"source_id": "doc1", "chunk_id": 42},
        )

        assert chunk.content == "This is a test chunk"
        assert chunk.score == 0.95
        assert chunk.metadata["source_id"] == "doc1"

        # Score and metadata are optional
        minimal = RetrievedChunk(content="Minimal chunk")
        assert minimal.score is None
        assert minimal.metadata == {}

    def test_query_validation(self):
        """Test Query model validation."""
        # Valid query
        query = Query(text="What is Islamic law?", reference="Some answer")
        assert query.text == "What is Islamic law?"
        assert query.reference == "Some answer"

        # Text is stripped
        query = Query(text="  Whitespace  ")
        assert query.text == "Whitespace"

        # Empty text raises error
        with pytest.raises(ValueError, match="Query text cannot be empty"):
            Query(text="")

        with pytest.raises(ValueError, match="Query text cannot be empty"):
            Query(text="   ")

    def test_run_status_enum(self):
        """Test RunStatus enum."""
        assert RunStatus.PENDING == "pending"
        assert RunStatus.RUNNING == "running"
        assert RunStatus.COMPLETED == "completed"
        assert RunStatus.FAILED == "failed"
        assert RunStatus.PARTIAL == "partial"

    def test_domain_name_validation(self):
        """Test Domain name validation."""
        # Valid names
        Domain(
            name="tafsir",
            evaluator=EvaluatorConfig(
                model="claude-3-5-sonnet-20241022",
                temperature=0.0,
                prompt_template="Compare these results",
            ),
        )
        Domain(
            name="legal-docs",
            evaluator=EvaluatorConfig(
                model="claude-3-5-sonnet-20241022",
                temperature=0.0,
                prompt_template="Compare these results",
            ),
        )
        Domain(
            name="test_domain_123",
            evaluator=EvaluatorConfig(
                model="claude-3-5-sonnet-20241022",
                temperature=0.0,
                prompt_template="Compare these results",
            ),
        )

        # Invalid names
        with pytest.raises(ValueError, match="Domain name cannot be empty"):
            Domain(
                name="",
                evaluator=EvaluatorConfig(
                    model="claude-3-5-sonnet-20241022",
                    temperature=0.0,
                    prompt_template="Compare",
                ),
            )

        with pytest.raises(ValueError, match="must be alphanumeric"):
            Domain(
                name="my/domain",
                evaluator=EvaluatorConfig(
                    model="claude-3-5-sonnet-20241022",
                    temperature=0.0,
                    prompt_template="Compare",
                ),
            )

    def test_system_config_name_validation(self):
        """Test SystemConfig name validation."""
        # Valid names
        SystemConfig(name="vectara-default", tool="vectara", config={})
        SystemConfig(name="agentset_v2", tool="agentset", config={})

        # Invalid names
        with pytest.raises(ValueError, match="System name cannot be empty"):
            SystemConfig(name="", tool="vectara", config={})

        with pytest.raises(ValueError, match="must be alphanumeric"):
            SystemConfig(name="my system", tool="vectara", config={})

    def test_query_set_max_queries(self):
        """Test QuerySet enforces 1000 query limit."""
        # Valid query set
        queries = [Query(text=f"Query {i}") for i in range(100)]
        query_set = QuerySet(name="test", domain="tafsir", queries=queries)
        assert len(query_set.queries) == 100

        # Exactly 1000 is OK
        queries = [Query(text=f"Query {i}") for i in range(1000)]
        query_set = QuerySet(name="test", domain="tafsir", queries=queries)
        assert len(query_set.queries) == 1000

        # 1001 raises error
        queries = [Query(text=f"Query {i}") for i in range(1001)]
        with pytest.raises(ValueError, match="cannot exceed 1000 queries"):
            QuerySet(name="test", domain="tafsir", queries=queries)

        # Empty query set raises error
        with pytest.raises(ValueError, match="Query set cannot be empty"):
            QuerySet(name="test", domain="tafsir", queries=[])

    def test_run_timestamp_validation(self):
        """Test Run timestamp validation (must be UTC)."""
        run_id = uuid4()
        system_config = SystemConfig(name="test", tool="vectara", config={})
        query_set = QuerySet(
            name="test", domain="tafsir", queries=[Query(text="Test")]
        )

        # Valid: timezone-aware (UTC)
        run = Run(
            id=run_id,
            domain="tafsir",
            system="test",
            query_set="test",
            status=RunStatus.COMPLETED,
            results=[],
            system_config=system_config,
            query_set_snapshot=query_set,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        assert run.started_at.tzinfo is not None

        # Invalid: naive datetime
        with pytest.raises(ValueError, match="must be timezone-aware"):
            Run(
                id=run_id,
                domain="tafsir",
                system="test",
                query_set="test",
                status=RunStatus.COMPLETED,
                results=[],
                system_config=system_config,
                query_set_snapshot=query_set,
                started_at=datetime.now(),  # Naive!
                completed_at=None,
            )

    def test_run_serialization(self):
        """Test Run JSON serialization/deserialization."""
        run = Run(
            id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            domain="tafsir",
            system="vectara-default",
            query_set="test-queries",
            status=RunStatus.COMPLETED,
            results=[
                QueryResult(
                    query="Test query",
                    retrieved=[
                        RetrievedChunk(
                            content="Test content", score=0.95, metadata={"foo": "bar"}
                        )
                    ],
                    reference=None,
                    duration_ms=123.45,
                    error=None,
                )
            ],
            system_config=SystemConfig(
                name="vectara-default",
                tool="vectara",
                config={"api_key": "${VECTARA_API_KEY}", "top_k": 5},
            ),
            query_set_snapshot=QuerySet(
                name="test-queries", domain="tafsir", queries=[Query(text="Test query")]
            ),
            started_at=datetime(2025, 10, 25, 12, 0, 0, tzinfo=timezone.utc),
            completed_at=datetime(2025, 10, 25, 12, 5, 0, tzinfo=timezone.utc),
        )

        # Serialize to JSON
        json_str = run.model_dump_json()
        data = json.loads(json_str)

        # Deserialize back
        run2 = Run(**data)

        assert run2.id == run.id
        assert run2.domain == run.domain
        assert run2.system == run.system
        assert run2.status == run.status
        assert len(run2.results) == 1
        assert run2.results[0].query == "Test query"


# ============================================================================
# Environment Variable Tests
# ============================================================================


class TestEnvVars:
    """Tests for environment variable substitution."""

    def test_validate_env_vars(self):
        """Test extracting environment variable names."""
        config = {
            "api_key": "${API_KEY}",
            "endpoints": ["${BASE_URL}/v1", "${BASE_URL}/v2"],
            "nested": {"secret": "${SECRET}"},
        }

        required = validate_env_vars(config)
        assert required == {"API_KEY", "BASE_URL", "SECRET"}

    def test_substitute_env_vars_resolve(self):
        """Test environment variable substitution with resolution."""
        os.environ["TEST_API_KEY"] = "secret123"
        os.environ["TEST_URL"] = "https://example.com"

        try:
            config = {
                "api_key": "${TEST_API_KEY}",
                "base_url": "${TEST_URL}",
                "count": 42,
            }

            resolved = substitute_env_vars(config, resolve_secrets=True)

            assert resolved["api_key"] == "secret123"
            assert resolved["base_url"] == "https://example.com"
            assert resolved["count"] == 42

        finally:
            del os.environ["TEST_API_KEY"]
            del os.environ["TEST_URL"]

    def test_substitute_env_vars_preserve(self):
        """Test environment variable substitution without resolution (snapshots)."""
        config = {
            "api_key": "${API_KEY}",
            "base_url": "${BASE_URL}",
            "count": 42,
        }

        # Do NOT resolve secrets (for snapshots)
        preserved = substitute_env_vars(config, resolve_secrets=False)

        assert preserved["api_key"] == "${API_KEY}"  # Preserved!
        assert preserved["base_url"] == "${BASE_URL}"  # Preserved!
        assert preserved["count"] == 42

    def test_substitute_env_vars_missing(self):
        """Test error when environment variable is missing."""
        config = {"api_key": "${MISSING_KEY}"}

        with pytest.raises(ConfigError, match="Environment variable 'MISSING_KEY' not set"):
            substitute_env_vars(config, resolve_secrets=True)

    def test_check_required_vars(self):
        """Test checking for missing environment variables."""
        os.environ["TEST_KEY"] = "value"

        try:
            # All variables present
            config = {"key": "${TEST_KEY}"}
            check_required_vars(config)  # Should not raise

            # Missing variable
            config = {"key": "${MISSING_KEY}"}
            with pytest.raises(ConfigError, match="Missing required environment variables"):
                check_required_vars(config)

        finally:
            del os.environ["TEST_KEY"]


# ============================================================================
# File Loader Tests
# ============================================================================


class TestLoaders:
    """Tests for file loaders."""

    def test_load_domain(self, tmp_path):
        """Test loading domain configuration."""
        # Create domain directory
        domain_dir = tmp_path / "domains" / "test-domain"
        domain_dir.mkdir(parents=True)

        # Write domain.yaml
        domain_config = {
            "name": "test-domain",
            "description": "Test domain",
            "variables": {"var1": "value1"},
            "secrets": {"api_key": "API_KEY"},
            "evaluator": {
                "model": "claude-3-5-sonnet-20241022",
                "temperature": 0.0,
                "prompt_template": "Compare these results: {results}",
            },
        }

        with open(domain_dir / "domain.yaml", "w") as f:
            yaml.dump(domain_config, f)

        # Load domain
        domain = load_domain("test-domain", domains_dir=tmp_path / "domains")

        assert domain.name == "test-domain"
        assert domain.description == "Test domain"
        assert domain.evaluator.model == "claude-3-5-sonnet-20241022"

    def test_load_domain_not_found(self, tmp_path):
        """Test loading non-existent domain."""
        with pytest.raises(ConfigError, match="Domain 'missing' not found"):
            load_domain("missing", domains_dir=tmp_path / "domains")

    def test_load_system(self, tmp_path):
        """Test loading system configuration."""
        # Set environment variable for testing
        os.environ["TEST_VECTARA_KEY"] = "test_key_123"

        try:
            # Create domain and systems directory
            systems_dir = tmp_path / "domains" / "test-domain" / "systems"
            systems_dir.mkdir(parents=True)

            # Write system.yaml
            system_config = {
                "name": "vectara-test",
                "tool": "vectara",
                "config": {
                    "api_key": "${TEST_VECTARA_KEY}",
                    "corpus_id": 123,
                    "top_k": 5,
                },
            }

            with open(systems_dir / "vectara-test.yaml", "w") as f:
                yaml.dump(system_config, f)

            # Load system (secrets resolved)
            system = load_system(
                "test-domain", "vectara-test", domains_dir=tmp_path / "domains"
            )

            assert system.name == "vectara-test"
            assert system.tool == "vectara"
            assert system.config["api_key"] == "test_key_123"  # Resolved!
            assert system.config["corpus_id"] == 123

        finally:
            del os.environ["TEST_VECTARA_KEY"]

    def test_load_system_for_snapshot(self, tmp_path):
        """Test loading system configuration without resolving secrets."""
        # Create domain and systems directory
        systems_dir = tmp_path / "domains" / "test-domain" / "systems"
        systems_dir.mkdir(parents=True)

        # Write system.yaml
        system_config = {
            "name": "vectara-test",
            "tool": "vectara",
            "config": {
                "api_key": "${VECTARA_API_KEY}",
                "corpus_id": 123,
                "top_k": 5,
            },
        }

        with open(systems_dir / "vectara-test.yaml", "w") as f:
            yaml.dump(system_config, f)

        # Load system for snapshot (secrets NOT resolved)
        system = load_system_for_snapshot(
            "test-domain", "vectara-test", domains_dir=tmp_path / "domains"
        )

        assert system.name == "vectara-test"
        assert system.config["api_key"] == "${VECTARA_API_KEY}"  # Preserved!

    def test_load_query_set_txt(self, tmp_path):
        """Test loading query set from .txt file."""
        # Create query-sets directory
        query_sets_dir = tmp_path / "domains" / "test-domain" / "query-sets"
        query_sets_dir.mkdir(parents=True)

        # Write queries.txt
        with open(query_sets_dir / "test-queries.txt", "w") as f:
            f.write("# This is a comment\n")
            f.write("What is Islamic law?\n")
            f.write("\n")  # Empty line
            f.write("What is inheritance law?\n")

        # Load query set
        query_set = load_query_set(
            "test-domain", "test-queries", domains_dir=tmp_path / "domains"
        )

        assert query_set.name == "test-queries"
        assert query_set.domain == "test-domain"
        assert len(query_set.queries) == 2
        assert query_set.queries[0].text == "What is Islamic law?"
        assert query_set.queries[1].text == "What is inheritance law?"

    def test_load_query_set_jsonl(self, tmp_path):
        """Test loading query set from .jsonl file."""
        # Create query-sets directory
        query_sets_dir = tmp_path / "domains" / "test-domain" / "query-sets"
        query_sets_dir.mkdir(parents=True)

        # Write queries.jsonl
        with open(query_sets_dir / "test-queries.jsonl", "w") as f:
            f.write('{"query": "What is Islamic law?", "reference": "Answer 1"}\n')
            f.write('{"query": "What is inheritance law?", "reference": "Answer 2"}\n')

        # Load query set
        query_set = load_query_set(
            "test-domain", "test-queries", domains_dir=tmp_path / "domains"
        )

        assert len(query_set.queries) == 2
        assert query_set.queries[0].text == "What is Islamic law?"
        assert query_set.queries[0].reference == "Answer 1"
        assert query_set.queries[1].text == "What is inheritance law?"
        assert query_set.queries[1].reference == "Answer 2"

    def test_load_query_set_not_found(self, tmp_path):
        """Test loading non-existent query set."""
        with pytest.raises(ConfigError, match="Query set 'missing' not found"):
            load_query_set("test-domain", "missing", domains_dir=tmp_path / "domains")


# ============================================================================
# Path Utilities Tests
# ============================================================================


class TestPaths:
    """Tests for path utilities."""

    def test_ensure_domain_structure(self, tmp_path):
        """Test creating domain directory structure."""
        ensure_domain_structure("test-domain", domains_dir=tmp_path)

        # Check all directories exist
        assert (tmp_path / "test-domain").is_dir()
        assert (tmp_path / "test-domain" / "systems").is_dir()
        assert (tmp_path / "test-domain" / "query-sets").is_dir()
        assert (tmp_path / "test-domain" / "runs").is_dir()
        assert (tmp_path / "test-domain" / "comparisons").is_dir()

    def test_get_run_path(self, tmp_path):
        """Test generating run file path."""
        run_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        date = datetime(2025, 10, 25, tzinfo=timezone.utc)

        run_path = get_run_path("test-domain", run_id, date, domains_dir=tmp_path)

        expected = (
            tmp_path
            / "test-domain"
            / "runs"
            / "2025-10-25"
            / "550e8400-e29b-41d4-a716-446655440000.json"
        )
        assert run_path == expected

    def test_find_run_by_prefix(self, tmp_path):
        """Test finding run by UUID prefix."""
        # Create runs directory
        runs_dir = tmp_path / "test-domain" / "runs" / "2025-10-25"
        runs_dir.mkdir(parents=True)

        # Create run files
        run1 = runs_dir / "550e8400-e29b-41d4-a716-446655440000.json"
        run2 = runs_dir / "551e8400-e29b-41d4-a716-446655440000.json"
        run3 = runs_dir / "660e8400-e29b-41d4-a716-446655440000.json"
        run1.write_text("{}")
        run2.write_text("{}")
        run3.write_text("{}")

        # Find by full prefix (unique)
        found = find_run_by_prefix("test-domain", "550e", domains_dir=tmp_path)
        assert found == run1

        found = find_run_by_prefix("test-domain", "551e", domains_dir=tmp_path)
        assert found == run2

        found = find_run_by_prefix("test-domain", "660e", domains_dir=tmp_path)
        assert found == run3

        # Prefix too short (ambiguous - "55" matches both "550e..." and "551e...")
        with pytest.raises(RunError, match="Multiple runs found"):
            find_run_by_prefix("test-domain", "55", domains_dir=tmp_path)

        # No match
        with pytest.raises(RunError, match="No run found"):
            find_run_by_prefix("test-domain", "999", domains_dir=tmp_path)

    def test_list_systems(self, tmp_path):
        """Test listing systems in a domain."""
        systems_dir = tmp_path / "test-domain" / "systems"
        systems_dir.mkdir(parents=True)

        # Create system files
        (systems_dir / "vectara-default.yaml").write_text("name: vectara-default")
        (systems_dir / "agentset.yaml").write_text("name: agentset")

        systems = list_systems("test-domain", domains_dir=tmp_path)

        assert systems == ["agentset", "vectara-default"]

    def test_list_query_sets(self, tmp_path):
        """Test listing query sets in a domain."""
        query_sets_dir = tmp_path / "test-domain" / "query-sets"
        query_sets_dir.mkdir(parents=True)

        # Create query set files
        (query_sets_dir / "test-queries.txt").write_text("Query 1\nQuery 2")
        (query_sets_dir / "eval-set.jsonl").write_text('{"query": "Test"}')

        query_sets = list_query_sets("test-domain", domains_dir=tmp_path)

        assert query_sets == ["eval-set", "test-queries"]


# ============================================================================
# Storage Tests
# ============================================================================


class TestStorage:
    """Tests for run and comparison storage."""

    def test_save_and_load_run(self, tmp_path):
        """Test saving and loading a run."""
        run = Run(
            id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            domain="test-domain",
            system="vectara-test",
            query_set="test-queries",
            status=RunStatus.COMPLETED,
            results=[
                QueryResult(
                    query="Test query",
                    retrieved=[RetrievedChunk(content="Test content", score=0.95)],
                    reference=None,
                    duration_ms=123.45,
                    error=None,
                )
            ],
            system_config=SystemConfig(
                name="vectara-test",
                tool="vectara",
                config={"api_key": "${VECTARA_API_KEY}", "top_k": 5},
            ),
            query_set_snapshot=QuerySet(
                name="test-queries",
                domain="test-domain",
                queries=[Query(text="Test query")],
            ),
            started_at=datetime(2025, 10, 25, 12, 0, 0, tzinfo=timezone.utc),
            completed_at=datetime(2025, 10, 25, 12, 5, 0, tzinfo=timezone.utc),
        )

        # Save run
        saved_path = save_run(run, domains_dir=tmp_path)
        assert saved_path.exists()

        # Load run by full UUID
        loaded = load_run(
            "test-domain",
            "550e8400-e29b-41d4-a716-446655440000",
            domains_dir=tmp_path,
        )
        assert loaded.id == run.id
        assert loaded.system == run.system

        # Load run by prefix
        loaded = load_run("test-domain", "550e", domains_dir=tmp_path)
        assert loaded.id == run.id

    def test_list_runs(self, tmp_path):
        """Test listing runs with filters."""
        # Create multiple runs
        for i in range(3):
            run = Run(
                id=uuid4(),
                domain="test-domain",
                system=f"system-{i}",
                query_set="test-queries",
                status=RunStatus.COMPLETED,
                results=[],
                system_config=SystemConfig(
                    name=f"system-{i}", tool="vectara", config={}
                ),
                query_set_snapshot=QuerySet(
                    name="test-queries",
                    domain="test-domain",
                    queries=[Query(text="Test")],
                ),
                started_at=datetime.now(timezone.utc),
                completed_at=None,
            )
            save_run(run, domains_dir=tmp_path)

        # List all runs
        runs = list_runs("test-domain", domains_dir=tmp_path)
        assert len(runs) == 3

        # List with limit
        runs = list_runs("test-domain", limit=2, domains_dir=tmp_path)
        assert len(runs) == 2

        # Filter by system
        runs = list_runs("test-domain", system="system-0", domains_dir=tmp_path)
        assert len(runs) == 1
        assert runs[0].system == "system-0"

    def test_save_and_load_comparison(self, tmp_path):
        """Test saving and loading a comparison."""
        comparison = Comparison(
            id=UUID("660e8400-e29b-41d4-a716-446655440000"),
            domain="test-domain",
            runs=[UUID("550e8400-e29b-41d4-a716-446655440000")],
            evaluations=[
                EvaluationResult(
                    query="Test query",
                    reference=None,
                    run_results={"system1": [RetrievedChunk(content="Result 1")]},
                    evaluation={"winner": "system1", "reasoning": "Better results"},
                )
            ],
            evaluator_config=EvaluatorConfig(
                model="claude-3-5-sonnet-20241022",
                temperature=0.0,
                prompt_template="Compare these",
            ),
            created_at=datetime(2025, 10, 25, 12, 0, 0, tzinfo=timezone.utc),
        )

        # Save comparison
        saved_path = save_comparison(comparison, domains_dir=tmp_path)
        assert saved_path.exists()

        # Load comparison
        loaded = load_comparison("test-domain", str(comparison.id), domains_dir=tmp_path)
        assert loaded.id == comparison.id
        assert len(loaded.evaluations) == 1

    def test_list_comparisons(self, tmp_path):
        """Test listing comparisons."""
        # Create multiple comparisons
        for i in range(3):
            comparison = Comparison(
                id=uuid4(),
                domain="test-domain",
                runs=[uuid4()],
                evaluations=[],
                evaluator_config=EvaluatorConfig(
                    model="claude-3-5-sonnet-20241022",
                    temperature=0.0,
                    prompt_template="Compare",
                ),
                created_at=datetime.now(timezone.utc),
            )
            save_comparison(comparison, domains_dir=tmp_path)

        # List all comparisons
        comparisons = list_comparisons("test-domain", domains_dir=tmp_path)
        assert len(comparisons) == 3

        # List with limit
        comparisons = list_comparisons("test-domain", limit=2, domains_dir=tmp_path)
        assert len(comparisons) == 2
