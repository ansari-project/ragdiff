# Specification: RAGDiff Library Refactoring

**Status**: Draft
**Created**: 2025-10-21
**Reference**: api-refactor-guidance.md
**SPIDER Protocol**: Active

## Problem Statement

RAGDiff currently functions as a CLI-only tool, which limits its utility for programmatic integration. The RAGDiff Web UI (spec 0001) requires RAGDiff to be usable as a library with a stable programmatic API to enable the FastAPI backend to perform comparisons, run batch queries, and evaluate results. Without a stable library interface:

1. Web UI cannot reliably integrate with RAGDiff functionality
2. Breaking changes could occur without warning
3. Adapter interface is not frozen, risking future incompatibilities
4. No semantic versioning for managing breaking changes
5. Potential global state or non-deterministic behavior could cause issues in multi-threaded web environments

## Stakeholders

- **Primary**: RAGDiff maintainers (Waleed)
- **Secondary**: Web UI developers, FastAPI backend developers
- **Tertiary**: Future library users, Python package consumers

## Current State

### Strengths
- ✅ Core logic well-separated from CLI (models, adapters, comparison, evaluation)
- ✅ Clean adapter pattern for RAG tools
- ✅ Excellent test coverage (90+%)
- ✅ Pure dataclasses with no CLI dependencies

### Gaps
- ❌ No stable public API for library usage
- ❌ Adapter interface not frozen (risk of breaking changes)
- ❌ Potential global state or non-deterministic behavior
- ❌ CLI and library not clearly separated
- ❌ No semantic versioning for breaking changes

## Desired State

A dual-purpose package that:
1. Maintains CLI backwards compatibility (no breaking changes)
2. Provides stable `ragdiff.api` module for programmatic access
3. Freezes adapter interface via ABCs with explicit versioning
4. Ensures deterministic, reentrant behavior for background workers
5. Follows semantic versioning for managing breaking changes
6. Can be published to PyPI or used as git dependency

## Solution Approaches

### Approach 1: Comprehensive Library Refactoring (RECOMMENDED)

**Design**:
- Create `src/ragdiff/api/__init__.py` with 6 public functions for library usage
- Define abstract `RagAdapter` base class with versioning
- Audit and fix global state, non-deterministic behavior
- Implement golden parity tests (CLI vs library output identical)
- Refactor CLI to internally use library API via `ragdiff.api` module
- Add semantic versioning and CHANGELOG.md

**Pros**:
- Complete solution addressing all gaps
- Establishes solid foundation for future development
- Clear separation of concerns (library vs CLI)
- Strong backwards compatibility guarantees
- Professional library interface for programmatic use

**Cons**:
- More extensive changes required
- Need comprehensive testing strategy
- Initial time investment higher

**Complexity**: Medium (well-structured, mostly organizational)

**Risk Assessment**: Low
- Core logic already well-structured
- Changes are mostly organizational
- Golden parity tests ensure no regressions
- Can implement incrementally

### Approach 2: Minimal Library Wrapper

**Design**:
- Create thin wrapper around existing CLI functionality
- Expose only essential functions needed for Web UI
- Skip adapter interface freezing
- Minimal testing (basic smoke tests)

**Pros**:
- Faster initial implementation
- Minimal code changes
- Lower initial complexity

**Cons**:
- Technical debt accumulation
- No adapter stability guarantees
- Potential breaking changes in future
- Weak foundation for long-term growth
- May need rework later

**Complexity**: Low

**Risk Assessment**: Medium-High
- Defers important architectural decisions
- Could require significant rework later
- No protection against breaking changes

## Recommended Approach

**Approach 1: Comprehensive Library Refactoring**

This approach transforms RAGDiff into a proper Python library with a stable programmatic API while maintaining CLI compatibility. It provides the solid foundation needed for the Web UI and future integrations while maintaining professional library standards.

## Detailed Design

### 1. API Module Structure

**Location**: `src/ragdiff/api/__init__.py`

**Public Interface** (6 functions):
1. `run_single_query()` - Execute single query against RAG system
2. `run_batch_queries()` - Execute multiple queries with optional parallelization
3. `create_comparison()` - Compare multiple RAG results
4. `evaluate_with_llm()` - Evaluate results using Claude LLM
5. `get_available_adapters()` - List available adapters with schemas
6. `validate_config()` - Validate configuration without executing

**Version**: 1.0.0 (initial release)

### 2. Adapter Interface

