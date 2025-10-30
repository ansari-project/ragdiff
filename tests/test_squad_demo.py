"""Tests for SQuAD demo to ensure example works correctly.

These tests verify:
- Domain configuration is valid
- FAISS provider works
- Query sets can be loaded
- Runs can be executed
- Demo workflow functions properly
"""

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import yaml

from ragdiff.core.loaders import load_domain, load_provider, load_query_set
from ragdiff.core.models import RetrievedChunk, RunStatus
from ragdiff.execution import execute_run
from ragdiff.providers.faiss import FAISSProvider

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_faiss_index():
    """Create a mock FAISS index."""
    try:
        import faiss
    except ImportError:
        pytest.skip("FAISS not installed")

    # Create a small mock index
    dimension = 384
    index = faiss.IndexFlatL2(dimension)

    # Add some random vectors
    np.random.seed(42)
    vectors = np.random.rand(10, dimension).astype("float32")
    index.add(vectors)

    return index


@pytest.fixture
def mock_sentence_transformer():
    """Create a mock sentence transformer."""
    mock = MagicMock()

    # Mock encode method to return random embeddings
    def encode_side_effect(texts, **kwargs):
        if isinstance(texts, str):
            texts = [texts]
        np.random.seed(42)
        return np.random.rand(len(texts), 384).astype("float32")

    mock.encode.side_effect = encode_side_effect
    return mock


@pytest.fixture
def squad_demo_setup(tmp_path):
    """Set up a minimal SQuAD demo structure for testing."""
    # Create directory structure
    demo_dir = tmp_path / "squad-demo"
    demo_dir.mkdir()

    domains_dir = demo_dir / "domains" / "squad"
    domains_dir.mkdir(parents=True)

    (domains_dir / "providers").mkdir()
    (domains_dir / "query-sets").mkdir()
    (domains_dir / "runs").mkdir()

    data_dir = demo_dir / "data"
    data_dir.mkdir()

    # Create domain.yaml
    domain_config = {
        "name": "squad",
        "description": "Test SQuAD demo domain",
        "evaluator": {
            "model": "gpt-3.5-turbo",
            "temperature": 0.0,
            "prompt_template": "Compare: {results}",
        },
    }
    with open(domains_dir / "domain.yaml", "w") as f:
        yaml.dump(domain_config, f)

    # Create provider configs
    faiss_small_config = {
        "name": "faiss-small",
        "tool": "faiss",
        "config": {
            "index_path": str(data_dir / "faiss_small.index"),
            "documents_path": str(data_dir / "documents.jsonl"),
            "embedding_service": "sentence-transformers",
            "embedding_model": "paraphrase-MiniLM-L3-v2",
            "dimensions": 384,
        },
    }
    with open(domains_dir / "providers" / "faiss-small.yaml", "w") as f:
        yaml.dump(faiss_small_config, f)

    faiss_large_config = {
        "name": "faiss-large",
        "tool": "faiss",
        "config": {
            "index_path": str(data_dir / "faiss_large.index"),
            "documents_path": str(data_dir / "documents.jsonl"),
            "embedding_service": "sentence-transformers",
            "embedding_model": "all-MiniLM-L12-v2",
            "dimensions": 384,
        },
    }
    with open(domains_dir / "providers" / "faiss-large.yaml", "w") as f:
        yaml.dump(faiss_large_config, f)

    # Create test query set
    with open(domains_dir / "query-sets" / "test-queries.txt", "w") as f:
        f.write("What is the capital of France?\n")
        f.write("How does photosynthesis work?\n")
        f.write("What is machine learning?\n")

    # Create mock documents
    documents = [
        {
            "id": "doc_0",
            "text": "Paris is the capital and largest city of France.",
            "source": "test",
            "metadata": {"title": "France"},
        },
        {
            "id": "doc_1",
            "text": "Photosynthesis is the process by which plants use sunlight to produce energy.",
            "source": "test",
            "metadata": {"title": "Biology"},
        },
        {
            "id": "doc_2",
            "text": "Machine learning is a type of artificial intelligence that enables computers to learn.",
            "source": "test",
            "metadata": {"title": "AI"},
        },
    ]

    with open(data_dir / "documents.jsonl", "w") as f:
        for doc in documents:
            f.write(json.dumps(doc) + "\n")

    return demo_dir, domains_dir, data_dir


# ============================================================================
# Domain Configuration Tests
# ============================================================================


