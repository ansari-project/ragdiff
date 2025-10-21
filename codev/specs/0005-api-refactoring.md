# Specification: RAGDiff API Refactoring

**Status**: Draft
**Created**: 2025-10-21
**Reference**: api-refactor-guidance.md
**SPIDER Protocol**: Active

## Problem Statement

RAGDiff currently functions as a CLI-only tool, which limits its utility for programmatic integration. The RAGDiff Web UI (spec 0001) requires a stable programmatic API to enable the FastAPI backend to perform comparisons, run batch queries, and evaluate results. Without a stable library interface:

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

### Approach 1: Comprehensive Refactoring (RECOMMENDED)

**Design**:
- Create `src/ragdiff/api/__init__.py` with 6 public functions
- Define abstract `RagAdapter` base class with versioning
- Audit and fix global state, non-deterministic behavior
- Implement golden parity tests (CLI vs library output identical)
- Refactor CLI to internally use `ragdiff.api` module
- Add semantic versioning and CHANGELOG.md

**Pros**:
- Complete solution addressing all gaps
- Establishes solid foundation for future development
- Clear separation of concerns
- Strong backwards compatibility guarantees
- Professional library interface

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

**Approach 1: Comprehensive Refactoring**

This approach provides the solid foundation needed for the Web UI and future integrations while maintaining professional library standards.

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

## Success Criteria

### Must Have (Phase Complete)
- [ ] All 6 functions in `ragdiff.api` implemented and tested
- [ ] All adapters inherit from `RagAdapter` ABC
- [ ] 10+ golden parity tests pass (CLI vs library identical)
- [ ] CLI continues to work unchanged (all existing tests pass)
- [ ] Package can be imported and used programmatically
- [ ] Semantic versioning documented in CHANGELOG.md
- [ ] No global state or non-deterministic behavior
- [ ] All existing tests continue to pass

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

### Critical (Blocks Progress)
None identified - core architecture is well-understood

### Important (Affects Design)
1. **Adapter versioning**: Should we support multiple adapter versions simultaneously (v1 and v2 coexist)?
   - **Recommendation**: Start with single version, add multi-version support if needed
2. **Publishing strategy**: PyPI or git dependency during development?
   - **Recommendation**: Git dependency initially, PyPI after stable
3. **Testing access**: Do we have real RAG API keys for integration testing?
   - **Impact**: May need to use mocked tests if keys not available

### Nice-to-Know (Optimization)
1. **Performance overhead**: What's acceptable overhead for library vs CLI?
   - **Target**: <10ms overhead acceptable
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

*This section will be populated after multi-agent consultation with GPT-5 and Gemini Pro*

### First Consultation (After Initial Draft)
*Pending*

### Second Consultation (After User Feedback)
*Pending*

## References

- RAGDiff Web UI Plan: `codev/plans/0001-ragdiff-web-ui.md` (Phase 2)
- RAGDiff Web UI Spec: `codev/specs/0001-ragdiff-web-ui.md`
- API Refactoring Guidance: `api-refactor-guidance.md`
- Semantic Versioning: https://semver.org/
- Python Packaging: https://packaging.python.org/

## Revision History

- 2025-10-21: Initial specification draft
