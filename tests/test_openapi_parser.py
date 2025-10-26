"""Tests for OpenAPI specification parser."""

import json
from pathlib import Path

import pytest
import responses

from ragdiff.core.errors import ConfigurationError
from ragdiff.openapi import AuthScheme, EndpointInfo, OpenAPIInfo, OpenAPISpec


# Sample OpenAPI 3.0 spec for testing
SAMPLE_OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {
        "title": "Test API",
        "version": "1.0.0",
        "description": "A test API for unit testing",
    },
    "servers": [{"url": "https://api.example.com", "description": "Production server"}],
    "paths": {
        "/search": {
            "post": {
                "summary": "Search for documents",
                "description": "Full-text search across documents",
                "operationId": "searchDocuments",
                "tags": ["search"],
                "parameters": [],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string"},
                                    "limit": {"type": "integer"},
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "results": {
                                            "type": "array",
                                            "items": {"type": "object"},
                                        }
                                    },
                                }
                            }
                        },
                    }
                },
            }
        },
        "/users/{userId}": {
            "get": {
                "summary": "Get user by ID",
                "operationId": "getUserById",
                "tags": ["users"],
                "parameters": [
                    {
                        "name": "userId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "User found",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"id": {"type": "string"}},
                                }
                            }
                        },
                    }
                },
            }
        },
    },
    "components": {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT bearer token authentication",
            },
            "apiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key in header",
            },
        }
    },
}


class TestOpenAPIInfo:
    """Test OpenAPIInfo model."""

    def test_create_info(self):
        """Test creating OpenAPIInfo."""
        info = OpenAPIInfo(
            title="Test API",
            version="1.0.0",
            description="Test description",
            openapi_version="3.0.0",
        )

        assert info.title == "Test API"
        assert info.version == "1.0.0"
        assert info.description == "Test description"
        assert str(info) == "Test API v1.0.0 (OpenAPI 3.0.0)"

    def test_get_base_url(self):
        """Test getting base URL from servers."""
        info = OpenAPIInfo(
            title="Test API",
            version="1.0.0",
            servers=[{"url": "https://api.example.com"}],
        )

        assert info.get_base_url() == "https://api.example.com"

    def test_get_base_url_no_servers(self):
        """Test getting base URL when no servers defined."""
        info = OpenAPIInfo(title="Test API", version="1.0.0")
        assert info.get_base_url() is None


class TestEndpointInfo:
    """Test EndpointInfo model."""

    def test_create_endpoint(self):
        """Test creating EndpointInfo."""
        endpoint = EndpointInfo(
            path="/search",
            method="POST",
            summary="Search endpoint",
            description="Full-text search",
            operation_id="search",
        )

        assert endpoint.path == "/search"
        assert endpoint.method == "POST"
        assert endpoint.summary == "Search endpoint"
        assert str(endpoint) == "POST /search - Search endpoint"

    def test_endpoint_without_summary(self):
        """Test endpoint string representation without summary."""
        endpoint = EndpointInfo(path="/users", method="GET")
        assert str(endpoint) == "GET /users"


class TestAuthScheme:
    """Test AuthScheme model."""

    def test_bearer_auth(self):
        """Test Bearer authentication scheme."""
        auth = AuthScheme(
            name="bearerAuth",
            type="http",
            scheme="bearer",
            bearer_format="JWT",
        )

        assert auth.name == "bearerAuth"
        assert auth.type == "http"
        assert auth.scheme == "bearer"
        assert str(auth) == "bearerAuth: HTTP bearer"

    def test_api_key_auth(self):
        """Test API key authentication scheme."""
        auth = AuthScheme(
            name="apiKeyAuth",
            type="apiKey",
            location="header",
            parameter_name="X-API-Key",
        )

        assert auth.type == "apiKey"
        assert auth.location == "header"
        assert auth.parameter_name == "X-API-Key"
        assert str(auth) == "apiKeyAuth: API Key in header (X-API-Key)"


