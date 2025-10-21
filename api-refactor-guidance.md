# RAGDiff API Refactoring Guidance

## Purpose

This document provides guidance for refactoring RAGDiff from a CLI-only tool into a library with a stable programmatic API, while maintaining CLI backwards compatibility.

**Target Audience**: RAGDiff maintainers implementing the library refactoring
**Reference**: RAGDiff Web UI Plan Phase 2 (codev/plans/0001-ragdiff-web-ui.md)

---

## Goals

1. **Create stable `ragdiff.api` module** for programmatic access
2. **Freeze adapter interface** via ABCs with explicit versioning
3. **Ensure deterministic behavior** for background workers
4. **Maintain CLI backwards compatibility** (no breaking changes to existing users)
5. **Enable library usage** for FastAPI backend and other integrations
6. **Publish to PyPI** (or support git dependency during development)

---

## Current State Analysis

### Strengths (Already Well-Architected)
- ✅ Core logic separated from CLI (models, adapters, comparison, evaluation)
- ✅ Clean adapter pattern for RAG tools
- ✅ Excellent test coverage (90+)
- ✅ Pure dataclasses with no CLI dependencies

### What Needs Refactoring
- ❌ No stable public API for library usage
- ❌ Adapter interface not frozen (risk of breaking changes)
- ❌ Some global state or non-deterministic behavior
- ❌ CLI and library not clearly separated
- ❌ No semantic versioning for breaking changes

---

## Refactoring Requirements

### 1. Create `ragdiff.api` Module

**Location**: `src/ragdiff/api/__init__.py`

**Public Interface** (stable, versioned):