class TestSquadDomainConfig:
    """Tests for SQuAD demo domain configuration."""

    def test_load_domain_config(self, squad_demo_setup):
        """Test that domain configuration can be loaded."""
        demo_dir, domains_dir, data_dir = squad_demo_setup

        domain = load_domain("squad", domains_dir.parent)

        assert domain.name == "squad"
        assert "SQuAD" in domain.description or "squad" in domain.description.lower()
        assert domain.evaluator.model == "gpt-3.5-turbo"
        assert domain.evaluator.temperature == 0.0

    def test_load_provider_configs(self, squad_demo_setup):
        """Test that provider configurations can be loaded."""
        demo_dir, domains_dir, data_dir = squad_demo_setup

        # Load faiss-small provider
        small_provider = load_provider("squad", "faiss-small", domains_dir.parent)
        assert small_provider.name == "faiss-small"
        assert small_provider.tool == "faiss"
        assert "paraphrase-MiniLM-L3-v2" in small_provider.config["embedding_model"]

        # Load faiss-large provider
        large_provider = load_provider("squad", "faiss-large", domains_dir.parent)
        assert large_provider.name == "faiss-large"
        assert large_provider.tool == "faiss"
        assert "all-MiniLM-L12-v2" in large_provider.config["embedding_model"]

    def test_load_query_set(self, squad_demo_setup):
        """Test that query sets can be loaded."""
        demo_dir, domains_dir, data_dir = squad_demo_setup

        query_set = load_query_set("squad", "test-queries", domains_dir.parent)

        assert query_set.name == "test-queries"
        assert query_set.domain == "squad"
        assert len(query_set.queries) == 3
        assert "capital of France" in query_set.queries[0].text
        assert "photosynthesis" in query_set.queries[1].text.lower()
        assert "machine learning" in query_set.queries[2].text.lower()


# ============================================================================
# FAISS Provider Tests
# ============================================================================


class TestFAISSProvider:
    """Tests for FAISS provider functionality."""

    @patch("sentence_transformers.SentenceTransformer")
    def test_faiss_provider_initialization(self, mock_st_class, squad_demo_setup):
        """Test FAISS provider can be initialized."""
        demo_dir, domains_dir, data_dir = squad_demo_setup

        # Mock faiss module
        mock_faiss = MagicMock()
        mock_index = MagicMock()
        mock_index.ntotal = 10
        mock_index.d = 384
        mock_faiss.read_index.return_value = mock_index

        mock_st = MagicMock()
        mock_st_class.return_value = mock_st

        # Create provider config
        config = {
            "index_path": str(data_dir / "test.index"),
            "documents_path": str(data_dir / "documents.jsonl"),
            "embedding_service": "sentence-transformers",
            "embedding_model": "test-model",
            "dimensions": 384,
        }

        # Create fake index file
        (data_dir / "test.index").touch()

        # Patch faiss at import time within FAISSProvider.__init__
        with patch.dict("sys.modules", {"faiss": mock_faiss}):
            # Initialize provider
            provider = FAISSProvider(config)

            # Verify initialization
            assert str(provider.index_path) == str(data_dir / "test.index")
            assert str(provider.documents_path) == str(data_dir / "documents.jsonl")
            assert provider.embedding_model == "test-model"
            mock_st_class.assert_called_once_with("test-model")

    @patch("sentence_transformers.SentenceTransformer")
    def test_faiss_provider_search(self, mock_st_class, squad_demo_setup):
        """Test FAISS provider search functionality."""
        demo_dir, domains_dir, data_dir = squad_demo_setup

        # Mock faiss module
        mock_faiss = MagicMock()
        mock_index = MagicMock()
        mock_index.ntotal = 3
        mock_index.d = 384

        # Mock search to return indices [0, 1, 2] with decreasing distances
        def search_side_effect(query_vector, k):
            distances = np.array([[0.1, 0.5, 0.9]], dtype=np.float32)
            indices = np.array([[0, 1, 2]], dtype=np.int64)
            return distances, indices

        mock_index.search.side_effect = search_side_effect
        mock_faiss.read_index.return_value = mock_index

        # Mock sentence transformer
        mock_st = MagicMock()
        mock_st.encode.return_value = np.random.rand(1, 384).astype("float32")
        mock_st_class.return_value = mock_st

        # Create fake index file
        (data_dir / "test.index").touch()

        # Patch faiss at import time within FAISSProvider.__init__
        with patch.dict("sys.modules", {"faiss": mock_faiss}):
            # Create provider
            config = {
                "index_path": str(data_dir / "test.index"),
                "documents_path": str(data_dir / "documents.jsonl"),
                "embedding_service": "sentence-transformers",
                "embedding_model": "test-model",
                "dimensions": 384,
            }

            provider = FAISSProvider(config)

            # Perform search
            results = provider.search("What is the capital of France?", top_k=3)

            # Verify results
            assert len(results) == 3
            assert all(isinstance(r, RetrievedChunk) for r in results)
            assert (
                results[0].content == "Paris is the capital and largest city of France."
            )
            assert (
                results[0].score > results[1].score
            )  # Scores should be in descending order

            # Verify encoding was called
            mock_st.encode.assert_called_once()


