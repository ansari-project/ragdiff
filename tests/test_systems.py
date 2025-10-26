"""Tests for RAGDiff v2.0 systems (Phase 2).

Tests cover:
- System ABC
- Tool registry (register_tool, get_tool, list_tools)
- Tool factory (create_system)
- System implementations (Vectara, MongoDB, Agentset)
"""

import pytest

from ragdiff.core.errors import ConfigError, RunError
from ragdiff.core.models_v2 import RetrievedChunk, SystemConfig
from ragdiff.systems import (
    System,
    create_system,
    get_tool,
    is_tool_registered,
    list_tools,
    register_tool,
)
from ragdiff.systems.registry import TOOL_REGISTRY


# ============================================================================
# Test Fixtures
# ============================================================================


class MockSystem(System):
    """Mock system for testing."""

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Mock search that returns dummy chunks."""
        return [
            RetrievedChunk(
                content=f"Mock result {i} for: {query}",
                score=1.0 - (i * 0.1),
                metadata={"index": i}
            )
            for i in range(min(top_k, 3))
        ]


class ErrorSystem(System):
    """System that always raises errors for testing."""

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Always raises an error."""
        raise RunError("Mock error")


@pytest.fixture
def clean_registry():
    """Clear the tool registry before each test."""
    original_registry = TOOL_REGISTRY.copy()
    TOOL_REGISTRY.clear()
    yield
    TOOL_REGISTRY.clear()
    TOOL_REGISTRY.update(original_registry)


# ============================================================================
# System ABC Tests
# ============================================================================


class TestSystemABC:
    """Tests for System abstract base class."""

    def test_system_abc_cannot_instantiate(self):
        """Test that System ABC cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            System(config={})

    def test_system_requires_search_method(self):
        """Test that System subclasses must implement search()."""
        class IncompleteSystem(System):
            pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteSystem(config={})

    def test_mock_system_works(self):
        """Test that a valid System implementation works."""
        system = MockSystem(config={"test": "config"})
        assert system.config == {"test": "config"}

        chunks = system.search("test query", top_k=2)
        assert len(chunks) == 2
        assert chunks[0].content == "Mock result 0 for: test query"
        assert chunks[0].score == 1.0
        assert chunks[1].score == 0.9

    def test_system_repr(self):
        """Test System __repr__."""
        system = MockSystem(config={})
        assert repr(system) == "MockSystem()"


# ============================================================================
# Tool Registry Tests
# ============================================================================


class TestToolRegistry:
    """Tests for tool registry."""

    def test_register_tool(self, clean_registry):
        """Test registering a tool."""
        register_tool("mock", MockSystem)
        assert "mock" in TOOL_REGISTRY
        assert TOOL_REGISTRY["mock"] == MockSystem

    def test_register_tool_invalid_name(self, clean_registry):
        """Test registering tool with invalid name."""
        with pytest.raises(ConfigError, match="Tool name cannot be empty"):
            register_tool("", MockSystem)

        with pytest.raises(ConfigError, match="must be alphanumeric"):
            register_tool("my/tool", MockSystem)

        with pytest.raises(ConfigError, match="must be alphanumeric"):
            register_tool("my tool", MockSystem)

    def test_register_tool_not_system_subclass(self, clean_registry):
        """Test registering a class that doesn't inherit from System."""
        class NotASystem:
            pass

        with pytest.raises(ConfigError, match="must inherit from System"):
            register_tool("bad", NotASystem)

    def test_register_tool_duplicate_warning(self, clean_registry):
        """Test registering the same tool name twice overwrites."""
        register_tool("mock", MockSystem)
        assert TOOL_REGISTRY["mock"] == MockSystem

        register_tool("mock", ErrorSystem)  # Overwrite
        assert TOOL_REGISTRY["mock"] == ErrorSystem  # Second registration wins

    def test_get_tool(self, clean_registry):
        """Test getting a tool from registry."""
        register_tool("mock", MockSystem)

        tool_class = get_tool("mock")
        assert tool_class == MockSystem

    def test_get_tool_not_found(self, clean_registry):
        """Test getting a tool that doesn't exist."""
        with pytest.raises(ConfigError, match="Unknown tool 'missing'"):
            get_tool("missing")

        # Register one tool to test error message shows available tools
        register_tool("mock", MockSystem)
        with pytest.raises(ConfigError, match="Available tools: mock"):
            get_tool("missing")

    def test_list_tools(self, clean_registry):
        """Test listing all registered tools."""
        assert list_tools() == []

        register_tool("vectara", MockSystem)
        register_tool("mongodb", MockSystem)
        register_tool("agentset", MockSystem)

        tools = list_tools()
        assert tools == ["agentset", "mongodb", "vectara"]  # Sorted

    def test_is_tool_registered(self, clean_registry):
        """Test checking if tool is registered."""
        assert not is_tool_registered("mock")

        register_tool("mock", MockSystem)
        assert is_tool_registered("mock")

        assert not is_tool_registered("other")


# ============================================================================
# Tool Factory Tests
# ============================================================================


class TestToolFactory:
    """Tests for create_system factory."""

    def test_create_system_success(self, clean_registry):
        """Test creating a system from config."""
        register_tool("mock", MockSystem)

        config = SystemConfig(
            name="test-system",
            tool="mock",
            config={"api_key": "test123"}
        )

        system = create_system(config)
        assert isinstance(system, MockSystem)
        assert system.config == {"api_key": "test123"}

    def test_create_system_tool_not_found(self, clean_registry):
        """Test creating system with unknown tool."""
        config = SystemConfig(
            name="test-system",
            tool="missing",
            config={}
        )

        with pytest.raises(ConfigError, match="Failed to create system"):
            create_system(config)

    def test_create_system_initialization_error(self, clean_registry):
        """Test handling system initialization errors."""
        class BadSystem(System):
            def __init__(self, config: dict):
                raise ValueError("Bad config!")

            def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
                return []

        register_tool("bad", BadSystem)

        config = SystemConfig(
            name="bad-system",
            tool="bad",
            config={}
        )

        with pytest.raises(RunError, match="Failed to initialize system"):
            create_system(config)