```python
"""
Stable programmatic API for RAGDiff library.
Version: 1.0.0

This module provides the public interface for web applications and integrations.
Breaking changes will follow semantic versioning.
"""

from typing import List, Dict, Any, Optional, Callable
from ragdiff.core.models import ComparisonResult, RagResult, LLMEvaluation
from ragdiff.core.config import Config, ToolConfig

__version__ = "1.0.0"
__all__ = [
    "run_single_query",
    "run_batch_queries",
    "create_comparison",
    "evaluate_with_llm",
    "get_available_adapters",
    "validate_config",
]

def run_single_query(
    config: ToolConfig,
    query: str,
    top_k: int = 5,
    timeout: int = 30,
) -> RagResult:
    """
    Execute a single query against a RAG system.

    Args:
        config: RAG tool configuration (parsed from YAML or constructed programmatically)
        query: Query string
        top_k: Number of documents to retrieve (default: 5)
        timeout: Request timeout in seconds (default: 30)

    Returns:
        RagResult with documents, scores, latency, and metadata

    Raises:
        ConfigurationError: Invalid configuration
        AdapterError: RAG system error (network, auth, etc.)
        TimeoutError: Request timeout exceeded

    Example:
        >>> from ragdiff.api import run_single_query
        >>> from ragdiff.core.config import ToolConfig
        >>>
        >>> config = ToolConfig(
        ...     adapter="vectara",
        ...     api_key_env="VECTARA_API_KEY",
        ...     corpus_id="123"
        ... )
        >>> result = run_single_query(config, "What is RAG?", top_k=5)
        >>> print(f"Found {len(result.documents)} documents")
    """
    pass

def run_batch_queries(
    config: ToolConfig,
    queries: List[str],
    top_k: int = 5,
    parallel: bool = True,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> List[RagResult]:
    """
    Execute multiple queries against a RAG system.

    Args:
        config: RAG tool configuration
        queries: List of query strings (up to 1000 recommended)
        top_k: Number of documents to retrieve per query (default: 5)
        parallel: Execute queries in parallel (default: True)
        progress_callback: Optional callback(completed, total) for progress updates

    Returns:
        List of RagResult, one per query (same order as input)

    Raises:
        ConfigurationError: Invalid configuration
        AdapterError: RAG system error
        ValueError: Too many queries (>1000)

    Example:
        >>> queries = ["What is RAG?", "How does retrieval work?"]
        >>> results = run_batch_queries(
        ...     config,
        ...     queries,
        ...     progress_callback=lambda done, total: print(f"{done}/{total}")
        ... )
        >>> for q, r in zip(queries, results):
        ...     print(f"{q}: {len(r.documents)} docs")
    """
    pass

def create_comparison(
    results: List[RagResult],
    llm_evaluate: bool = False,
    llm_model: str = "claude-sonnet-4-20250514",
    llm_api_key: Optional[str] = None,
) -> ComparisonResult:
    """
    Compare multiple RAG results (typically from different systems or configs).

    Args:
        results: List of RagResult to compare (2+ required, must have same query)
        llm_evaluate: Enable LLM-based quality evaluation (default: False)
        llm_model: Claude model to use for evaluation (default: claude-sonnet-4-20250514)
        llm_api_key: Optional Anthropic API key (defaults to ANTHROPIC_API_KEY env var)

    Returns:
        ComparisonResult with side-by-side comparison and optional LLM evaluation

    Raises:
        ValueError: Less than 2 results or mismatched queries
        LLMEvaluationError: LLM evaluation failed

    Example:
        >>> vectara_result = run_single_query(vectara_config, "What is RAG?")
        >>> goodmem_result = run_single_query(goodmem_config, "What is RAG?")
        >>>
        >>> comparison = create_comparison(
        ...     [vectara_result, goodmem_result],
        ...     llm_evaluate=True
        ... )
        >>> print(f"Winner: {comparison.llm_evaluation.winner}")
    """
    pass

def evaluate_with_llm(
    results: List[RagResult],
    model: str = "claude-sonnet-4-20250514",
    api_key: Optional[str] = None,
) -> LLMEvaluation:
    """
    Evaluate RAG results using Claude LLM on 5 dimensions:
    - Relevance
    - Completeness
    - Accuracy
    - Coherence
    - Source Quality

    Args:
        results: List of RagResult to evaluate (must have same query)
        model: Claude model to use (default: claude-sonnet-4-20250514)
        api_key: Optional Anthropic API key (defaults to ANTHROPIC_API_KEY env var)

    Returns:
        LLMEvaluation with scores, winner, and detailed analysis

    Raises:
        ValueError: Results have mismatched queries
        LLMEvaluationError: LLM API error

    Example:
        >>> results = [vectara_result, goodmem_result]
        >>> eval = evaluate_with_llm(results)
        >>> print(f"Scores: {eval.quality_scores}")
        >>> print(f"Analysis: {eval.analysis}")
    """
    pass

def get_available_adapters() -> List[Dict[str, Any]]:
    """
    Get list of available RAG adapters with schemas.

    Returns:
        List of adapter descriptors:
        [
            {
                "name": "vectara",
                "version": "1.0.0",
                "required_env_vars": ["VECTARA_API_KEY"],
                "options_schema": {
                    "type": "object",
                    "properties": {
                        "corpus_id": {"type": "string", "required": True},
                        "namespace_id": {"type": "string"},
                        ...
                    }
                }
            },
            ...
        ]

    Example:
        >>> adapters = get_available_adapters()
        >>> for adapter in adapters:
        ...     print(f"{adapter['name']} v{adapter['version']}")
    """
    pass

def validate_config(config_yaml: str, adapter: str) -> Dict[str, Any]:
    """
    Validate RAG configuration YAML without executing.

    Args:
        config_yaml: YAML configuration string
        adapter: Adapter name to validate against ("vectara", "goodmem", "agentset")

    Returns:
        {
            "valid": bool,
            "errors": List[str],  # Empty if valid
            "parsed": Dict[str, Any]  # Parsed config if valid, None if invalid
        }

    Example:
        >>> yaml_config = '''
        ... adapter: vectara
        ... api_key_env: VECTARA_API_KEY
        ... corpus_id: "123"
        ... '''
        >>> result = validate_config(yaml_config, "vectara")
        >>> if result["valid"]:
        ...     print("Config is valid!")
        ... else:
        ...     print(f"Errors: {result['errors']}")
    """
    pass
```

