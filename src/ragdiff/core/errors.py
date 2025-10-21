"""Exception hierarchy for RAGDiff.

This module defines a clear taxonomy of errors to help users and developers
understand what went wrong and how to fix it.
"""


class RagDiffError(Exception):
    """Base exception for all RAGDiff errors.

    All custom exceptions in RAGDiff inherit from this base class,
    making it easy to catch all RAGDiff-specific errors.
    """

    pass


class ConfigurationError(RagDiffError):
    """Invalid configuration detected.

    Raised when:
    - Required configuration fields are missing
    - Configuration values are invalid (wrong type, out of range, etc.)
    - Environment variables required by config are missing
    - Config file cannot be parsed

    Examples:
        - Missing required field: "config.tools.vectara.corpus_id is required"
        - Invalid value: "top_k must be positive integer, got -5"
        - Missing env var: "VECTARA_API_KEY environment variable not set"
    """

    pass


class AdapterError(RagDiffError):
    """Error from RAG system adapter.

    Raised when:
    - Network request to RAG system fails
    - Authentication/authorization fails
    - RAG system returns an error
    - Response cannot be parsed
    - Timeout occurs

    Examples:
        - Network error: "Connection timeout to Vectara API"
        - Auth error: "Invalid API key for Goodmem"
        - Parse error: "Unable to parse Agentset response: invalid JSON"

    Note: This is for errors from the RAG system itself, not configuration issues.
    """

    pass


class AdapterRegistryError(RagDiffError):
    """Error in adapter registration or discovery.

    Raised when:
    - Adapter with duplicate name is registered
    - Requested adapter not found in registry
    - Adapter API version incompatible with registry

    Examples:
        - Duplicate: "Adapter 'vectara' already registered"
        - Not found: "No adapter found with name 'unknown_tool'"
        - Version mismatch: "Adapter requires API v2.0.0, registry supports v1.0.0"
    """

    pass


class ValidationError(RagDiffError):
    """Data validation failed.

    Raised when:
    - Input data doesn't match expected schema
    - Required fields are missing from data
    - Data types are incorrect

    Examples:
        - Schema mismatch: "RagResult missing required field 'id'"
        - Type error: "Expected str for query, got int"
    """

    pass


class EvaluationError(RagDiffError):
    """Error during LLM evaluation.

    Raised when:
    - LLM API request fails
    - LLM response cannot be parsed
    - Evaluation prompt is invalid

    Examples:
        - API error: "Claude API returned 429 (rate limit)"
        - Parse error: "Could not extract quality scores from LLM response"
    """

    pass
