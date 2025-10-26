"""Tests for OpenAPI adapter system."""

import pytest
import responses

from ragdiff.adapters.openapi import OpenAPIAdapter
from ragdiff.adapters.openapi_mapping import ResponseMapper, TemplateEngine
from ragdiff.core.errors import AdapterError, ConfigurationError
from ragdiff.core.models import ToolConfig


class TestTemplateEngine:
    """Test TemplateEngine variable substitution."""

    def test_simple_string_substitution(self):
        """Test ${var} substitution in strings."""
        engine = TemplateEngine()
        template = "hello ${name}"
        variables = {"name": "world"}
        result = engine.render(template, variables)
        assert result == "hello world"

    def test_full_variable_preserves_type(self):
        """Test that ${var} alone preserves variable type."""
        engine = TemplateEngine()

        # Integer
        result = engine.render("${count}", {"count": 5})
        assert result == 5
        assert isinstance(result, int)

        # Float
        result = engine.render("${score}", {"score": 0.95})
        assert result == 0.95
        assert isinstance(result, float)

        # Boolean
        result = engine.render("${flag}", {"flag": True})
        assert result is True

    def test_dict_substitution(self):
        """Test variable substitution in dicts."""
        engine = TemplateEngine()
        template = {"query": "${q}", "limit": "${n}"}
        variables = {"q": "test", "n": 10}
        result = engine.render(template, variables)
        assert result == {"query": "test", "limit": 10}

    def test_list_substitution(self):
        """Test variable substitution in lists."""
        engine = TemplateEngine()
        template = ["${a}", "${b}", "static"]
        variables = {"a": "first", "b": "second"}
        result = engine.render(template, variables)
        assert result == ["first", "second", "static"]

    def test_nested_substitution(self):
        """Test variable substitution in nested structures."""
        engine = TemplateEngine()
        template = {
            "outer": {"inner": "${value}"},
            "list": ["${item1}", "${item2}"],
        }
        variables = {"value": "nested", "item1": "a", "item2": "b"}
        result = engine.render(template, variables)
        assert result == {
            "outer": {"inner": "nested"},
            "list": ["a", "b"],
        }

    def test_missing_variable_raises_error(self):
        """Test that missing variables raise ConfigurationError."""
        engine = TemplateEngine()
        with pytest.raises(ConfigurationError, match="not provided"):
            engine.render("${missing}", {})

    def test_primitive_types_pass_through(self):
        """Test that primitive types without variables pass through."""
        engine = TemplateEngine()
        assert engine.render(123, {}) == 123
        assert engine.render(3.14, {}) == 3.14
        assert engine.render(True, {}) is True
        assert engine.render(None, {}) is None