**Location**: `src/ragdiff/adapters/base.py`

**Abstract Base Class**:
```python
class RagAdapter(ABC):
    ADAPTER_API_VERSION = "1.0.0"
    ADAPTER_NAME: str  # Set by subclasses

    @abstractmethod
    def query(self, query: str, top_k: int = 5) -> RagResult:
        pass

    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def get_required_env_vars(self) -> List[str]:
        pass

    @abstractmethod
    def get_options_schema(self) -> Dict[str, Any]:
        pass
```

**Migration**: All existing adapters (Vectara, Goodmem, Agentset) must implement this ABC.

### 3. Deterministic Behavior Requirements

**Anti-patterns to eliminate**:
- ❌ Module-level clients (shared state)
- ❌ Non-deterministic ordering (sets without sorting)
- ❌ Unseeded random number generators
- ❌ Global mutable state

**Best practices**:
- ✅ Client per call or dependency injection
- ✅ Deterministic ordering (sorted by score)
- ✅ Thread-safe or process-safe by design
- ✅ Reentrant engines for concurrent calls

### 4. Golden Parity Tests

**Purpose**: Ensure library produces identical output to CLI

**Strategy**:
1. Create 10+ test fixtures (queries + configs + expected outputs)
2. Run same query via CLI and via library
3. Normalize outputs (ignore timestamps, unstable fields)
4. Assert outputs are identical

**Coverage**:
- Different adapters (Vectara, Goodmem, Agentset)
- Single queries vs batch
- With and without LLM evaluation
- Edge cases (empty results, errors, timeouts)

### 5. CLI Refactoring

**Requirement**: CLI continues to work exactly as before

**Implementation**:
- CLI commands internally use `ragdiff.api` module
- No changes to CLI arguments or output format
- Same behavior, different internal implementation

**Example**:
```python
@app.command()
def compare(config: str, query: str, ...):
    cfg = load_config(config)
    result = run_single_query(cfg, query, top_k=top_k)  # NEW API
    print(format_json(result))  # Existing formatter
```

### 6. Semantic Versioning

**Format**: MAJOR.MINOR.PATCH

**Rules**:
- **MAJOR**: Breaking changes to `ragdiff.api` or `RagAdapter`
- **MINOR**: New features, backwards compatible
- **PATCH**: Bug fixes

**Documentation**: Maintain CHANGELOG.md for all releases

### 7. Additional Requirements from Consultation

Based on multi-agent feedback, the following components must be added:

#### 7.1 Error Taxonomy (`ragdiff.core.errors`)
**Purpose**: Stable exception contract for library users

```python
# ragdiff/core/errors.py
class RagDiffError(Exception):
    """Base exception for all RAGDiff errors"""
    pass

class ConfigurationError(RagDiffError):
    """Invalid configuration"""
    pass

class AdapterError(RagDiffError):
    """RAG system error (network, auth, etc.)"""
    pass

class LLMEvaluationError(RagDiffError):
    """LLM evaluation failed"""
    pass

class QueryError(RagDiffError):
    """Query execution error"""
    pass
```

**Export Strategy**: Re-export from `ragdiff.api.__init__` in `__all__`

#### 7.2 Adapter Registry (`ragdiff.adapters.registry`)
**Purpose**: Centralized adapter discovery and version validation

```python
# ragdiff/adapters/registry.py
_ADAPTERS: Dict[str, Type[RagAdapter]] = {}

def register_adapter(adapter_cls: Type[RagAdapter]) -> None:
    """Register an adapter with version check"""
    # Validate API version compatibility
    if adapter_cls.ADAPTER_API_VERSION != ADAPTER_API_VERSION:
        raise ValueError(f"Incompatible adapter API version")
    _ADAPTERS[adapter_cls.ADAPTER_NAME] = adapter_cls

def get_adapter(name: str) -> Type[RagAdapter]:
    """Get adapter class by name"""
    if name not in _ADAPTERS:
        raise KeyError(f"Unknown adapter: {name}")
    return _ADAPTERS[name]

def list_adapters() -> List[str]:
    """List all registered adapter names"""
    return list(_ADAPTERS.keys())
```

**Usage**: Each adapter module calls `register_adapter()` at import time

#### 7.3 Version Centralization (`ragdiff/version.py`)
**Purpose**: Single source of truth for version strings

```python
# ragdiff/version.py
VERSION = "1.0.0"
ADAPTER_API_VERSION = "1.0.0"
```

