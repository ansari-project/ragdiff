"""Data models for RAGDiff v2.0.

This module defines all Pydantic models for the domain-based architecture.
All models include validation and are designed for JSON serialization.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

# ============================================================================
# Core Models
# ============================================================================


class RunStatus(str, Enum):
    """Run execution states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some queries succeeded, some failed


class RetrievedChunk(BaseModel):
    """A single retrieved text chunk with metadata."""

    content: str
    score: float | None = None
    token_count: int | None = None
    metadata: dict[str, Any] = Field(
        default_factory=dict
    )  # source_id, doc_id, chunk_id, etc.


class SearchResult(BaseModel):
    """Result of a search operation from a provider.

    Wraps chunks with additional execution metadata like cost.
    """

    chunks: list[RetrievedChunk]
    cost: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    total_tokens_returned: int | None = None


class Query(BaseModel):
    """A single query with optional reference answer."""

    text: str
    reference: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("text")
    @classmethod
    def validate_text_not_empty(cls, v: str) -> str:
        """Ensure query text is not empty."""
        if not v or not v.strip():
            raise ValueError("Query text cannot be empty")
        return v.strip()


# ============================================================================
# Configuration Models
# ============================================================================


class EvaluatorConfig(BaseModel):
    """LLM evaluator configuration for comparisons."""

    model: str = "claude-3-5-sonnet-20241022"
    temperature: float = 0.0
    prompt_template: str


class Domain(BaseModel):
    """Domain configuration (loaded from domains/<domain>/domain.yaml)."""

    name: str
    description: str = ""
    variables: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict)  # env var names
    evaluator: EvaluatorConfig
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate domain name format."""
        if not v:
            raise ValueError("Domain name cannot be empty")
        if not all(c.isalnum() or c in "-_" for c in v):
            raise ValueError(
                f"Domain name '{v}' must be alphanumeric with hyphens/underscores only"
            )
        return v


class ProviderConfig(BaseModel):
    """System configuration (loaded from domains/<domain>/systems/<name>.yaml)."""

    name: str
    tool: str  # "vectara", "mongodb", "agentset", etc.
    config: dict[str, Any]  # includes top_k, timeout, and tool-specific config
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate provider name format."""
        if not v:
            raise ValueError("Provider name cannot be empty")
        if not all(c.isalnum() or c in "-_" for c in v):
            raise ValueError(
                f"Provider name '{v}' must be alphanumeric with hyphens/underscores only"
            )
        return v


class QuerySet(BaseModel):
    """Query set (loaded from domains/<domain>/query-sets/<name>.{txt,jsonl})."""

    name: str
    domain: str
    queries: list[Query]

    @field_validator("queries")
    @classmethod
    def validate_max_queries(cls, v: list[Query]) -> list[Query]:
        """Enforce maximum query limit."""
        if len(v) > 1000:
            raise ValueError(f"Query set cannot exceed 1000 queries (got {len(v)})")
        if not v:
            raise ValueError("Query set cannot be empty")
        return v

    @field_validator("name", "domain")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate name format."""
        if not v:
            raise ValueError("Name cannot be empty")
        if not all(c.isalnum() or c in "-_" for c in v):
            raise ValueError(
                f"Name '{v}' must be alphanumeric with hyphens/underscores only"
            )
        return v


# ============================================================================
# Run and Result Models
# ============================================================================


class QueryResult(BaseModel):
    """Result for a single query within a run."""

    query: str
    retrieved: list[RetrievedChunk]
    reference: str | None = None
    duration_ms: float
    cost: float | None = None
    total_tokens_returned: int | None = None
    error: str | None = None


class Run(BaseModel):
    """Run execution result (stored as domains/<domain>/runs/YYYY-MM-DD/<id>.json)."""

    id: UUID = Field(default_factory=uuid4)
    label: str | None = (
        None  # Human-readable label (e.g., "vectara-20251026-001") - optional for backward compatibility
    )
    domain: str
    provider: str  # system name
    model_name: str | None = None
    query_set: str  # query set name
    status: RunStatus
    results: list[QueryResult]

    # Snapshots for reproducibility (CRITICAL: keep ${VAR_NAME} placeholders, do NOT resolve secrets)
    provider_config: ProviderConfig
    query_set_snapshot: QuerySet

    # Timing
    started_at: datetime
    completed_at: datetime | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_utc(cls, v: datetime | None) -> datetime | None:
        """Ensure all timestamps are UTC."""
        if v and v.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (UTC)")
        return v


# ============================================================================
# Comparison Models
# ============================================================================


class EvaluationResult(BaseModel):
    """Evaluation result for comparing multiple runs on a single query."""

    query: str
    reference: str | None
    run_results: dict[str, list[RetrievedChunk]]  # system name -> retrieved chunks
    evaluation: dict[str, Any]  # winner, reasoning, scores


class Comparison(BaseModel):
    """Comparison of multiple runs (stored as domains/<domain>/comparisons/YYYY-MM-DD/<id>.json)."""

    id: UUID = Field(default_factory=uuid4)
    label: str  # Human-readable label (e.g., "comparison-20251026-001")
    domain: str
    runs: list[UUID]  # run IDs being compared
    evaluations: list[EvaluationResult]
    evaluator_config: EvaluatorConfig  # Snapshot of evaluator used
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("created_at")
    @classmethod
    def validate_utc(cls, v: datetime) -> datetime:
        """Ensure timestamp is UTC."""
        if v.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (UTC)")
        return v
