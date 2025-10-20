"""Tests for Vectara adapter."""

import os
from unittest.mock import Mock, patch

import pytest
import requests

from ragdiff.adapters.vectara import VectaraAdapter
from ragdiff.core.models import RagResult, ToolConfig


class TestVectaraAdapter:
    """Test Vectara adapter."""

    @pytest.fixture
    def tool_config(self):
        """Create test configuration."""
        return ToolConfig(
            name="mawsuah",
            api_key_env="VECTARA_API_KEY",
            corpus_id="test_corpus",
            base_url="https://api.vectara.io",
            timeout=30,
            default_top_k=5,
        )

    @pytest.fixture
    def mock_vectara_response(self):
        """Create mock Vectara API response."""
        return {
            "responseSet": [
                {
                    "response": [
                        {
                            "text": "First result text about Islamic law",
                            "score": 0.95,
                            "documentIndex": "doc_1",
                            "metadata": [
                                {"name": "source", "value": "Fiqh Book 1"},
                                {"name": "author", "value": "Scholar A"},
                            ],
                        },
                        {
                            "text": "Second result text about jurisprudence",
                            "score": 0.85,
                            "documentIndex": "doc_2",
                            "metadata": [{"name": "source", "value": "Fiqh Book 2"}],
                        },
                    ],
                    "summary": [{"text": "This is a summary of the search results."}],
                }
            ]
        }

    @patch.dict(os.environ, {"VECTARA_API_KEY": "test_key"})
    def test_initialization(self, tool_config):
        """Test adapter initialization."""
        adapter = VectaraAdapter(tool_config)
        assert adapter.name == "mawsuah"
        assert adapter.corpus_id == "test_corpus"
        assert "jurisprudence" in adapter.description.lower()

    @patch.dict(os.environ, {"VECTARA_API_KEY": "test_key"})
    @patch("requests.post")
    def test_search_success(self, mock_post, tool_config, mock_vectara_response):
        """Test successful search."""
        # Setup mock response
        mock_response = Mock()
        mock_response.json.return_value = mock_vectara_response
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        adapter = VectaraAdapter(tool_config)
        results = adapter.search("Islamic inheritance law", top_k=3)

        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://api.vectara.io/v1/query"

        # Check request headers
        headers = call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer test_key"
        # customer-id header is no longer required in Vectara v2 API
        assert "customer-id" not in headers

        # Check request body
        body = call_args[1]["json"]
        assert body["query"][0]["query"] == "Islamic inheritance law"
        assert body["query"][0]["num_results"] == 3
        # Verify corpus_key doesn't have customer_id in v2 API
        corpus_key = body["query"][0]["corpus_key"][0]
        assert "customer_id" not in corpus_key
        assert corpus_key["corpus_id"] == "test_corpus"

        # Verify results
        assert len(results) == 3  # Summary + 2 results

        # Check summary (should be first)
        assert results[0].id == "summary"
        assert results[0].score == 1.0
        assert "summary" in results[0].text.lower()

        # Check first actual result
        assert results[1].text == "First result text about Islamic law"
        assert results[1].score == 0.95
        assert results[1].source == "Fiqh Book 1"
        assert results[1].metadata["author"] == "Scholar A"

    @patch.dict(os.environ, {"VECTARA_API_KEY": "test_key"})
    @patch("requests.post")
    def test_search_empty_response(self, mock_post, tool_config):
        """Test search with empty response."""
        mock_response = Mock()
        mock_response.json.return_value = {"responseSet": []}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        adapter = VectaraAdapter(tool_config)
        results = adapter.search("very obscure query")

        assert len(results) == 0

    @patch.dict(os.environ, {"VECTARA_API_KEY": "test_key"})
    @patch("requests.post")
    def test_search_api_error(self, mock_post, tool_config):
        """Test search with API error."""
        mock_post.side_effect = requests.exceptions.RequestException("API Error")

        adapter = VectaraAdapter(tool_config)
        with pytest.raises(requests.exceptions.RequestException):
            adapter.search("test query")

    @patch.dict(os.environ, {"VECTARA_API_KEY": "test_key"})
    @patch("requests.post")
    def test_search_without_summary(self, mock_post, tool_config):
        """Test search response without summary."""
        response = {
            "responseSet": [
                {
                    "response": [
                        {
                            "text": "Result without summary",
                            "score": 0.75,
                            "documentIndex": "doc_1",
                            "metadata": [],
                        }
                    ]
                }
            ]
        }

        mock_response = Mock()
        mock_response.json.return_value = response
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        adapter = VectaraAdapter(tool_config)
        results = adapter.search("test")

        assert len(results) == 1
        assert results[0].text == "Result without summary"
        assert results[0].id == "doc_1"

    @patch.dict(os.environ, {"VECTARA_API_KEY": "test_key"})
    def test_format_as_ref_list(self, tool_config):
        """Test formatting results as reference list."""
        adapter = VectaraAdapter(tool_config)

        # Create test results
        test_results = {
            "success": True,
            "results": [
                RagResult(
                    id="1",
                    text="Test text",
                    score=0.9,
                    source="Test Source",
                    metadata={"key": "value"},
                )
            ],
        }

        ref_list = adapter.format_as_ref_list(test_results)

        assert len(ref_list) == 1
        assert ref_list[0]["text"] == "Test text"
        assert ref_list[0]["source"] == "Test Source"
        assert ref_list[0]["score"] == 0.9
        assert ref_list[0]["metadata"]["key"] == "value"