**Import Pattern**: All modules import from this file

#### 7.4 Enhanced Public API Exports
**Updated `__all__`**:

```python
# ragdiff/api/__init__.py
__all__ = [
    # Core functions
    "run_single_query",
    "run_batch_queries",
    "create_comparison",
    "evaluate_with_llm",
    "get_available_adapters",
    "validate_config",

    # Utilities
    "load_config",

    # Exceptions
    "RagDiffError",
    "ConfigurationError",
    "AdapterError",
    "LLMEvaluationError",
    "QueryError",

    # Version
    "__version__",
]
```

#### 7.5 LLMConfig for Evaluation
**Purpose**: Decouple from Anthropic, enable future providers

```python
# ragdiff/core/models.py (or config.py)
@dataclass
class LLMConfig:
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    api_key_env: str = "ANTHROPIC_API_KEY"
    temperature: float = 0.0  # Deterministic by default
    max_tokens: int = 4096
```

**Updated Function Signatures**:
```python
def create_comparison(
    results: List[RagResult],
    llm_evaluate: bool = False,
    llm_config: Optional[LLMConfig] = None,  # Changed from llm_model, llm_api_key
) -> ComparisonResult:
    pass

def evaluate_with_llm(
    results: List[RagResult],
    config: LLMConfig,  # Required, not optional with defaults
) -> LLMEvaluation:
    pass
```

#### 7.6 Enhanced Batch API
**Updated Signature**:

```python
def run_batch_queries(
    config: ToolConfig,
    queries: List[str],
    top_k: int = 5,
    parallel: bool = True,
    max_workers: Optional[int] = None,  # NEW
    per_query_timeout: Optional[int] = None,  # NEW
    raise_on_any_error: bool = False,  # NEW
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> List[RagResult]:
    """
    For partial failure handling:
    - If raise_on_any_error=True: Raise on first query error
    - If raise_on_any_error=False: Return mixed list of RagResult and QueryErrorResult
    """
    pass
```

**QueryErrorResult** (for partial failures):
```python
@dataclass
class QueryErrorResult:
    query: str
    error: Exception
    error_type: str
```

#### 7.7 Deterministic Sorting
**Requirement**: All result lists sorted with tie-breakers

```python
# In all adapters and comparison logic
results.sort(key=lambda r: (-r.score, r.document.id or ""))  # Stable sort
```

#### 7.8 FastAPI Usage Documentation
**Requirement**: Document thread pool executor usage

```python
# Example for FastAPI integration docs
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from ragdiff.api import run_single_query

@app.post("/query")
async def query_endpoint(query: str):
    # REQUIRED: Run in thread pool to avoid blocking event loop
    result = await run_in_threadpool(
        run_single_query,
        config,
        query
    )
    return result
```

## Success Criteria

### Must Have (Phase Complete)
- [ ] All 6 functions in `ragdiff.api` implemented and tested
- [ ] `load_config` exported from public API
- [ ] All custom exceptions (`RagDiffError`, etc.) exported from public API
- [ ] `ragdiff.core.errors` module created with stable exception taxonomy
- [ ] `ragdiff.adapters.registry` module created with adapter discovery
- [ ] `ragdiff/version.py` created as single source of truth for versions
- [ ] `LLMConfig` dataclass implemented for evaluation configuration
- [ ] All adapters inherit from `RagAdapter` ABC with `-> None` validate_config
- [ ] Golden parity tests pass, covering every adapter in both single and batch query modes, with and without LLM evaluation
- [ ] Parity tests include float normalization (6-8 digit precision)
- [ ] Deterministic sorting with tie-breakers implemented (`-score, doc_id`)
- [ ] CLI continues to work unchanged (all existing tests pass)
- [ ] Package can be imported and used programmatically
- [ ] Semantic versioning documented in CHANGELOG.md
- [ ] No global state or non-deterministic behavior
- [ ] All existing tests continue to pass
- [ ] FastAPI usage documentation with thread pool executor example

### Should Have
- [ ] Comprehensive API documentation with examples
- [ ] Published to PyPI or git dependency works
- [ ] Performance benchmarks (library vs CLI)
- [ ] Reentrancy tests (concurrent calls)

### Nice to Have
- [ ] Interactive examples in Jupyter notebooks
- [ ] Integration examples (FastAPI usage)
- [ ] Video tutorial on library usage

## Open Questions

