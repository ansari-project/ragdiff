"""Data models for RAG comparison harness."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


@dataclass
class RagResult:
    """Normalized result from any RAG system."""

    id: str
    text: str
    score: float
    source: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    latency_ms: Optional[float] = None

    def __post_init__(self):
        """Validate result data."""
        if not self.id:
            raise ValueError("Result ID cannot be empty")
        if not self.text:
            raise ValueError("Result text cannot be empty")
        if not 0 <= self.score <= 1:
            # Normalize scores to 0-1 range if needed
            if self.score > 100:
                self.score = min(self.score / 1000, 1.0)  # Assume out of 1000
            elif self.score > 1:
                self.score = min(self.score / 100, 1.0)  # Assume percentage
            else:
                self.score = max(0, self.score)


class ComparisonOutcome(Enum):
    """Possible outcomes of LLM comparison."""

    GOODMEM_BETTER = "goodmem"
    MAWSUAH_BETTER = "mawsuah"
    TIE = "tie"
    UNCLEAR = "unclear"


@dataclass
class LLMEvaluation:
    """Results from LLM evaluation."""

    llm_model: str  # e.g., "claude-opus-4-1"
    winner: Optional[str] = None  # Tool name that won, or None for tie
    analysis: str = ""  # Analysis text
    quality_scores: Dict[str, int] = field(default_factory=dict)  # Tool -> score (0-10)
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata

    # Legacy fields for backward compatibility
    summary: Optional[str] = None
    confidence: Optional[str] = None  # high, medium, low
    key_differences: List[str] = field(default_factory=list)
    recommendations: Optional[str] = None
    raw_response: Optional[str] = None
    evaluation_time_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "llm_model": self.llm_model,
            "winner": self.winner,
            "analysis": self.analysis,
            "quality_scores": self.quality_scores,
            "metadata": self.metadata,
            "evaluation_time_ms": self.evaluation_time_ms,
        }


@dataclass
class ComparisonResult:
    """Complete comparison result for a query."""

    query: str
    tool_results: Dict[str, List[RagResult]]
    errors: Dict[str, str]
    timestamp: datetime = field(default_factory=datetime.now)
    llm_evaluation: Optional[LLMEvaluation] = None

    # Legacy properties for backward compatibility
    @property
    def goodmem_results(self) -> List[RagResult]:
        """Get Goodmem results for backward compatibility."""
        return self.tool_results.get("goodmem", [])

    @property
    def mawsuah_results(self) -> List[RagResult]:
        """Get Mawsuah results for backward compatibility."""
        return self.tool_results.get("mawsuah", [])

    @property
    def goodmem_error(self) -> Optional[str]:
        """Get Goodmem error for backward compatibility."""
        return self.errors.get("goodmem")

    @property
    def mawsuah_error(self) -> Optional[str]:
        """Get Mawsuah error for backward compatibility."""
        return self.errors.get("mawsuah")

    @property
    def goodmem_latency_ms(self) -> Optional[float]:
        """Get Goodmem latency for backward compatibility."""
        results = self.tool_results.get("goodmem", [])
        return results[0].latency_ms if results else None

    @property
    def mawsuah_latency_ms(self) -> Optional[float]:
        """Get Mawsuah latency for backward compatibility."""
        results = self.tool_results.get("mawsuah", [])
        return results[0].latency_ms if results else None

    def has_errors(self) -> bool:
        """Check if any system had errors."""
        return bool(self.errors)

    def get_result_counts(self) -> Dict[str, int]:
        """Get count of results from each system."""
        return {
            tool_name: len(results) for tool_name, results in self.tool_results.items()
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "query": self.query,
            "timestamp": self.timestamp.isoformat(),
            "tool_results": {
                tool_name: [
                    {
                        "id": r.id,
                        "text": r.text,
                        "score": r.score,
                        "source": r.source,
                        "metadata": r.metadata,
                    }
                    for r in results
                ]
                for tool_name, results in self.tool_results.items()
            },
            "errors": self.errors,
            "llm_evaluation": (
                self.llm_evaluation.to_dict() if self.llm_evaluation else None
            ),
        }


@dataclass
class ToolConfig:
    """Configuration for a RAG tool."""

    name: str
    api_key_env: str
    adapter: Optional[str] = None  # Which adapter class to use (defaults to name)
    options: Optional[Dict[str, Any]] = None  # Custom adapter-specific options
    base_url: Optional[str] = None
    corpus_id: Optional[str] = None
    customer_id: Optional[str] = None
    namespace_id_env: Optional[str] = None  # For Agentset
    timeout: int = 30
    max_retries: int = 3
    default_top_k: int = 5
    space_ids: Optional[List[str]] = None

    def validate(self) -> None:
        """Validate configuration."""
        if not self.name:
            raise ValueError("Tool name is required")
        if not self.api_key_env:
            raise ValueError("API key environment variable name is required")