class TestResponseMapper:
    """Test ResponseMapper JMESPath extraction."""

    def test_simple_mapping(self):
        """Test simple field extraction."""
        mapping_config = {
            "results_array": "results",
            "fields": {
                "id": "id",
                "text": "text",
                "score": "score",
            },
        }
        mapper = ResponseMapper(mapping_config)

        response = {
            "results": [
                {"id": "1", "text": "first", "score": 0.9},
                {"id": "2", "text": "second", "score": 0.8},
            ]
        }

        results = mapper.map_results(response)
        assert len(results) == 2
        assert results[0].id == "1"
        assert results[0].text == "first"
        assert results[0].score == 0.9

    def test_nested_path_extraction(self):
        """Test extraction from nested objects."""
        mapping_config = {
            "results_array": "data.results",
            "fields": {
                "id": "doc.id",
                "text": "doc.content.text",
                "score": "ranking.score",
            },
        }
        mapper = ResponseMapper(mapping_config)

        response = {
            "data": {
                "results": [
                    {
                        "doc": {"id": "1", "content": {"text": "nested"}},
                        "ranking": {"score": 0.95},
                    }
                ]
            }
        }

        results = mapper.map_results(response)
        assert len(results) == 1
        assert results[0].id == "1"
        assert results[0].text == "nested"
        assert results[0].score == 0.95

    def test_object_construction(self):
        """Test JMESPath object construction for metadata."""
        mapping_config = {
            "results_array": "results",
            "fields": {
                "id": "id",
                "text": "text",
                "score": "score",
                "metadata": "{author: meta.author, date: meta.date}",
            },
        }
        mapper = ResponseMapper(mapping_config)

        response = {
            "results": [
                {
                    "id": "1",
                    "text": "content",
                    "score": 0.9,
                    "meta": {"author": "John", "date": "2024-01-01"},
                }
            ]
        }

        results = mapper.map_results(response)
        assert results[0].metadata == {"author": "John", "date": "2024-01-01"}

    def test_score_normalization(self):
        """Test score normalization from various ranges."""
        mapping_config = {
            "results_array": "results",
            "fields": {"id": "id", "text": "text", "score": "score"},
        }
        mapper = ResponseMapper(mapping_config)

        # Test different score ranges
        response = {
            "results": [
                {"id": "1", "text": "a", "score": 0.5},  # 0-1: pass through
                {"id": "2", "text": "b", "score": 75},  # 0-100: divide by 100
                {"id": "3", "text": "c", "score": 850},  # 0-1000: divide by 1000
                {"id": "4", "text": "d", "score": -0.5},  # negative: clamp to 0
            ]
        }

        results = mapper.map_results(response)
        assert results[0].score == 0.5
        assert results[1].score == 0.75
        assert results[2].score == 0.85
        assert results[3].score == 0.0

    def test_optional_fields(self):
        """Test that optional fields (source, metadata) can be missing."""
        mapping_config = {
            "results_array": "results",
            "fields": {
                "id": "id",
                "text": "text",
                "score": "score",
                "source": "source",  # Optional, might be missing
            },
        }
        mapper = ResponseMapper(mapping_config)

        response = {
            "results": [
                {"id": "1", "text": "with source", "score": 0.9, "source": "doc1"},
                {"id": "2", "text": "without source", "score": 0.8},
            ]
        }

        results = mapper.map_results(response)
        assert results[0].source == "doc1"
        assert results[1].source is None

    def test_empty_results_array(self):
        """Test handling of empty results array."""
        mapping_config = {
            "results_array": "results",
            "fields": {"id": "id", "text": "text", "score": "score"},
        }
        mapper = ResponseMapper(mapping_config)

        response = {"results": []}
        results = mapper.map_results(response)
        assert results == []

    def test_missing_results_array(self):
        """Test handling when results array path doesn't exist."""
        mapping_config = {
            "results_array": "data.results",
            "fields": {"id": "id", "text": "text", "score": "score"},
        }
        mapper = ResponseMapper(mapping_config)

        response = {"other_field": "value"}
        results = mapper.map_results(response)
        assert results == []

    def test_invalid_jmespath_raises_error(self):
        """Test that invalid JMESPath expressions raise ConfigurationError."""
        with pytest.raises(ConfigurationError, match="Invalid JMESPath"):
            ResponseMapper(
                {
                    "results_array": "results",
                    "fields": {
                        "id": "id",
                        "text": "invalid..syntax",  # Invalid JMESPath
                        "score": "score",
                    },
                }
            )

    def test_missing_required_field_in_mapping_config(self):
        """Test that ResponseMapper can be created even if fields are missing.

        Note: Field validation happens in OpenAPIAdapter.validate_config(),
        not in ResponseMapper constructor. The mapper just uses what's provided.
        """
        # This should NOT raise an error - mapper just stores the config
        mapper = ResponseMapper(
            {
                "results_array": "results",
                "fields": {
                    "id": "id",
                    "text": "text",
                    # Missing 'score' - validation happens at adapter level
                },
            }
        )
        assert mapper is not None