### Critical (Blocks Progress - MUST RESOLVE BEFORE PLANNING)

**From Multi-Agent Consultation:**

1. **CLI `compare` Command Semantics** (GPT-5)
   - What does the existing CLI `compare` command output today?
   - Is it a single `RagResult` or a `ComparisonResult` across multiple adapters/configs?
   - This affects parity test design and API mapping
   - **Action**: Examine current CLI implementation before planning phase

2. **Batch Partial Failure Strategy** (GPT-5)
   - How should `run_batch_queries()` handle per-query failures?
   - Option A: Return `List[Union[RagResult, QueryErrorResult]]` preserving order
   - Option B: Return wrapper `{ results: [...], errors: [...] }`
   - Option C: Raise on first error with `raise_on_any_error` flag
   - **Decision Needed**: Choose approach before API design

3. **LLM Evaluation in CI** (Both models)
   - Should CI parity tests use cached golden LLM responses or skip live calls?
   - LLMs are non-deterministic; live calls will cause test flakiness
   - **Recommendation**: Use cached responses for CI, optional live tests
   - **Decision Needed**: Confirm approach

### Important (Affects Design)

4. **Adapter Discovery Mechanism** (GPT-5)
   - Is simple in-repo registry acceptable to start?
   - Registry: `ragdiff.adapters.registry` with `register_adapter()` and `list_adapters()`
   - **Recommendation**: Start simple, defer entry points
   - **Confirmation Needed**: Acceptable approach?

5. **Error Taxonomy Module** (GPT-5)
   - Should we create `ragdiff.core.errors` for exception definitions?
   - Export from `ragdiff.api` for stable contract
   - **Recommendation**: Yes, create error module
   - **Confirmation Needed**: Location and naming OK?

6. **Adapter versioning**: Should we support multiple adapter versions simultaneously (v1 and v2 coexist)?
   - **Recommendation**: Start with single version, add multi-version support if needed

7. **Publishing strategy**: PyPI or git dependency during development?
   - **Recommendation**: Git dependency initially, PyPI after stable

8. **Testing access**: Do we have real RAG API keys for integration testing?
   - **Impact**: May need to use mocked tests if keys not available

### Nice-to-Know (Optimization)

1. **Performance overhead**: What's acceptable overhead for library vs CLI?
   - **Target**: <10ms overhead acceptable (confirmed in consultation)

2. **Breaking change timeline**: What's acceptable deprecation period?
   - **Recommendation**: 1 minor release (deprecate in 1.1.0, remove in 2.0.0)

## Assumptions and Constraints

### Assumptions
- Core logic (models, adapters, comparison) is already well-structured
- Existing tests provide good coverage
- No major performance issues in current implementation
- Python 3.9.2+ is minimum supported version

### Constraints
- Must maintain CLI backwards compatibility (no breaking changes)
- Must follow user's git preferences (explicit file listing, no git add -A)
- Must use existing test infrastructure (pytest)
- Must adhere to existing code style (Ruff formatting)

## Technical Requirements

### Performance
- Library overhead: <10ms per call
- Concurrent calls: Support 10+ workers without degradation
- Memory: No memory leaks in long-running processes

### Security
- No API keys or secrets in code
- Environment variables for sensitive data
- Input validation for all API functions
- Secure defaults for all configurations

### Quality
- Test coverage: Maintain 90%+ coverage
- Type hints: All public API functions
- Documentation: Docstrings for all public functions
- Linting: Pass Ruff checks

### Compatibility
- Python: 3.9.2+
- OS: Cross-platform (Linux, macOS, Windows)
- Dependencies: Minimize new dependencies

## Non-Requirements

The following are explicitly OUT OF SCOPE for this refactoring:

