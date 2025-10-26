"""OpenAPI specification parsing and analysis.

This package provides tools for fetching, parsing, and analyzing OpenAPI
specifications to automatically generate adapter configurations.
"""

from .models import AuthScheme, EndpointInfo, OpenAPIInfo
from .parser import OpenAPISpec

__all__ = [
    "OpenAPISpec",
    "EndpointInfo",
    "AuthScheme",
    "OpenAPIInfo",
]
