"""Exception hierarchy for RAGDiff v2.0.

This module defines a clear taxonomy of errors to help users and developers
understand what went wrong and how to fix it.

All custom exceptions inherit from RagDiffError, making it easy to catch
all RAGDiff-specific errors in a single except clause.
"""


class RagDiffError(Exception):
    """Base exception for all RAGDiff errors.

    All custom exceptions in RAGDiff inherit from this base class,
    making it easy to catch all RAGDiff-specific errors.

    Example:
        try:
            ragdiff.execute_run(...)
        except RagDiffError as e:
            print(f"RAGDiff error: {e}")
    """

    pass


class ConfigError(RagDiffError):
    """Configuration-related errors.

    Raised when:
    - Config files are missing or cannot be read
    - YAML syntax is invalid
    - Required fields are missing
    - Field values are invalid
    - Environment variables are missing
    - Domain/system/query-set names are invalid

    Examples:
        - "Domain 'tafsir' not found at domains/tafsir/domain.yaml"
        - "Missing required field: evaluator.model in domain.yaml"
        - "Environment variable VECTARA_API_KEY not set"
        - "Invalid domain name 'my/domain': cannot contain slashes"
        - "Query set exceeds 1000 query limit (got 1500)"
    """

    pass


class RunError(RagDiffError):
    """Run execution errors.

    Raised when:
    - System initialization fails
    - System search() method raises an error
    - Query execution times out
    - File I/O errors during run storage
    - Run state transitions are invalid

    Examples:
        - "System 'vectara-mmr' initialization failed: Invalid API key"
        - "Query timeout after 30s: What is Islamic inheritance law?"
        - "Failed to save run to domains/tafsir/runs/2025-10-25/abc123.json"
        - "Cannot transition run from 'completed' to 'running'"

    Note: Per-query errors are captured in QueryResult.error, not raised as RunError.
    """

    pass


class ComparisonError(RagDiffError):
    """Comparison and LLM evaluation errors.

    Raised when:
    - Runs are from different domains
    - LLM API authentication fails
    - LLM evaluation exhausts all retries
    - Comparison file storage fails
    - Run loading fails during comparison

    Examples:
        - "Cannot compare runs from different domains: tafsir vs legal"
        - "LLM API authentication failed: Invalid ANTHROPIC_API_KEY"
        - "LLM evaluation failed after 3 retries: Rate limit exceeded"
        - "Run not found: abc123 in domain tafsir"

    Note: Per-query evaluation errors are captured in EvaluationResult, not raised.
    """

    pass


class ValidationError(RagDiffError):
    """Input validation errors.

    Raised when:
    - Pydantic model validation fails
    - Data doesn't match expected schema
    - Required fields are missing
    - Data types are incorrect
    - Constraints are violated

    Examples:
        - "Query text cannot be empty"
        - "Query set cannot exceed 1000 queries (got 1500)"
        - "Timestamp must be timezone-aware (UTC)"
        - "Domain name must be alphanumeric with hyphens/underscores only"

    Note: This is typically raised by Pydantic validators.
    """

    pass


# ============================================================================
# Backward Compatibility Aliases (v1.x)
# ============================================================================
# These aliases allow v1.x adapters to continue working during the v2.0 migration.
# They will be removed when v1.x code is fully deprecated.

AdapterError = RunError  # v1.x: Adapter-specific errors
ConfigurationError = ConfigError  # v1.x: Configuration errors
AdapterRegistryError = ConfigError  # v1.x: Adapter registry errors
EvaluationError = ComparisonError  # v1.x: Evaluation errors