class TestOpenAPIAdapter:
    """Test OpenAPIAdapter end-to-end."""

    def test_adapter_registration(self):
        """Test that OpenAPI adapter is registered."""
        from ragdiff.adapters import list_available_adapters

        adapters = list_available_adapters()
        assert "openapi" in adapters

    def test_valid_config(self):
        """Test adapter initialization with valid config."""
        config = ToolConfig(
            name="test-api",
            api_key_env="TEST_API_KEY",
            options={
                "base_url": "https://api.example.com",
                "endpoint": "/search",
                "method": "POST",
                "auth": {"type": "bearer", "header": "Authorization"},
                "response_mapping": {
                    "results_array": "results",
                    "fields": {"id": "id", "text": "text", "score": "score"},
                },
            },
        )

        credentials = {"TEST_API_KEY": "test-key-123"}
        adapter = OpenAPIAdapter(config, credentials=credentials)
        assert adapter.api_key == "test-key-123"
        assert adapter.base_url == "https://api.example.com"
        assert adapter.endpoint == "/search"
        assert adapter.method == "POST"

    def test_missing_options_raises_error(self):
        """Test that missing options raises ConfigurationError."""
        config = ToolConfig(
            name="test-api",
            api_key_env="TEST_API_KEY",
            # Missing options
        )

        with pytest.raises(ConfigurationError, match="requires 'options'"):
            OpenAPIAdapter(config, credentials={"TEST_API_KEY": "key"})

    def test_missing_required_option_raises_error(self):
        """Test that missing required options raise ConfigurationError."""
        config = ToolConfig(
            name="test-api",
            api_key_env="TEST_API_KEY",
            options={
                "base_url": "https://api.example.com",
                # Missing endpoint, auth, response_mapping
            },
        )

        with pytest.raises(ConfigurationError, match="missing required field"):
            OpenAPIAdapter(config, credentials={"TEST_API_KEY": "key"})

    def test_invalid_auth_type_raises_error(self):
        """Test that invalid auth type raises ConfigurationError."""
        config = ToolConfig(
            name="test-api",
            api_key_env="TEST_API_KEY",
            options={
                "base_url": "https://api.example.com",
                "endpoint": "/search",
                "auth": {"type": "invalid_auth_type"},
                "response_mapping": {
                    "results_array": "results",
                    "fields": {"id": "id", "text": "text", "score": "score"},
                },
            },
        )

        with pytest.raises(ConfigurationError, match="Invalid auth type"):
            OpenAPIAdapter(config, credentials={"TEST_API_KEY": "key"})

    @responses.activate
    def test_search_with_bearer_auth(self):
        """Test search with Bearer token authentication."""
        # Mock API response
        responses.add(
            responses.POST,
            "https://api.example.com/search",
            json={
                "results": [
                    {"id": "1", "text": "result one", "score": 0.95},
                    {"id": "2", "text": "result two", "score": 0.85},
                ]
            },
            status=200,
        )

        config = ToolConfig(
            name="test-api",
            api_key_env="TEST_API_KEY",
            options={
                "base_url": "https://api.example.com",
                "endpoint": "/search",
                "method": "POST",
                "auth": {
                    "type": "bearer",
                    "header": "Authorization",
                    "scheme": "Bearer",
                },
                "request_body": {"query": "${query}", "limit": "${top_k}"},
                "response_mapping": {
                    "results_array": "results",
                    "fields": {"id": "id", "text": "text", "score": "score"},
                },
            },
        )

        adapter = OpenAPIAdapter(config, credentials={"TEST_API_KEY": "test-key"})
        results = adapter.search("test query", top_k=5)

        assert len(results) == 2
        assert results[0].id == "1"
        assert results[0].text == "result one"
        assert results[0].score == 0.95

        # Verify request was made with correct headers
        assert len(responses.calls) == 1
        request = responses.calls[0].request
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.body  # Request body should be present

    @responses.activate
    def test_search_with_api_key_header(self):
        """Test search with API key in header."""
        responses.add(
            responses.POST,
            "https://api.example.com/search",
            json={"results": [{"id": "1", "text": "result", "score": 0.9}]},
            status=200,
        )

        config = ToolConfig(
            name="test-api",
            api_key_env="TEST_API_KEY",
            options={
                "base_url": "https://api.example.com",
                "endpoint": "/search",
                "method": "POST",
                "auth": {"type": "api_key", "header": "X-API-Key"},
                "request_body": {"q": "${query}"},
                "response_mapping": {
                    "results_array": "results",
                    "fields": {"id": "id", "text": "text", "score": "score"},
                },
            },
        )

        adapter = OpenAPIAdapter(config, credentials={"TEST_API_KEY": "my-api-key"})
        results = adapter.search("test", top_k=1)

        assert len(results) == 1
        # Verify API key header
        request = responses.calls[0].request
        assert request.headers["X-API-Key"] == "my-api-key"

    @responses.activate
    def test_search_with_get_request(self):
        """Test search with GET request and query parameters."""
        responses.add(
            responses.GET,
            "https://api.example.com/search",
            json={"items": [{"id": "1", "text": "result", "score": 0.9}]},
            status=200,
        )

        config = ToolConfig(
            name="test-api",
            api_key_env="TEST_API_KEY",
            options={
                "base_url": "https://api.example.com",
                "endpoint": "/search",
                "method": "GET",
                "auth": {"type": "bearer", "header": "Authorization"},
                "request_params": {"q": "${query}", "limit": "${top_k}"},
                "response_mapping": {
                    "results_array": "items",
                    "fields": {"id": "id", "text": "text", "score": "score"},
                },
            },
        )

        adapter = OpenAPIAdapter(config, credentials={"TEST_API_KEY": "key"})
        results = adapter.search("test", top_k=5)

        assert len(results) == 1
        # Verify query parameters
        request = responses.calls[0].request
        assert "q=test" in request.url
        assert "limit=5" in request.url

    @responses.activate
    def test_http_error_raises_adapter_error(self):
        """Test that HTTP errors raise AdapterError."""
        responses.add(
            responses.POST,
            "https://api.example.com/search",
            json={"error": "Not Found"},
            status=404,
        )

        config = ToolConfig(
            name="test-api",
            api_key_env="TEST_API_KEY",
            options={
                "base_url": "https://api.example.com",
                "endpoint": "/search",
                "auth": {"type": "bearer", "header": "Authorization"},
                "request_body": {"query": "${query}"},
                "response_mapping": {
                    "results_array": "results",
                    "fields": {"id": "id", "text": "text", "score": "score"},
                },
            },
        )

        adapter = OpenAPIAdapter(config, credentials={"TEST_API_KEY": "key"})

        with pytest.raises(AdapterError, match="HTTP 404"):
            adapter.search("test")

    @responses.activate
    def test_results_sorted_by_score(self):
        """Test that results are sorted by score descending."""
        responses.add(
            responses.POST,
            "https://api.example.com/search",
            json={
                "results": [
                    {"id": "1", "text": "low", "score": 0.5},
                    {"id": "2", "text": "high", "score": 0.95},
                    {"id": "3", "text": "medium", "score": 0.75},
                ]
            },
            status=200,
        )

        config = ToolConfig(
            name="test-api",
            api_key_env="TEST_API_KEY",
            options={
                "base_url": "https://api.example.com",
                "endpoint": "/search",
                "auth": {"type": "bearer", "header": "Authorization"},
                "request_body": {"query": "${query}"},
                "response_mapping": {
                    "results_array": "results",
                    "fields": {"id": "id", "text": "text", "score": "score"},
                },
            },
        )

        adapter = OpenAPIAdapter(config, credentials={"TEST_API_KEY": "key"})
        results = adapter.search("test", top_k=10)

        # Should be sorted by score descending
        assert results[0].score == 0.95
        assert results[1].score == 0.75
        assert results[2].score == 0.5

    @responses.activate
    def test_top_k_limit(self):
        """Test that top_k limits the number of results."""
        responses.add(
            responses.POST,
            "https://api.example.com/search",
            json={
                "results": [
                    {"id": str(i), "text": f"result {i}", "score": 1.0 - i * 0.1}
                    for i in range(10)
                ]
            },
            status=200,
        )

        config = ToolConfig(
            name="test-api",
            api_key_env="TEST_API_KEY",
            options={
                "base_url": "https://api.example.com",
                "endpoint": "/search",
                "auth": {"type": "bearer", "header": "Authorization"},
                "request_body": {"query": "${query}"},
                "response_mapping": {
                    "results_array": "results",
                    "fields": {"id": "id", "text": "text", "score": "score"},
                },
            },
        )

        adapter = OpenAPIAdapter(config, credentials={"TEST_API_KEY": "key"})
        results = adapter.search("test", top_k=3)

        # Should only return top 3 results
        assert len(results) == 3

    def test_get_options_schema(self):
        """Test that options schema is provided."""
        config = ToolConfig(
            name="test-api",
            api_key_env="TEST_API_KEY",
            options={
                "base_url": "https://api.example.com",
                "endpoint": "/search",
                "auth": {"type": "bearer", "header": "Authorization"},
                "response_mapping": {
                    "results_array": "results",
                    "fields": {"id": "id", "text": "text", "score": "score"},
                },
            },
        )

        adapter = OpenAPIAdapter(config, credentials={"TEST_API_KEY": "key"})
        schema = adapter.get_options_schema()

        assert schema["type"] == "object"
        assert "base_url" in schema["properties"]
        assert "endpoint" in schema["properties"]
        assert "response_mapping" in schema["properties"]