---

### 2. Freeze Adapter Interface via ABCs

**Location**: `src/ragdiff/adapters/base.py`

**Requirements**:
- Define abstract base class with versioning
- All adapters must inherit from ABC
- Breaking changes require new version (v2, v3, etc.)

```python
# src/ragdiff/adapters/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from ragdiff.core.models import RagResult

class RagAdapter(ABC):
    """
    Base adapter interface for RAG systems.

    This interface follows semantic versioning. Breaking changes will be
    communicated via ADAPTER_API_VERSION and documented in CHANGELOG.
    """

    ADAPTER_API_VERSION = "1.0.0"  # API version, not adapter version
    ADAPTER_NAME: str  # Must be set by subclasses (e.g., "vectara")

    @abstractmethod
    def query(self, query: str, top_k: int = 5) -> RagResult:
        """
        Execute single query against RAG system.

        Args:
            query: Query string
            top_k: Number of documents to retrieve

        Returns:
            RagResult with documents, scores, latency

        Raises:
            AdapterError: RAG system error
        """
        pass

    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate adapter-specific configuration.

        Args:
            config: Adapter configuration dict

        Returns:
            True if valid

        Raises:
            ConfigurationError: Invalid configuration with details
        """
        pass

    @abstractmethod
    def get_required_env_vars(self) -> List[str]:
        """
        Get list of required environment variables.

        Returns:
            List of env var names (e.g., ["VECTARA_API_KEY"])
        """
        pass

    @abstractmethod
    def get_options_schema(self) -> Dict[str, Any]:
        """
        Get JSON Schema for adapter-specific options.

        Returns:
            JSON Schema dict describing valid configuration options
        """
        pass
```

**Migration Path**:
- All existing adapters (Vectara, Goodmem, Agentset) must implement `RagAdapter`
- Add API version check in adapter registry
- Document adapter API versioning in CHANGELOG

---

### 3. Ensure Deterministic Behavior

**Requirements**:
- Seed RNGs if using randomness
- Isolate global clients (no module-level state)
- Make engines reentrant for background workers

**Anti-patterns to fix**:
```python
# ❌ BAD: Module-level state
client = VectaraClient()  # Shared across all calls

# ✅ GOOD: Client per call or dependency injection
def query(config):
    client = VectaraClient(config)
    return client.query(...)
```

```python
# ❌ BAD: Non-deterministic ordering
results = set(documents)  # Set order is random

# ✅ GOOD: Deterministic ordering
results = sorted(documents, key=lambda d: d.score, reverse=True)
```

**Reentrancy**:
- Comparison engine must support concurrent calls from multiple workers
- No shared mutable state between invocations
- Thread-safe or process-safe by design

---

### 4. Golden Parity Tests

**Purpose**: Ensure library produces identical output to CLI

**Location**: `tests/test_cli_library_parity.py`

**Strategy**:
1. Create 10+ test fixtures (queries + configs + expected outputs)
2. Run same query via CLI and via library
3. Normalize outputs (ignore timestamps, unstable fields)
4. Assert outputs are identical

