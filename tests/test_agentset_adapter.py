"""Tests for Agentset adapter."""

import pytest
import os
from unittest.mock import patch, MagicMock, Mock

from ragdiff.adapters.agentset import AgentsetAdapter
from ragdiff.core.models import ToolConfig, RagResult


class TestAgentsetAdapter:
    """Test Agentset adapter."""

    @pytest.fixture
    def tool_config(self):
        """Create test configuration."""
        return ToolConfig(
            name="agentset",
            api_key_env="AGENTSET_API_TOKEN",
            namespace_id_env="AGENTSET_NAMESPACE_ID",
            timeout=60,
            default_top_k=10
        )

    @pytest.fixture
    def mock_search_data(self):
        """Create mock SearchData objects."""
        # Create mock SearchData objects
        mock_data_1 = Mock()
        mock_data_1.id = "doc_1"
        mock_data_1.text = "First result about tafsir of Surah Al-Fatiha"
        mock_data_1.score = 0.95
        mock_data_1.metadata = Mock()
        mock_data_1.metadata.filename = "section-1-1-to-1-7.txt"
        mock_data_1.metadata.filetype = "text/plain"
        mock_data_1.metadata.file_directory = "ibn-kathir/sections/surah-001"
        mock_data_1.metadata.sequence_number = 1
        mock_data_1.metadata.languages = ["ar", "en"]

        mock_data_2 = Mock()
        mock_data_2.id = "doc_2"
        mock_data_2.text = "Second result about tafsir"
        mock_data_2.score = 0.85
        mock_data_2.metadata = Mock()
        mock_data_2.metadata.filename = "section-1-8-to-1-10.txt"
        mock_data_2.metadata.filetype = "text/plain"
        mock_data_2.metadata.file_directory = "ibn-kathir/sections/surah-001"
        mock_data_2.metadata.sequence_number = 2
        mock_data_2.metadata.languages = None

        return [mock_data_1, mock_data_2]

    @patch.dict(os.environ, {
        "AGENTSET_API_TOKEN": "test_token",
        "AGENTSET_NAMESPACE_ID": "test_namespace"
    })
    @patch('ragdiff.adapters.agentset.Agentset')
    def test_initialization(self, mock_agentset_class, tool_config):
        """Test adapter initialization."""
        mock_client = Mock()
        mock_agentset_class.return_value = mock_client

        adapter = AgentsetAdapter(tool_config)

        # Verify Agentset client was initialized
        mock_agentset_class.assert_called_once_with(
            token="test_token",
            namespace_id="test_namespace"
        )

        assert adapter.name == "agentset"
        assert adapter.description == "Agentset RAG-as-a-Service platform"
        assert adapter.client == mock_client

    @patch.dict(os.environ, {})
    def test_initialization_missing_token(self, tool_config):
        """Test initialization fails without API token."""
        with pytest.raises(ValueError) as exc_info:
            AgentsetAdapter(tool_config)

        assert "AGENTSET_API_TOKEN" in str(exc_info.value)

    @patch.dict(os.environ, {"AGENTSET_API_TOKEN": "test_token"})
    def test_initialization_missing_namespace(self, tool_config):
        """Test initialization fails without namespace ID."""
        with pytest.raises(ValueError) as exc_info:
            AgentsetAdapter(tool_config)

        assert "AGENTSET_NAMESPACE_ID" in str(exc_info.value)

    @patch.dict(os.environ, {
        "AGENTSET_API_TOKEN": "test_token",
        "AGENTSET_NAMESPACE_ID": "test_namespace"
    })
    @patch('ragdiff.adapters.agentset.Agentset')
    def test_search_success(self, mock_agentset_class, tool_config, mock_search_data):
        """Test successful search."""
        # Setup mock client
        mock_client = Mock()
        mock_search = Mock()
        mock_search.execute = Mock(return_value=mock_search_data)
        mock_client.search = mock_search
        mock_agentset_class.return_value = mock_client

        adapter = AgentsetAdapter(tool_config)
        results = adapter.search("tafsir of Al-Fatiha", top_k=5)

        # Verify search was called correctly
        mock_search.execute.assert_called_once_with(
            query="tafsir of Al-Fatiha",
            top_k=5.0,  # Agentset expects float
            include_metadata=True,
            mode='semantic'
        )

        # Verify results
        assert len(results) == 2

        # Check first result
        assert results[0].id == "doc_1"
        assert results[0].text == "First result about tafsir of Surah Al-Fatiha"
        assert results[0].score == 0.95
        assert results[0].source == "section-1-1-to-1-7.txt"
        assert results[0].metadata["filename"] == "section-1-1-to-1-7.txt"
        assert results[0].metadata["filetype"] == "text/plain"
        assert results[0].metadata["sequence_number"] == 1
        assert results[0].metadata["languages"] == ["ar", "en"]

        # Check second result
        assert results[1].id == "doc_2"
        assert results[1].text == "Second result about tafsir"
        assert results[1].score == 0.85
        assert results[1].metadata["filename"] == "section-1-8-to-1-10.txt"

    @patch.dict(os.environ, {
        "AGENTSET_API_TOKEN": "test_token",
        "AGENTSET_NAMESPACE_ID": "test_namespace"
    })
    @patch('ragdiff.adapters.agentset.Agentset')
    def test_search_empty_results(self, mock_agentset_class, tool_config):
        """Test search with no results."""
        mock_client = Mock()
        mock_search = Mock()
        mock_search.execute = Mock(return_value=[])
        mock_client.search = mock_search
        mock_agentset_class.return_value = mock_client

        adapter = AgentsetAdapter(tool_config)
        results = adapter.search("nonexistent query")

        assert len(results) == 0

    @patch.dict(os.environ, {
        "AGENTSET_API_TOKEN": "test_token",
        "AGENTSET_NAMESPACE_ID": "test_namespace"
    })
    @patch('ragdiff.adapters.agentset.Agentset')
    def test_search_with_missing_text(self, mock_agentset_class, tool_config):
        """Test search filters out results without text."""
        # Create mock result with no text
        mock_data = Mock()
        mock_data.id = "doc_empty"
        mock_data.text = None  # No text
        mock_data.score = 0.9
        mock_data.metadata = None

        mock_client = Mock()
        mock_search = Mock()
        mock_search.execute = Mock(return_value=[mock_data])
        mock_client.search = mock_search
        mock_agentset_class.return_value = mock_client

        adapter = AgentsetAdapter(tool_config)
        results = adapter.search("test query")

        # Should filter out result with no text
        assert len(results) == 0

    @patch.dict(os.environ, {
        "AGENTSET_API_TOKEN": "test_token",
        "AGENTSET_NAMESPACE_ID": "test_namespace"
    })
    @patch('ragdiff.adapters.agentset.Agentset')
    def test_search_without_metadata(self, mock_agentset_class, tool_config):
        """Test search with results that have no metadata."""
        # Create mock result without metadata
        mock_data = Mock()
        mock_data.id = "doc_no_meta"
        mock_data.text = "Result without metadata"
        mock_data.score = 0.8
        mock_data.metadata = None

        mock_client = Mock()
        mock_search = Mock()
        mock_search.execute = Mock(return_value=[mock_data])
        mock_client.search = mock_search
        mock_agentset_class.return_value = mock_client

        adapter = AgentsetAdapter(tool_config)
        results = adapter.search("test query")

        assert len(results) == 1
        assert results[0].text == "Result without metadata"
        assert results[0].source == "Agentset"  # Default source
        assert results[0].metadata["document_id"] == "doc_no_meta"

    @patch.dict(os.environ, {
        "AGENTSET_API_TOKEN": "test_token",
        "AGENTSET_NAMESPACE_ID": "test_namespace"
    })
    @patch('ragdiff.adapters.agentset.Agentset')
    def test_search_api_error(self, mock_agentset_class, tool_config):
        """Test search with API error."""
        mock_client = Mock()
        mock_search = Mock()
        mock_search.execute = Mock(side_effect=Exception("API Error"))
        mock_client.search = mock_search
        mock_agentset_class.return_value = mock_client

        adapter = AgentsetAdapter(tool_config)

        with pytest.raises(Exception) as exc_info:
            adapter.search("test query")

        assert "API Error" in str(exc_info.value)

    @patch.dict(os.environ, {
        "AGENTSET_API_TOKEN": "test_token",
        "AGENTSET_NAMESPACE_ID": "test_namespace"
    })
    @patch('ragdiff.adapters.agentset.Agentset')
    def test_score_normalization(self, mock_agentset_class, tool_config):
        """Test that scores are properly normalized."""
        # Create mock with high score
        mock_data = Mock()
        mock_data.id = "doc_1"
        mock_data.text = "Test result"
        mock_data.score = 150.0  # High score
        mock_data.metadata = None

        mock_client = Mock()
        mock_search = Mock()
        mock_search.execute = Mock(return_value=[mock_data])
        mock_client.search = mock_search
        mock_agentset_class.return_value = mock_client

        adapter = AgentsetAdapter(tool_config)
        results = adapter.search("test")

        # Score should be normalized
        assert results[0].score <= 1.0