- ❌ Adding new RAG adapters
- ❌ Changing CLI command structure
- ❌ Adding new CLI features
- ❌ Performance optimizations beyond determinism
- ❌ Database integration
- ❌ Async/await support (may add later)
- ❌ GraphQL or REST API (that's Web UI scope)

## Testing Strategy

### Unit Tests
- Test each `ragdiff.api` function independently
- Mock external dependencies (RAG APIs, LLM APIs)
- Cover error cases (invalid config, network errors, timeouts)

### Integration Tests
- Test full flow with real adapters (if API keys available)
- Test LLM evaluation with real Anthropic API
- Test batch processing with 100+ queries

### Parity Tests (CRITICAL)
- Golden parity tests (CLI vs library output identical)
- Cover all adapters, single/batch, with/without LLM eval
- Edge cases (empty results, errors, timeouts)

### Performance Tests
- Benchmark library vs CLI performance (should be identical or faster)
- Test concurrent calls from multiple workers
- Memory leak detection (run 1000+ queries)

## Documentation Requirements

### API Documentation
- Comprehensive docstrings for all 6 public functions
- Usage examples for common scenarios
- Error handling examples
- Type hints for all parameters and returns

### Migration Guide
- How to use library instead of CLI
- Common patterns and anti-patterns
- Breaking change policy

### README Updates
- Add library usage examples
- Document installation methods
- Link to API reference

## Dependencies

### Existing Dependencies (No Changes)
- anthropic>=0.40.0
- pydantic>=2.0.0
- pyyaml>=6.0
- typer>=0.9.0
- rich>=13.0.0

### New Dependencies (None Expected)
No new runtime dependencies required

## Implementation Phases

The implementation will be broken into logical phases during the Planning stage. Expected phases:

1. **Foundation**: Create API module structure and base adapter class
2. **API Implementation**: Implement 6 public functions
3. **Adapter Migration**: Update adapters to use ABC
4. **Determinism Audit**: Fix global state and non-deterministic behavior
5. **Golden Parity Tests**: Create comprehensive CLI vs library tests
6. **CLI Refactoring**: Update CLI to use API module
7. **Documentation**: Complete API docs and examples

Each phase will follow the IDE cycle (Implement, Defend, Evaluate) with proper git commits.

## Risks and Mitigation

### Risk: Breaking CLI Behavior
**Likelihood**: Medium
**Impact**: High
**Mitigation**: Golden parity tests ensure identical output

### Risk: Hidden Global State
**Likelihood**: Low
**Impact**: Medium
**Mitigation**: Systematic code audit and reentrancy tests

### Risk: Adapter Interface Too Restrictive
**Likelihood**: Low
**Impact**: Medium
**Mitigation**: Design ABC based on existing adapter patterns

### Risk: Test Coverage Gaps
**Likelihood**: Medium
**Impact**: Medium
**Mitigation**: Comprehensive test strategy with multiple test types

## Success Metrics

### Functional Metrics
- All 6 API functions working correctly
- 100% of existing CLI tests still passing
- 100% of golden parity tests passing
- All adapters implementing RagAdapter ABC

### Quality Metrics
- Test coverage: ≥90%
- Type hint coverage: 100% for public API
- Documentation coverage: 100% for public API
- Linting: 0 errors/warnings

### Performance Metrics
- Library overhead: <10ms per call
- Concurrent calls: 10+ workers supported
- Memory: No leaks in 1000+ query test

## Consultation Log

### First Consultation (After Initial Draft) - 2025-10-21

**Consulted Models**: GPT-5 (OpenAI), Gemini 2.5 Pro (Google)

#### Key Feedback Summary

Both models provided excellent, complementary feedback. GPT-5 focused on implementation details and concrete fixes, while Gemini Pro emphasized design refinements and future-proofing.

#### Critical Issues Identified

1. **CLI/Library Parity Test Mapping** (GPT-5)
   - Issue: Current parity tests show CLI `compare` command but library calls `run_single_query()`
   - Impact: These may not be equivalent - `compare` implies multiple systems, `run_single_query` returns one result
   - Resolution: Need to clarify what CLI `compare` actually outputs and ensure parity tests match semantics

2. **Error Taxonomy Not Defined** (GPT-5)
   - Issue: Functions reference `ConfigurationError`, `AdapterError`, `LLMEvaluationError` but no module defines them
   - Impact: No stable exception contract for library users
   - Resolution: Create `ragdiff.core.errors` module and export from `ragdiff.api`

3. **Adapter Discovery/Registry Missing** (GPT-5)
   - Issue: `get_available_adapters()` needs adapter metadata but no registry mechanism exists
   - Impact: Cannot implement the function without defining how adapters are discovered
   - Resolution: Add simple `ragdiff.adapters.registry` with `register_adapter()` and `list_adapters()`

4. **Configuration and Secret Handling** (Gemini Pro)
   - Issue: Passing API keys directly as function parameters (`llm_api_key: Optional[str]`)
   - Impact: Tight coupling to Anthropic, non-extensible, discouraged pattern for secrets
   - Resolution: Introduce `LLMConfig` dataclass similar to `ToolConfig` for better abstraction

5. **Missing Utilities in Public API** (Gemini Pro)
   - Issue: CLI uses `load_config()` but it's not exported from `ragdiff.api`
   - Impact: Library users can't load the same YAML configs as CLI
   - Resolution: Export `load_config` and all custom exceptions in `__all__`

#### Design Improvements

6. **ABC validate_config Contract** (Both models)
   - Issue: Method returns `bool` but also raises `ConfigurationError` - redundant
   - Resolution: Change to `-> None`, only raise exception on invalid config

7. **Batch API Partial Failures** (GPT-5)
   - Issue: `run_batch_queries()` returns `List[RagResult]` with no strategy for per-query failures
   - Impact: Can't distinguish successful from failed queries in batch
   - Resolution Options:
     - Option A: Return `List[Union[RagResult, QueryErrorResult]]` preserving order
     - Option B: Return wrapper `{ results: [...], errors: [...] }`
     - Add `raise_on_any_error: bool = False` flag

8. **Batch API Concurrency Controls** (GPT-5)
   - Issue: Only has `parallel: bool` but no controls for rate limiting, workers, timeouts
   - Impact: Can't handle adapters with strict rate limits
   - Resolution: Add `max_workers`, `per_query_timeout`, retry/backoff options

9. **LLM Evaluation Determinism** (Both models)
   - Issue: LLMs are inherently non-deterministic; parity tests will drift
   - Impact: Golden parity tests with LLM evaluation will be flaky
   - Resolution: Support `evaluation_cache` for tests, fix temperature/top_p, or skip LLM in CI parity tests

10. **Async Framework Usage Risk** (Gemini Pro)
    - Issue: Synchronous API will block event loops in FastAPI
    - Impact: Poor performance if not handled correctly
    - Resolution: Document requirement to use thread pool executors in async frameworks

#### Additional Refinements

11. **Version String Centralization** (GPT-5)
    - Create `ragdiff/version.py` with `VERSION` and `ADAPTER_API_VERSION` to avoid drift

12. **Float Normalization in Parity Tests** (GPT-5)
    - Round floats to fixed precision (6-8 digits) in `normalize_output()` to avoid trivial drift

13. **Deterministic Sorting with Tie-Breakers** (GPT-5)
    - Sort by `(-score, doc_id)` or `(-score, stable_hash)` for complete determinism

14. **Success Criteria Enhancement** (Gemini Pro)
    - Change "10+ golden parity tests pass" to "All golden parity tests pass, covering every adapter in both single and batch query modes, with and without LLM evaluation"

#### Questions Requiring Clarification

**CRITICAL** (from GPT-5):
1. What does the existing CLI `compare` command output today? Single `RagResult` or `ComparisonResult` across multiple adapters?
2. How should batch partial failures be handled? Mixed list or raise on first error?
3. For LLM evaluation in CI, use cached golden responses or skip live calls?
4. Adapter discovery: OK to start with simple in-repo registry?
5. Error taxonomy: Create `ragdiff.core.errors` module?

### Second Consultation (After User Feedback)
*Pending - will occur after user reviews and provides feedback on this draft*

## References

- RAGDiff Web UI Plan: `codev/plans/0001-ragdiff-web-ui.md` (Phase 2)
- RAGDiff Web UI Spec: `codev/specs/0001-ragdiff-web-ui.md`
- API Refactoring Guidance: `api-refactor-guidance.md`
- Semantic Versioning: https://semver.org/
- Python Packaging: https://packaging.python.org/

## Revision History

- 2025-10-21: Initial specification draft
- 2025-10-21: Renamed from "API Refactoring" to "Library Refactoring" for clarity
- 2025-10-21: Incorporated feedback from GPT-5 and Gemini 2.5 Pro consultation
  - Added section 7: Additional Requirements from Consultation
  - Created error taxonomy requirements (`ragdiff.core.errors`)
  - Created adapter registry requirements (`ragdiff.adapters.registry`)
  - Added version centralization requirements (`ragdiff/version.py`)
  - Enhanced public API exports (added `load_config`, exceptions)
  - Introduced `LLMConfig` for better abstraction
  - Enhanced batch API with concurrency controls
  - Added deterministic sorting requirements
  - Added FastAPI usage documentation requirements
  - Updated Open Questions with critical items from consultation
  - Enhanced Success Criteria based on feedback
  - Documented all consultation feedback in Consultation Log section
