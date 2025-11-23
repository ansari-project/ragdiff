import os
from unittest.mock import MagicMock, patch

import pytest

from ragdiff.core.errors import ConfigError, RunError
from ragdiff.core.models import ProviderConfig
from ragdiff.providers import create_provider, is_tool_registered


class TestGoogleFileSearchProvider:
    """Tests for GoogleFileSearchProvider."""

    def test_google_file_search_registered(self):
        """Test that Google File Search tool is registered."""
        assert is_tool_registered("google_file_search")

    def test_missing_api_key(self):
        """Test requires api_key."""
        with pytest.raises(ConfigError, match="Missing required field: api_key"):
            config = ProviderConfig(
                name="google-test",
                tool="google_file_search",
                config={"store_name": "projects/..."},
            )
            # Ensure env var is not set
            with patch.dict(os.environ, {}, clear=True):
                create_provider(config)

    def test_missing_store_name(self):
        """Test requires store_name."""
        with pytest.raises(ConfigError, match="Missing required field: store_name"):
            config = ProviderConfig(
                name="google-test",
                tool="google_file_search",
                config={"api_key": "test"},
            )
            create_provider(config)

    @patch("ragdiff.providers.google_file_search.genai.Client")
    def test_initialization_success(self, mock_client):
        """Test initialization success."""
        config = ProviderConfig(
            name="google-test",
            tool="google_file_search",
            config={
                "api_key": "test_key",
                "store_name": "projects/123/locations/us-central1/collections/default_collection/dataStores/test-store",
                "model": "gemini-1.5-pro",
            },
        )

        provider = create_provider(config)
        assert provider.api_key == "test_key"
        assert (
            provider.store_name
            == "projects/123/locations/us-central1/collections/default_collection/dataStores/test-store"
        )
        assert provider.model_name == "gemini-1.5-pro"
        mock_client.assert_called_with(api_key="test_key")

    @patch("ragdiff.providers.google_file_search.genai.Client")
    def test_search_success(self, mock_client_cls):
        """Test search success with mocked response."""
        # Setup mock client and response
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "This is the answer based on the file."

        # Mock grounding metadata
        mock_candidate = MagicMock()
        mock_grounding_metadata = MagicMock()

        # Create a mock chunk
        mock_chunk = MagicMock()
        mock_chunk.retrieved_context.uri = "gs://bucket/file.pdf"
        mock_chunk.retrieved_context.title = "File Title"
        mock_chunk.retrieved_context.text = "This is the answer based on the file."

        mock_grounding_metadata.grounding_chunks = [mock_chunk]
        mock_candidate.grounding_metadata = mock_grounding_metadata

        mock_response.candidates = [mock_candidate]
        mock_client.models.generate_content.return_value = mock_response

        # Create provider
        config = ProviderConfig(
            name="google-test",
            tool="google_file_search",
            config={"api_key": "test_key", "store_name": "test-store"},
        )
        provider = create_provider(config)

        # Execute search
        result = provider.search("test query")
        chunks = result.chunks

        # Verify results
        assert len(chunks) == 1
        assert chunks[0].content == "This is the answer based on the file."
        assert chunks[0].metadata["source"] == "File Title"
        assert "File Title (gs://bucket/file.pdf)" in chunks[0].metadata["citations"]

        # Verify API call
        mock_client.models.generate_content.assert_called_once()
        call_args = mock_client.models.generate_content.call_args
        assert call_args.kwargs["model"] == "gemini-1.5-flash-lite"
        assert call_args.kwargs["contents"] == "Question: test query"

        # Verify tool config
        tools = call_args.kwargs["config"].tools
        assert len(tools) == 1
        assert tools[0].file_search.file_search_store_names == ["test-store"]

    @patch("ragdiff.providers.google_file_search.genai.Client")
    def test_search_failure(self, mock_client_cls):
        """Test search failure handling."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.side_effect = Exception("API Error")

        config = ProviderConfig(
            name="google-test",
            tool="google_file_search",
            config={"api_key": "test_key", "store_name": "test-store"},
        )
        provider = create_provider(config)

        with pytest.raises(RunError, match="Google File Search failed"):
            provider.search("test query")