```python
# tests/test_cli_library_parity.py
import pytest
import subprocess
import json
from ragdiff.api import run_single_query, create_comparison
from ragdiff.core.config import load_config

FIXTURES = [
    {
        "name": "vectara_single_query",
        "query": "What is retrieval-augmented generation?",
        "config_file": "tests/fixtures/vectara.yaml",
        "expected_cli_output": "tests/fixtures/expected/vectara_rag.json",
    },
    {
        "name": "goodmem_batch",
        "queries_file": "tests/fixtures/queries.txt",
        "config_file": "tests/fixtures/goodmem.yaml",
        "expected_cli_output": "tests/fixtures/expected/goodmem_batch.jsonl",
    },
    # Add 10+ fixtures covering:
    # - Different adapters (Vectara, Goodmem, Agentset)
    # - Single queries vs batch
    # - With and without LLM evaluation
    # - Edge cases (empty results, errors, timeouts)
]

@pytest.mark.parametrize("fixture", FIXTURES)
def test_cli_library_parity(fixture):
    """
    Ensure CLI and library produce identical outputs.

    This is CRITICAL for ensuring refactoring doesn't break behavior.
    """

    # Run via CLI
    if "query" in fixture:
        cli_result = subprocess.run(
            [
                "ragdiff", "compare",
                "--config", fixture["config_file"],
                fixture["query"]
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    else:
        cli_result = subprocess.run(
            [
                "ragdiff", "batch",
                "--config", fixture["config_file"],
                "--queries", fixture["queries_file"]
            ],
            capture_output=True,
            text=True,
            check=True,
        )

    cli_output = json.loads(cli_result.stdout)

    # Run via library
    config = load_config(fixture["config_file"])

    if "query" in fixture:
        library_result = run_single_query(config, fixture["query"])
        library_output = library_result.dict()
    else:
        queries = open(fixture["queries_file"]).read().splitlines()
        library_results = run_batch_queries(config, queries)
        library_output = [r.dict() for r in library_results]

    # Normalize (ignore timestamps and non-deterministic fields)
    normalized_cli = normalize_output(cli_output)
    normalized_lib = normalize_output(library_output)

    # Assert identical
    assert normalized_cli == normalized_lib, (
        f"CLI and library outputs differ for {fixture['name']}\n"
        f"CLI: {normalized_cli}\n"
        f"Lib: {normalized_lib}"
    )

def normalize_output(output):
    """Remove timestamps, UUIDs, and other non-deterministic fields."""
    if isinstance(output, dict):
        return {
            k: normalize_output(v)
            for k, v in output.items()
            if k not in ["timestamp", "request_id", "trace_id"]
        }
    elif isinstance(output, list):
        return [normalize_output(item) for item in output]
    else:
        return output
```

---

### 5. CLI Backwards Compatibility

**Requirements**:
- CLI continues to work exactly as before
- No breaking changes to CLI arguments or output format
- CLI internally uses `ragdiff.api` module

**Implementation**:
```python
# src/ragdiff/cli.py (refactored to use api module)
import typer
from ragdiff.api import run_single_query, run_batch_queries, get_available_adapters
from ragdiff.core.config import load_config
from ragdiff.formatters import format_json, format_markdown, format_csv

app = typer.Typer()

@app.command()
def compare(
    config: str = typer.Option(..., "--config", help="Path to config YAML"),
    query: str = typer.Argument(..., help="Query string"),
    output: str = typer.Option("json", "--output", help="Output format"),
    top_k: int = typer.Option(5, "--top-k", help="Number of documents"),
):
    """Execute single query comparison (UNCHANGED CLI interface)."""

    # Load config (existing function)
    cfg = load_config(config)

    # Use NEW API (internal change, no user impact)
    result = run_single_query(cfg, query, top_k=top_k)

    # Format output (existing function)
    if output == "json":
        print(format_json(result))
    elif output == "markdown":
        print(format_markdown(result))
    elif output == "csv":
        print(format_csv(result))
```

---

### 6. Semantic Versioning

**Version Format**: `MAJOR.MINOR.PATCH`

**Rules**:
- **MAJOR**: Breaking changes to `ragdiff.api` or `RagAdapterV1`
- **MINOR**: New features, backwards compatible
- **PATCH**: Bug fixes

**Examples**:
- `1.0.0` → `1.1.0`: Add new `export_results()` function to API
- `1.1.0` → `1.1.1`: Fix bug in LLM evaluation
- `1.1.1` → `2.0.0`: Change `run_single_query()` signature (breaking)

**CHANGELOG.md** (maintain for all releases):
```markdown
# Changelog

## [1.0.0] - 2025-10-20

### Added
- `ragdiff.api` module with stable programmatic interface
- `RagAdapterV1` base class for adapter versioning
- Golden parity tests (CLI vs library)
- Semantic versioning for breaking changes

### Changed
- CLI internally uses `ragdiff.api` (no user-facing changes)

### Deprecated
- None

### Removed
- None

### Fixed
- Ensured deterministic behavior (no global state)

### Security
- No security changes
```