class TestOpenAPISpec:
    """Test OpenAPISpec parser."""

    def test_create_from_dict(self):
        """Test creating OpenAPISpec from dictionary."""
        spec = OpenAPISpec(SAMPLE_OPENAPI_SPEC)
        assert spec.openapi_version == "3.0.0"

    def test_unsupported_version_raises_error(self):
        """Test that unsupported OpenAPI versions raise error."""
        spec_dict = {"openapi": "2.0.0", "info": {"title": "Test", "version": "1.0.0"}}

        with pytest.raises(ConfigurationError, match="Unsupported OpenAPI version"):
            OpenAPISpec(spec_dict)

    def test_get_info(self):
        """Test extracting API info."""
        spec = OpenAPISpec(SAMPLE_OPENAPI_SPEC)
        info = spec.get_info()

        assert info.title == "Test API"
        assert info.version == "1.0.0"
        assert info.description == "A test API for unit testing"
        assert info.openapi_version == "3.0.0"
        assert len(info.servers) == 1
        assert info.servers[0]["url"] == "https://api.example.com"

    def test_get_endpoints(self):
        """Test extracting all endpoints."""
        spec = OpenAPISpec(SAMPLE_OPENAPI_SPEC)
        endpoints = spec.get_endpoints()

        assert len(endpoints) == 2

        # Find search endpoint
        search_ep = next(e for e in endpoints if e.path == "/search")
        assert search_ep.method == "POST"
        assert search_ep.summary == "Search for documents"
        assert search_ep.operation_id == "searchDocuments"
        assert "search" in search_ep.tags
        assert search_ep.request_body_schema is not None
        assert search_ep.response_schema is not None

        # Find users endpoint
        users_ep = next(e for e in endpoints if e.path == "/users/{userId}")
        assert users_ep.method == "GET"
        assert users_ep.operation_id == "getUserById"
        assert len(users_ep.parameters) == 1
        assert users_ep.parameters[0]["name"] == "userId"

    def test_get_specific_endpoint(self):
        """Test getting a specific endpoint by path and method."""
        spec = OpenAPISpec(SAMPLE_OPENAPI_SPEC)

        endpoint = spec.get_endpoint("/search", "POST")
        assert endpoint is not None
        assert endpoint.path == "/search"
        assert endpoint.method == "POST"
        assert endpoint.summary == "Search for documents"

    def test_get_specific_endpoint_case_insensitive(self):
        """Test that method is case insensitive."""
        spec = OpenAPISpec(SAMPLE_OPENAPI_SPEC)

        endpoint = spec.get_endpoint("/search", "post")
        assert endpoint is not None
        assert endpoint.method == "POST"

    def test_get_nonexistent_endpoint(self):
        """Test getting endpoint that doesn't exist."""
        spec = OpenAPISpec(SAMPLE_OPENAPI_SPEC)

        endpoint = spec.get_endpoint("/nonexistent", "GET")
        assert endpoint is None

    def test_get_auth_schemes(self):
        """Test extracting authentication schemes."""
        spec = OpenAPISpec(SAMPLE_OPENAPI_SPEC)
        auth_schemes = spec.get_auth_schemes()

        assert len(auth_schemes) == 2

        # Find bearer auth
        bearer = next(a for a in auth_schemes if a.name == "bearerAuth")
        assert bearer.type == "http"
        assert bearer.scheme == "bearer"
        assert bearer.bearer_format == "JWT"

        # Find API key auth
        api_key = next(a for a in auth_schemes if a.name == "apiKeyAuth")
        assert api_key.type == "apiKey"
        assert api_key.location == "header"
        assert api_key.parameter_name == "X-API-Key"

    @responses.activate
    def test_from_url_json(self):
        """Test loading spec from URL (JSON format)."""
        responses.add(
            responses.GET,
            "https://api.example.com/openapi.json",
            json=SAMPLE_OPENAPI_SPEC,
            status=200,
            content_type="application/json",
        )

        spec = OpenAPISpec.from_url("https://api.example.com/openapi.json")
        assert spec.openapi_version == "3.0.0"

        info = spec.get_info()
        assert info.title == "Test API"

    @responses.activate
    def test_from_url_yaml(self):
        """Test loading spec from URL (YAML format)."""
        import yaml

        yaml_content = yaml.dump(SAMPLE_OPENAPI_SPEC)

        responses.add(
            responses.GET,
            "https://api.example.com/openapi.yaml",
            body=yaml_content,
            status=200,
            content_type="application/x-yaml",
        )

        spec = OpenAPISpec.from_url("https://api.example.com/openapi.yaml")
        assert spec.openapi_version == "3.0.0"

    @responses.activate
    def test_from_url_404_error(self):
        """Test handling 404 error when fetching spec."""
        responses.add(
            responses.GET,
            "https://api.example.com/openapi.json",
            status=404,
        )

        with pytest.raises(ConfigurationError, match="Failed to fetch"):
            OpenAPISpec.from_url("https://api.example.com/openapi.json")

    @responses.activate
    def test_from_url_invalid_json(self):
        """Test handling invalid JSON response."""
        responses.add(
            responses.GET,
            "https://api.example.com/openapi.json",
            body="invalid json{{{",
            status=200,
            content_type="application/json",
        )

        with pytest.raises(ConfigurationError, match="Failed to parse"):
            OpenAPISpec.from_url("https://api.example.com/openapi.json")

    def test_from_file_json(self, tmp_path):
        """Test loading spec from JSON file."""
        spec_file = tmp_path / "openapi.json"
        spec_file.write_text(json.dumps(SAMPLE_OPENAPI_SPEC))

        spec = OpenAPISpec.from_file(spec_file)
        assert spec.openapi_version == "3.0.0"

        info = spec.get_info()
        assert info.title == "Test API"

    def test_from_file_yaml(self, tmp_path):
        """Test loading spec from YAML file."""
        import yaml

        spec_file = tmp_path / "openapi.yaml"
        spec_file.write_text(yaml.dump(SAMPLE_OPENAPI_SPEC))

        spec = OpenAPISpec.from_file(spec_file)
        assert spec.openapi_version == "3.0.0"

    def test_from_file_not_found(self):
        """Test handling missing file."""
        with pytest.raises(ConfigurationError, match="not found"):
            OpenAPISpec.from_file("/nonexistent/openapi.json")

    def test_from_file_invalid_format(self, tmp_path):
        """Test handling invalid file format."""
        spec_file = tmp_path / "openapi.json"
        spec_file.write_text("invalid json{{{")

        with pytest.raises(ConfigurationError, match="Failed to parse"):
            OpenAPISpec.from_file(spec_file)

    def test_extract_request_body_schema(self):
        """Test extracting request body schema."""
        spec = OpenAPISpec(SAMPLE_OPENAPI_SPEC)
        endpoint = spec.get_endpoint("/search", "POST")

        assert endpoint.request_body_schema is not None
        assert endpoint.request_body_schema["type"] == "object"
        assert "query" in endpoint.request_body_schema["properties"]
        assert "limit" in endpoint.request_body_schema["properties"]

    def test_extract_response_schema(self):
        """Test extracting response schema."""
        spec = OpenAPISpec(SAMPLE_OPENAPI_SPEC)
        endpoint = spec.get_endpoint("/search", "POST")

        assert endpoint.response_schema is not None
        assert endpoint.response_schema["type"] == "object"
        assert "results" in endpoint.response_schema["properties"]

    def test_endpoint_without_request_body(self):
        """Test endpoint without request body (GET request)."""
        spec = OpenAPISpec(SAMPLE_OPENAPI_SPEC)
        endpoint = spec.get_endpoint("/users/{userId}", "GET")

        assert endpoint.request_body_schema is None
        assert endpoint.response_schema is not None