# ============================================================================
# Vectara System Tests
# ============================================================================


class TestVectaraSystem:
    """Tests for VectaraSystem."""

    def test_vectara_registered(self):
        """Test that Vectara tool is registered."""
        assert is_tool_registered("vectara")

    def test_vectara_missing_api_key(self):
        """Test Vectara requires api_key."""
        with pytest.raises(ConfigError, match="missing required field: api_key"):
            config = SystemConfig(
                name="vectara-test",
                tool="vectara",
                config={"corpus_id": "test"}
            )
            create_system(config)

    def test_vectara_missing_corpus_id(self):
        """Test Vectara requires corpus_id."""
        with pytest.raises(ConfigError, match="missing required field: corpus_id"):
            config = SystemConfig(
                name="vectara-test",
                tool="vectara",
                config={"api_key": "test"}
            )
            create_system(config)

    def test_vectara_initialization_success(self):
        """Test Vectara system initializes successfully."""
        config = SystemConfig(
            name="vectara-test",
            tool="vectara",
            config={
                "api_key": "vsk_test123",
                "corpus_id": "test-corpus",
                "base_url": "https://api.vectara.io",
                "timeout": 30
            }
        )

        system = create_system(config)
        assert system.api_key == "vsk_test123"
        assert system.corpus_id == "test-corpus"
        assert system.timeout == 30

    def test_vectara_repr(self):
        """Test Vectara __repr__."""
        config = SystemConfig(
            name="vectara-test",
            tool="vectara",
            config={"api_key": "test", "corpus_id": "my-corpus"}
        )

        system = create_system(config)
        assert repr(system) == "VectaraSystem(corpus_id='my-corpus')"


# ============================================================================
# MongoDB System Tests
# ============================================================================


class TestMongoDBSystem:
    """Tests for MongoDBSystem."""

    def test_mongodb_registered(self):
        """Test that MongoDB tool is registered."""
        assert is_tool_registered("mongodb")

    def test_mongodb_missing_dependencies_error(self):
        """Test MongoDB raises error if dependencies not installed."""
        # This test assumes pymongo/sentence-transformers may not be installed
        # If they are installed, the error should be about missing config instead
        config = SystemConfig(
            name="mongodb-test",
            tool="mongodb",
            config={}
        )

        with pytest.raises(ConfigError):
            create_system(config)

    def test_mongodb_missing_required_config(self):
        """Test MongoDB requires specific config fields."""
        # Test missing connection_uri
        config = SystemConfig(
            name="mongodb-test",
            tool="mongodb",
            config={
                "database": "test",
                "collection": "docs",
                "index_name": "vector_idx"
            }
        )

        with pytest.raises(ConfigError):
            create_system(config)


# ============================================================================
# Agentset System Tests
# ============================================================================


class TestAgentsetSystem:
    """Tests for AgentsetSystem."""

    def test_agentset_registered(self):
        """Test that Agentset tool is registered."""
        assert is_tool_registered("agentset")

    def test_agentset_missing_api_token(self):
        """Test Agentset requires api_token."""
        with pytest.raises(ConfigError, match="missing required field: api_token"):
            config = SystemConfig(
                name="agentset-test",
                tool="agentset",
                config={"namespace_id": "ns_123"}
            )
            create_system(config)

    def test_agentset_missing_namespace_id(self):
        """Test Agentset requires namespace_id."""
        with pytest.raises(ConfigError, match="missing required field: namespace_id"):
            config = SystemConfig(
                name="agentset-test",
                tool="agentset",
                config={"api_token": "token_123"}
            )
            create_system(config)

    def test_agentset_initialization_success(self):
        """Test Agentset system initializes successfully.

        Note: Agentset client doesn't validate credentials on init,
        so we can create a system with any credentials.
        Validation happens when search() is called.
        """
        config = SystemConfig(
            name="agentset-test",
            tool="agentset",
            config={
                "api_token": "test_token",
                "namespace_id": "test_namespace",
                "rerank": False
            }
        )

        system = create_system(config)
        assert system.api_token == "test_token"
        assert system.namespace_id == "test_namespace"
        assert system.rerank is False


# ============================================================================
# Integration Tests
# ============================================================================


class TestSystemIntegration:
    """Integration tests for system workflow."""

    def test_full_workflow_with_mock_system(self, clean_registry):
        """Test complete workflow: register → create → search."""
        # Register tool
        register_tool("mock", MockSystem)

        # Create system from config
        config = SystemConfig(
            name="mock-system",
            tool="mock",
            config={"setting": "value"}
        )
        system = create_system(config)

        # Use system
        chunks = system.search("test query", top_k=3)

        assert len(chunks) == 3
        assert all(isinstance(c, RetrievedChunk) for c in chunks)
        assert chunks[0].score >= chunks[1].score >= chunks[2].score

    def test_list_all_registered_tools(self):
        """Test listing all registered tools (real systems)."""
        tools = list_tools()

        # Should have at least the 3 core systems
        assert "vectara" in tools
        assert "mongodb" in tools
        assert "agentset" in tools

        # Should be sorted
        assert tools == sorted(tools)