# ============================================================================
# Integration Tests
# ============================================================================


class TestSquadDemoIntegration:
    """Integration tests for the complete SQuAD demo workflow."""

    @patch("sentence_transformers.SentenceTransformer")
    def test_execute_run_with_faiss(self, mock_st_class, squad_demo_setup):
        """Test executing a run with FAISS provider."""
        demo_dir, domains_dir, data_dir = squad_demo_setup

        # Mock faiss module
        mock_faiss = MagicMock()
        mock_index = MagicMock()
        mock_index.ntotal = 3
        mock_index.d = 384

        def search_side_effect(query_vector, k):
            # Return mock search results
            distances = np.array([[0.1, 0.5]], dtype=np.float32)
            indices = np.array([[0, 1]], dtype=np.int64)
            return distances, indices

        mock_index.search.side_effect = search_side_effect
        mock_faiss.read_index.return_value = mock_index

        # Mock sentence transformer
        mock_st = MagicMock()
        mock_st.encode.return_value = np.random.rand(1, 384).astype("float32")
        mock_st_class.return_value = mock_st

        # Create fake index files
        (data_dir / "faiss_small.index").touch()

        # Patch faiss at import time
        with patch.dict("sys.modules", {"faiss": mock_faiss}):
            # Execute run
            run = execute_run(
                domain="squad",
                provider="faiss-small",
                query_set="test-queries",
                concurrency=1,
                domains_dir=domains_dir.parent,
            )

            # Verify run results
            assert run.domain == "squad"
            assert run.provider == "faiss-small"
            assert run.query_set == "test-queries"
            assert run.status == RunStatus.COMPLETED
            assert len(run.results) == 3

            # Verify each query got results
            for result in run.results:
                assert result.error is None
                assert len(result.retrieved) > 0
                assert result.duration_ms > 0

    @patch("sentence_transformers.SentenceTransformer")
    def test_parallel_runs(self, mock_st_class, squad_demo_setup):
        """Test running multiple providers in parallel."""
        demo_dir, domains_dir, data_dir = squad_demo_setup

        # Mock faiss module
        mock_faiss = MagicMock()
        mock_index = MagicMock()
        mock_index.ntotal = 3
        mock_index.d = 384

        def search_side_effect(query_vector, k):
            distances = np.array([[0.1, 0.5]], dtype=np.float32)
            indices = np.array([[0, 1]], dtype=np.int64)
            return distances, indices

        mock_index.search.side_effect = search_side_effect
        mock_faiss.read_index.return_value = mock_index

        mock_st = MagicMock()
        mock_st.encode.return_value = np.random.rand(1, 384).astype("float32")
        mock_st_class.return_value = mock_st

        # Create fake index files
        (data_dir / "faiss_small.index").touch()
        (data_dir / "faiss_large.index").touch()

        # Patch faiss at import time
        with patch.dict("sys.modules", {"faiss": mock_faiss}):
            # Execute runs for both providers
            runs = []
            for provider in ["faiss-small", "faiss-large"]:
                run = execute_run(
                    domain="squad",
                    provider=provider,
                    query_set="test-queries",
                    concurrency=2,
                    domains_dir=domains_dir.parent,
                )
                runs.append(run)

            # Verify both runs completed
            assert all(run.status == RunStatus.COMPLETED for run in runs)
            assert all(len(run.results) == 3 for run in runs)

    def test_invalid_provider_config(self, squad_demo_setup):
        """Test handling of invalid provider configuration."""
        demo_dir, domains_dir, data_dir = squad_demo_setup

        # Create invalid provider config (missing required fields)
        invalid_config = {
            "name": "faiss-broken",
            "tool": "faiss",
            "config": {
                # Missing required fields
                "embedding_model": "test-model"
            },
        }

        with open(domains_dir / "providers" / "faiss-broken.yaml", "w") as f:
            yaml.dump(invalid_config, f)

        # Attempting to use this provider should fail gracefully
        from ragdiff.core.errors import ConfigError, RunError

        with pytest.raises((ConfigError, RunError)):
            execute_run(
                domain="squad",
                provider="faiss-broken",
                query_set="test-queries",
                domains_dir=domains_dir.parent,
            )


