"""Data models for RAG comparison harness."""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from datetime import datetime
from enum import Enum


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
    """Results from Claude 4.1 Opus evaluation."""

    summary: str
    winner: ComparisonOutcome
    confidence: str  # high, medium, low
    key_differences: List[str]
    recommendations: str
    raw_response: Optional[str] = None
    evaluation_time_ms: Optional[float] = None

    strengths_goodmem: List[str] = field(default_factory=list)
    strengths_mawsuah: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "summary": self.summary,
            "winner": self.winner.value,
            "confidence": self.confidence,
            "key_differences": self.key_differences,
            "recommendations": self.recommendations,
            "strengths_goodmem": self.strengths_goodmem,
            "strengths_mawsuah": self.strengths_mawsuah,
            "evaluation_time_ms": self.evaluation_time_ms
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
            tool_name: len(results)
            for tool_name, results in self.tool_results.items()
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
                        "metadata": r.metadata
                    }
                    for r in results
                ]
                for tool_name, results in self.tool_results.items()
            },
            "errors": self.errors,
            "llm_evaluation": self.llm_evaluation.to_dict() if self.llm_evaluation else None
        }


@dataclass
class ToolConfig:
    """Configuration for a RAG tool."""

    name: str
    api_key_env: str
    base_url: Optional[str] = None
    corpus_id: Optional[str] = None
    customer_id: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    default_top_k: int = 5

    def validate(self) -> None:
        """Validate configuration."""
        if not self.name:
            raise ValueError("Tool name is required")
        if not self.api_key_env:
            raise ValueError("API key environment variable name is required")