---

### 7. Publishing Strategy

**Option A: PyPI (Recommended for production)**
1. Create `pyproject.toml` with proper metadata
2. Test publish to Test PyPI first
3. Publish to production PyPI
4. Tag releases in git

```toml
# pyproject.toml
[project]
name = "ragdiff"
version = "1.0.0"
description = "RAG system comparison library and CLI"
authors = [{name = "Waleed Kadous", email = "your@email.com"}]
license = {text = "MIT"}
readme = "README.md"
requires-python = ">=3.9.2"

dependencies = [
    "anthropic>=0.40.0",
    "pydantic>=2.0.0",
    "pyyaml>=6.0",
    "typer>=0.9.0",
    "rich>=13.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "pytest-asyncio>=0.21.0",
]

[project.scripts]
ragdiff = "ragdiff.cli:app"

[project.urls]
Homepage = "https://github.com/ansari-project/ragdiff"
Documentation = "https://ragdiff.readthedocs.io"
Repository = "https://github.com/ansari-project/ragdiff"
```

**Option B: Git Dependency (Development)**
```toml
# ragdiff-ui/backend/pyproject.toml
dependencies = [
    "ragdiff @ git+https://github.com/ansari-project/ragdiff.git@main",
]
```

---

## Implementation Checklist

### Phase 2.1: API Module Creation
- [ ] Create `src/ragdiff/api/__init__.py` with 6 public functions
- [ ] Implement each function using existing core modules
- [ ] Add comprehensive docstrings with examples
- [ ] Add type hints for all parameters and returns
- [ ] Update `__all__` exports

### Phase 2.2: Adapter Interface Freezing
- [ ] Create `src/ragdiff/adapters/base.py` with `RagAdapter`
- [ ] Update Vectara adapter to inherit from `RagAdapter`
- [ ] Update Goodmem adapter to inherit from `RagAdapter`
- [ ] Update Agentset adapter to inherit from `RagAdapter`
- [ ] Add adapter API version validation in registry
- [ ] Document adapter API versioning in README

### Phase 2.3: Deterministic Behavior
- [ ] Audit code for global state (module-level variables)
- [ ] Remove or isolate global clients
- [ ] Ensure RNG seeding if randomness used
- [ ] Test reentrancy (concurrent calls from workers)
- [ ] Document thread-safety guarantees

### Phase 2.4: Golden Parity Tests
- [ ] Create 10+ test fixtures (queries + configs + expected outputs)
- [ ] Implement `test_cli_library_parity()` for each fixture
- [ ] Run tests on current CLI to capture baseline
- [ ] Ensure tests pass with library implementation
- [ ] Add to CI/CD pipeline

### Phase 2.5: CLI Refactoring
- [ ] Update `cli.py` to use `ragdiff.api` internally
- [ ] Verify CLI output unchanged (golden parity tests pass)
- [ ] Test all CLI commands (compare, batch, list-tools, validate-config, quick-test)
- [ ] Update CLI help text if needed

### Phase 2.6: Versioning & Publishing
- [ ] Add semantic versioning to `__version__`
- [ ] Create CHANGELOG.md
- [ ] Update pyproject.toml with metadata
- [ ] Test publish to Test PyPI
- [ ] Publish to production PyPI (or setup git dependency)
- [ ] Tag release in git (v1.0.0)

### Phase 2.7: Documentation
- [ ] Update README with library usage examples
- [ ] Create API reference documentation
- [ ] Add migration guide for CLI users (no changes needed)
- [ ] Document breaking change policy

---

## Testing Strategy

### Unit Tests
- Test each `ragdiff.api` function independently
- Mock external dependencies (RAG APIs, LLM APIs)
- Cover error cases (invalid config, network errors, timeouts)