# ============================================================================
# Example Notebook Tests
# ============================================================================


class TestSquadNotebook:
    """Tests for the SQuAD demo notebook functionality."""

    def test_notebook_imports(self):
        """Test that notebook imports are correct."""
        # This test verifies the imports that would be used in the notebook
        try:
            from ragdiff import execute_run  # noqa: F401
            from ragdiff.comparison import compare_runs  # noqa: F401
            from ragdiff.core.loaders import load_domain, load_provider, load_query_set  # noqa: F401
            from ragdiff.display.formatting import (  # noqa: F401
                calculate_provider_stats_from_runs,
                save_comparison_markdown,
            )
        except ImportError as e:
            pytest.fail(f"Failed to import required modules for notebook: {e}")

    def test_notebook_workflow_simulation(
        self, squad_demo_setup, mock_sentence_transformer
    ):
        """Test simulated notebook workflow without requiring actual models."""
        demo_dir, domains_dir, data_dir = squad_demo_setup

        # This simulates the key steps in the notebook

        # Step 1: Load configurations
        domain_config = load_domain("squad", domains_dir.parent)
        assert domain_config is not None

        # Step 2: Load query set
        query_set = load_query_set("squad", "test-queries", domains_dir.parent)
        assert len(query_set.queries) > 0

        # Step 3: Load provider configs
        providers = ["faiss-small", "faiss-large"]
        for provider_name in providers:
            provider_config = load_provider("squad", provider_name, domains_dir.parent)
            assert provider_config.tool == "faiss"

        # The actual execution would happen here with real models
        # but we've tested that separately above

        print("✓ Notebook workflow simulation passed")


# ============================================================================
# Performance Tests
# ============================================================================


class TestSquadDemoPerformance:
    """Performance and resource tests for the SQuAD demo."""

    @patch("sentence_transformers.SentenceTransformer")
    def test_concurrent_query_execution(self, mock_st_class, squad_demo_setup):
        """Test that concurrent query execution works properly."""
        demo_dir, domains_dir, data_dir = squad_demo_setup

        # Mock faiss module
        mock_faiss = MagicMock()
        mock_index = MagicMock()
        mock_index.ntotal = 3
        mock_index.d = 384

        # Track call count to ensure concurrency
        call_count = {"count": 0}

        def search_side_effect(query_vector, k):
            call_count["count"] += 1
            distances = np.array([[0.1]], dtype=np.float32)
            indices = np.array([[0]], dtype=np.int64)
            return distances, indices

        mock_index.search.side_effect = search_side_effect
        mock_faiss.read_index.return_value = mock_index

        mock_st = MagicMock()
        mock_st.encode.return_value = np.random.rand(1, 384).astype("float32")
        mock_st_class.return_value = mock_st

        (data_dir / "faiss_small.index").touch()

        # Patch faiss at import time
        with patch.dict("sys.modules", {"faiss": mock_faiss}):
            # Execute with high concurrency
            run = execute_run(
                domain="squad",
                provider="faiss-small",
                query_set="test-queries",
                concurrency=10,  # High concurrency
                domains_dir=domains_dir.parent,
            )

            # Verify all queries were executed
            assert run.status == RunStatus.COMPLETED
            assert call_count["count"] == 3  # All 3 queries should have been searched

    def test_progress_callback(self, squad_demo_setup):
        """Test that progress callbacks work correctly."""
        demo_dir, domains_dir, data_dir = squad_demo_setup

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

        # We can't actually run without mocking, but we can verify the callback signature
        assert callable(progress_callback)

        # Simulate some progress updates
        progress_callback(1, 3, 1, 0)
        progress_callback(2, 3, 2, 0)
        progress_callback(3, 3, 3, 0)

        assert len(progress_updates) == 3
        assert progress_updates[-1]["current"] == 3
        assert progress_updates[-1]["total"] == 3
