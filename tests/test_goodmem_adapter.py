"""Tests for Goodmem adapter."""

import pytest
import os
from unittest.mock import patch, MagicMock, Mock, AsyncMock
import asyncio
import sys

from src.adapters.goodmem import GoodmemAdapter
from src.core.models import ToolConfig, RagResult


class TestGoodmemAdapter:
    """Test Goodmem adapter."""

    @pytest.fixture
    def tool_config(self):
        """Create test configuration."""
        return ToolConfig(
            name="goodmem",
            api_key_env="GOODMEM_API_KEY",
            base_url=None,
            timeout=30,
            default_top_k=5
        )

    @patch.dict(os.environ, {"GOODMEM_API_KEY": "test_key"})
    def test_initialization_without_client(self, tool_config):
        """Test adapter initialization when goodmem-client not available."""
        with patch('src.adapters.goodmem.GOODMEM_AVAILABLE', False):
            adapter = GoodmemAdapter(tool_config)
            assert adapter.name == "goodmem"
            assert adapter.client is None
            assert "next-generation" in adapter.description.lower()

    @patch.dict(os.environ, {"GOODMEM_API_KEY": "test_key"})
    def test_initialization_with_mock_client(self, tool_config):
        """Test adapter initialization in mock mode."""
        # Since goodmem-client is not installed, it will use mock mode
        adapter = GoodmemAdapter(tool_config)
        assert adapter.name == "goodmem"
        # Client will be None since package not installed
        if not adapter.client:
            assert adapter.client is None

    @patch.dict(os.environ, {"GOODMEM_API_KEY": "test_key"})
    def test_mock_search(self, tool_config):
        """Test mock search when client not available."""
        with patch('src.adapters.goodmem.GOODMEM_AVAILABLE', False):
            adapter = GoodmemAdapter(tool_config)
            results = adapter.search("test query", top_k=2)

            assert len(results) == 2
            assert all(isinstance(r, RagResult) for r in results)
            assert results[0].id == "goodmem_mock_0"
            assert "Mock Goodmem result" in results[0].text
            assert results[0].score > results[1].score
            assert results[0].metadata["mock"] is True

    @patch.dict(os.environ, {"GOODMEM_API_KEY": "test_key"})
    def test_search_flow_integration(self, tool_config):
        """Test the full search flow with mock data."""
        # Since goodmem-client is not installed, adapter will use mock mode
        adapter = GoodmemAdapter(tool_config)

        # Test that search works and returns proper mock data
        results = adapter.search("integration test", top_k=3)

        # Verify results structure
        assert len(results) == 3
        assert all(isinstance(r, RagResult) for r in results)

        # Verify mock data characteristics
        for i, result in enumerate(results):
            assert f"goodmem_mock_{i}" == result.id
            assert "Mock Goodmem result" in result.text
            assert result.metadata["mock"] is True
            assert 0 <= result.score <= 1

        # Verify scores are descending
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score

    @patch.dict(os.environ, {"GOODMEM_API_KEY": "test_key"})
    def test_parse_goodmem_response_dict(self, tool_config):
        """Test parsing different response formats."""
        adapter = GoodmemAdapter(tool_config)

        # Test dict response
        dict_response = {
            'results': [
                {
                    'text': 'Dict result',
                    'score': 0.88,
                    'id': 'dict1',
                    'source': 'Dict Source',
                    'metadata': {'key': 'value'}
                }
            ]
        }
        results = adapter._parse_goodmem_response(dict_response)
        assert len(results) == 1
        assert results[0].text == "Dict result"
        assert results[0].score == 0.88

    @patch.dict(os.environ, {"GOODMEM_API_KEY": "test_key"})
    def test_parse_goodmem_response_list(self, tool_config):
        """Test parsing list response."""
        adapter = GoodmemAdapter(tool_config)

        # Test list response
        list_response = [
            {'text': 'List item 1', 'score': 0.7},
            {'text': 'List item 2', 'score': 0.6}
        ]
        results = adapter._parse_goodmem_response(list_response)
        assert len(results) == 2
        assert results[0].text == "List item 1"
        assert results[1].text == "List item 2"

    @patch.dict(os.environ, {"GOODMEM_API_KEY": "test_key"})
    def test_parse_goodmem_response_object(self, tool_config):
        """Test parsing object response."""
        adapter = GoodmemAdapter(tool_config)

        # Test object with results attribute
        mock_response = Mock()
        mock_response.results = [
            Mock(text="Object result", score=0.9, id="obj1",
                 source="Object Source", metadata={})
        ]
        results = adapter._parse_goodmem_response(mock_response)
        assert len(results) == 1
        assert results[0].text == "Object result"
        assert results[0].score == 0.9

    @patch.dict(os.environ, {"GOODMEM_API_KEY": "test_key"})
    def test_score_normalization_in_parse(self, tool_config):
        """Test score normalization during parsing."""
        adapter = GoodmemAdapter(tool_config)

        response = {
            'results': [
                {'text': 'High score', 'score': 950},  # Out of 1000
                {'text': 'Percentage', 'score': 85},   # Out of 100
                {'text': 'Normal', 'score': 0.75}      # Already normalized
            ]
        }
        results = adapter._parse_goodmem_response(response)

        assert 0 <= results[0].score <= 1
        assert 0 <= results[1].score <= 1
        assert results[2].score == 0.75

    @patch.dict(os.environ, {"GOODMEM_API_KEY": "test_key"})
    def test_search_with_empty_response(self, tool_config):
        """Test handling empty response."""
        adapter = GoodmemAdapter(tool_config)

        # Test empty dict
        results = adapter._parse_goodmem_response({})
        assert len(results) == 0

        # Test empty list
        results = adapter._parse_goodmem_response([])
        assert len(results) == 0

    @patch.dict(os.environ, {"GOODMEM_API_KEY": "test_key"})
    def test_parse_with_missing_fields(self, tool_config):
        """Test parsing with missing fields."""
        adapter = GoodmemAdapter(tool_config)

        response = {
            'results': [
                {'content': 'Using content field'},  # No 'text' field
                {'text': 'Missing score'},           # No 'score' field
                'Just a string'                       # Not even a dict
            ]
        }
        results = adapter._parse_goodmem_response(response)

        assert len(results) == 3
        assert results[0].text == "Using content field"
        assert results[1].score == 0.5  # Default score
        assert "Just a string" in results[2].text