### Integration Tests
- Test full flow with real adapters (if API keys available)
- Test LLM evaluation with real Anthropic API
- Test batch processing with 100+ queries

### Parity Tests
- **CRITICAL**: Golden parity tests (CLI vs library output identical)
- Cover all adapters, single/batch, with/without LLM eval
- Edge cases (empty results, errors, timeouts)

### Performance Tests
- Benchmark library vs CLI performance (should be identical or faster)
- Test concurrent calls from multiple workers
- Memory leak detection (run 1000+ queries)

---

## Breaking Change Policy

**Before releasing 1.0.0**:
- Any changes allowed (pre-release)

**After 1.0.0**:
- **Breaking changes** → MAJOR version bump (1.x.x → 2.0.0)
- **New features** → MINOR version bump (1.0.x → 1.1.0)
- **Bug fixes** → PATCH version bump (1.0.0 → 1.0.1)

**Examples of breaking changes**:
- Changing function signatures in `ragdiff.api`
- Removing functions from `ragdiff.api`
- Changing `RagResult` or `ComparisonResult` data models
- Breaking adapter interface (`RagAdapter` API)

**Migration path**:
- Deprecate old API in MINOR release
- Remove deprecated API in next MAJOR release
- Provide migration guide in CHANGELOG

---

## Success Criteria

### Must Have
- [ ] All 6 functions in `ragdiff.api` implemented and tested
- [ ] All adapters inherit from `RagAdapter`
- [ ] 10+ golden parity tests pass (CLI vs library identical)
- [ ] CLI continues to work unchanged
- [ ] Published to PyPI or git dependency works
- [ ] Semantic versioning documented

### Should Have
- [ ] Comprehensive API documentation with examples
- [ ] Migration guide for library users
- [ ] Performance benchmarks (library vs CLI)
- [ ] Reentrancy tests (concurrent calls)

### Nice to Have
- [ ] Interactive examples in Jupyter notebooks
- [ ] Video tutorial on library usage
- [ ] Integration examples (FastAPI, Flask, etc.)

---

## Timeline Considerations

**Dependencies**:
- Can run in parallel with Phase 1 (Foundation & Auth)
- Should be completed before Phase 3 (Configurations) to enable config validation

**Critical Path**:
- Golden parity tests are critical (prevent regressions)
- Adapter interface freezing is critical (prevent future breaking changes)
- Semantic versioning is critical (manage expectations)

**Risk Mitigation**:
- Start with golden parity tests FIRST (establish baseline)
- Implement API incrementally (one function at a time)
- Get early feedback from FastAPI integration (dogfooding)

---

## References

- RAGDiff Web UI Plan: `codev/plans/0001-ragdiff-web-ui.md` (Phase 2)
- RAGDiff Web UI Spec: `codev/specs/0001-ragdiff-web-ui.md`
- Semantic Versioning: https://semver.org/
- Python Packaging: https://packaging.python.org/

---

## Questions for RAGDiff Maintainer

1. **Adapter versioning**: Should we support multiple adapter versions simultaneously (v1 and v2 coexist)?
2. **Breaking changes**: What's acceptable timeline for deprecation (1 release, 6 months, 1 year)?
3. **Performance**: Are there any performance benchmarks we should maintain (e.g., <100ms overhead)?
4. **Testing**: Do you have access to real RAG API keys for integration testing?
5. **Publishing**: Prefer PyPI or git dependency during development?

---

## Next Steps

1. **Use SPIDER Protocol** in RAGDiff repo:
   - Specify: Use this guidance document
   - Plan: Break into implementation phases
   - Implement: Create `ragdiff.api` module
   - Defend: Run golden parity tests
   - Evaluate: Performance and API usability
   - Review: Get feedback from FastAPI integration

2. **Start with Golden Parity Tests**:
   - Capture current CLI behavior as baseline
   - Implement tests before refactoring
   - Ensure tests pass throughout refactoring

3. **Incremental Implementation**:
   - Implement one API function at a time
   - Test each function independently
   - Maintain CLI compatibility throughout
