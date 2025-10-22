# Implementation Plan: RAGDiff Library Refactoring

**Specification**: codev/specs/0005-library-refactoring.md
**Status**: Draft
**Created**: 2025-10-21
**SPIDER Protocol**: Active

## Overview

Transform RAGDiff from a CLI-only tool into a proper Python library with a stable programmatic API, while redesigning the CLI with clearer command names.

**Key Objectives**:
1. Export 6 core functions from top-level `ragdiff` module
2. Freeze adapter interface via ABCs with versioning
3. Ensure deterministic, reentrant behavior
4. Redesign CLI: `query`, `run`, `compare` commands
5. Implement comprehensive testing with golden parity tests

## Phase Breakdown

### Phase 0: Performance Baseline

**Objective**: Establish performance baseline before refactoring

**Deliverables**:
- Performance benchmark script (`tests/benchmarks/baseline.py`)
- Baseline measurements for:
  - Single query latency (average, p50, p95, p99)
  - Batch query throughput (queries/second)
  - Memory usage (RSS, peak)
  - CLI startup time
- Baseline results saved to `tests/benchmarks/baseline_results.json`
- Sample query outputs saved for correctness comparison (`tests/benchmarks/baseline_outputs.json`)
  - Ensures refactored code produces identical results, not just similar performance

**Dependencies**: None

**Success Criteria**:
- Benchmark script runs successfully
- All baseline metrics captured
- Performance results saved for comparison
- Sample outputs saved for correctness validation
- Outputs are deterministic (same query → same output)

**Tests**:
- Benchmark script executes without errors
- Results file is valid JSON
- Output file contains deterministic results

**Evaluation**:
- Baseline established
- Ready for both performance and correctness comparison after refactoring

**Commit**: Single commit after phase evaluation

**Status**: pending

---

### Phase 1: Foundation

**Objective**: Create core infrastructure for library interface

**Deliverables**:
- `ragdiff/version.py` - Centralized version strings
- `ragdiff/core/errors.py` - Exception taxonomy
- `ragdiff/adapters/base.py` - Abstract `RagAdapter` class with:
  - `ADAPTER_API_VERSION = "1.0.0"` class attribute
  - `ADAPTER_NAME` class attribute
  - Abstract methods with proper signatures
- `ragdiff/adapters/registry.py` - Adapter discovery mechanism with:
  - `ADAPTER_API_VERSION` compatibility enforcement
  - Version mismatch warnings/errors
  - Adapter metadata tracking

**Dependencies**: None

**Success Criteria**:
- All modules created and importable
- Version strings centralized
- Error hierarchy established
- Adapter ABC defined with proper signatures
- Registry can register and list adapters
- Registry enforces `ADAPTER_API_VERSION` compatibility
- Version mismatches detected and reported

**Tests**:
- Unit tests for registry operations
- Import tests for all new modules
- ABC enforcement tests
- Version compatibility tests (matching, mismatched)

**Evaluation**:
- All foundation modules in place
- No circular imports
- Clean module structure
- Version compatibility enforced

**Commit**: Single commit after phase evaluation

**Status**: pending

---

### Phase 2: Adapter Migration

**Objective**: Update existing adapters to use ABC and registry

**Deliverables**:
- Update `VectaraAdapter` to inherit from `RagAdapter`
- Update `GoodmemAdapter` to inherit from `RagAdapter`
- Update `AgentsetAdapter` to inherit from `RagAdapter`
- Each adapter registers on import
- Update `validate_config` to `-> None` signature
- Implement metadata methods for each adapter:
  - `get_required_env_vars() -> List[str]` - Returns list of required env var names
  - `get_options_schema() -> Dict[str, Any]` - Returns JSON schema for adapter options
  - Accurate, complete metadata for each adapter

**Dependencies**: Phase 1 (base adapter class and registry)

**Success Criteria**:
- All adapters inherit from `RagAdapter`
- All adapters auto-register on import
- All adapters set `ADAPTER_API_VERSION = "1.0.0"`
- All adapters set `ADAPTER_NAME` correctly
- `get_available_adapters()` returns all three adapters with complete metadata
- All adapter tests pass
- Metadata methods return accurate information

**Tests**:
- Adapter registration tests
- Adapter validation tests
- Backward compatibility tests
- Metadata method tests (env vars, options schema)
- Metadata accuracy tests

**Evaluation**:
- All adapters properly registered
- No breaking changes to adapter functionality
- Metadata complete and accurate
- Tests green

**Commit**: Single commit after phase evaluation

**Status**: pending

---

### Phase 3: Public Library Interface

**Objective**: Implement and export 6 core library functions

**Deliverables**:
- `ragdiff/__init__.py` with complete `__all__` exports including `__version__`
- Implementation of 6 core functions:
  - `run_single_query()`
  - `run_batch_queries()` with full signature:
    - Union return type: `List[Union[RagResult, QueryErrorResult]]`
    - Concurrency controls: `max_workers`, `per_query_timeout` (seconds)
    - Failure handling: `raise_on_any_error` flag
    - Progress callback support
  - `create_comparison()`
  - `evaluate_with_llm()`
  - `get_available_adapters()` with full metadata schema:
    - Returns: `name`, `api_version`, `required_env_vars`, `options_schema`, `description`
  - `validate_config()`
- Export `load_config` utility
- Export all error classes
- Export common models (RagResult, ToolConfig, LLMConfig, etc.)
- Export `__version__` from version.py
- `LLMConfig` dataclass implementation
- `QueryErrorResult` dataclass (JSON-serializable with `error_message`, `error_type`)
- **On-disk format specification**:
  - Define JSON schema for saved results (single query, batch, comparison)
  - Ensure all dataclasses are JSON-serializable via dataclasses.asdict() or custom serializers
  - Document format in docstrings and type hints
- **Deterministic output** (moved from Phase 5):
  - Implement deterministic sorting with tie-breakers: `(-score, doc_id)`
  - Float normalization in serialization (6-8 digit precision)

**Dependencies**: Phase 2 (adapters ready)

**Success Criteria**:
- All 6 functions implemented and working
- Clean top-level imports work: `from ragdiff import run_single_query, __version__`
- `run_batch_queries` returns `List[Union[RagResult, QueryErrorResult]]` preserving order
- `run_batch_queries` implements all concurrency parameters
- Partial failures tested: mix of RagResult and QueryErrorResult
- `QueryErrorResult` is JSON-serializable
- `LLMConfig` decouples from Anthropic-only
- `get_available_adapters()` returns complete metadata for all adapters
- **On-disk format**: All dataclasses serialize to JSON cleanly
- **On-disk format**: JSON schema documented and consistent
- **Deterministic sorting**: Same input produces same output
- **Float precision**: Normalized to 6-8 digits for consistency

**Tests**:
- Unit tests for each function
- Integration tests with mocked adapters
- Error handling tests
- Partial failure tests (mixed RagResult/QueryErrorResult)
- Concurrency parameter tests (max_workers, timeouts)
- Type checking tests
- JSON serialization tests (all dataclasses)
- JSON schema validation tests
- Determinism tests (same input → same output)
- Float precision tests

**Evaluation**:
- Library can be imported and used programmatically
- All functions work as specified
- Type hints correct

**Commit**: Single commit after phase evaluation

**Status**: pending

---

### Phase 4: CLI Redesign

**Objective**: Redesign CLI with new command structure

**Deliverables**:
- Rename `compare` → `query` command
- Rename `batch` → `run` command
- New `compare` command for comparing result files
- `load_result_file()` helper for compare command
- All CLI commands use library functions internally
- Update CLI help text and documentation

**Dependencies**: Phase 3 (library functions available)

**Success Criteria**:
- `ragdiff query "text" --config config.yaml` works
- `ragdiff run queries.txt --config config.yaml` works
- `ragdiff compare result1.json result2.json --evaluate` works
- CLI help text is clear and accurate
- All CLI commands internally use library functions

**Tests**:
- CLI integration tests for each command
- Output format tests
- Error message tests

**Evaluation**:
- All three commands work correctly
- Help text is clear
- No regressions in functionality

**Commit**: Single commit after phase evaluation

**Status**: pending

---

### Phase 5: Thread-Safety & Stability

**Objective**: Ensure thread-safe, reentrant behavior for production use

**Deliverables**:
- Audit and fix global state issues
- Thread-safety verification for all library functions
- Shared serialization utility (`ragdiff/core/serialization.py`) for consistent JSON output
- Remove any non-reentrant behavior
- Ensure adapter instances are thread-safe or properly isolated

**Dependencies**: Phase 3 (library interface)

**Success Criteria**:
- No global mutable state
- Concurrent calls work correctly
- Reentrancy tests pass
- Shared serialization utility handles all JSON output
- Adapters are thread-safe or properly documented

**Tests**:
- Concurrent execution tests (10+ workers)
- Reentrancy tests (same function called multiple times)
- Thread-safety tests (shared state detection)
- Serialization consistency tests

**Evaluation**:
- Library safe for multi-threaded use
- No race conditions detected
- Tests prove stability

**Commit**: Single commit after phase evaluation

**Status**: pending

---

### Phase 6: Golden Parity Tests

**Objective**: Ensure library and CLI produce identical results

**Deliverables**:
- Parity test framework
- 10+ parity test fixtures covering:
  - Each adapter (Vectara, Goodmem, Agentset)
  - Single query mode
  - Batch query mode
  - With and without comparison
  - Edge cases (empty results, errors)
- `normalize_output()` function for comparisons
- Parity tests in CI

**Dependencies**: Phase 4 (CLI redesigned)

**Success Criteria**:
- All parity tests pass
- CLI and library produce identical normalized output
- Coverage for all adapters and modes
- LLM evaluation tested separately (not in parity tests)

**Tests**:
- Parity tests (CLI vs library)
- Edge case parity tests
- Normalization tests

**Evaluation**:
- 100% parity between CLI and library
- All edge cases covered
- CI integration complete

**Commit**: Single commit after phase evaluation

**Status**: pending

---

### Phase 7: Documentation & Polish

**Objective**: Complete documentation for library release

**Deliverables**:
- README updated with library usage examples
- API reference documentation
- FastAPI integration example with thread pool
- CHANGELOG.md with v1.0.0 entry
- Update pyproject.toml metadata
- Migration notes (if needed)

**Dependencies**: Phase 6 (all functionality complete)

**Success Criteria**:
- README has clear library examples
- API docs complete for all 6 functions
- FastAPI example works
- CHANGELOG follows format
- Package metadata accurate

**Tests**:
- Documentation examples run correctly
- All docstrings accurate

**Evaluation**:
- Documentation is complete and accurate
- Examples work
- Ready for release

**Commit**: Single commit after phase evaluation

**Status**: pending

---

## Success Metrics

### Functional Metrics
- [ ] All 6 core library functions working correctly
- [ ] All 3 CLI commands working correctly
- [ ] 100% of existing tests still passing
- [ ] 100% of golden parity tests passing
- [ ] All adapters implementing RagAdapter ABC

### Quality Metrics
- [ ] Test coverage: ≥90%
- [ ] Type hint coverage: 100% for public interface
- [ ] Documentation coverage: 100% for public interface
- [ ] Linting: 0 errors/warnings

### Performance Metrics
- [ ] Library overhead: <10ms per call
- [ ] Concurrent calls: 10+ workers supported
- [ ] Memory: No leaks in 1000+ query test

## Risk Mitigation

### Risk: Breaking Existing Functionality
- **Mitigation**: Golden parity tests ensure identical behavior
- **Status**: Tests in Phase 6

### Risk: Performance Regression
- **Mitigation**: Benchmark tests before/after
- **Status**: Monitor in Phase 5

### Risk: Incomplete Error Handling
- **Mitigation**: Comprehensive error tests in each phase
- **Status**: Tests in Phases 2-3

## Timeline Considerations

**No time estimates** - Focus on phase completion, not calendar time.

**Critical Path**:
1. Foundation (Phase 1) → Everything else
2. Adapter Migration (Phase 2) → Library Interface (Phase 3)
3. Library Interface (Phase 3) → CLI Redesign (Phase 4)
4. CLI Redesign (Phase 4) → Parity Tests (Phase 6)

**Parallel Work Opportunities**:
- Phase 5 (Thread-Safety) can start after Phase 3
- Documentation (Phase 7) can be drafted during implementation

## Notes

- Each phase follows IDE cycle: Implement → Defend → Evaluate
- Each phase ends with single atomic commit
- No phase begins until previous phase is committed
- User approval required at Evaluate step before commit

## Consultation Log

### Implementation Plan Review (2025-10-21)

**Consulted**: GPT-5 Pro, Gemini 2.5 Pro

**Key Recommendations Applied**:

1. **Phase 3 Enhancement** (GPT-5, Gemini):
   - Moved deterministic sorting and float normalization from Phase 5 to Phase 3
   - Added full batch API signature with concurrency controls
   - Added complete metadata schema for `get_available_adapters()`
   - Added `__version__` export to top-level module

2. **Phase 1 Enhancement** (GPT-5):
   - Added `ADAPTER_API_VERSION` compatibility enforcement to registry
   - Added version mismatch detection and warnings

3. **Phase 2 Enhancement** (GPT-5, Gemini):
   - Added adapter metadata methods: `get_required_env_vars()`, `get_options_schema()`
   - Ensured all adapters provide accurate, complete metadata

4. **Phase 5 Refocus** (GPT-5, Gemini):
   - Renamed to "Thread-Safety & Stability"
   - Removed determinism features (moved to Phase 3)
   - Added shared serialization utility for consistent JSON output
   - Focus on thread-safety and reentrancy

5. **Phase 0 Addition** (Gemini):
   - Added performance baseline phase before implementation
   - Captures latency, throughput, memory metrics
   - Enables before/after comparison

**Status**: All recommendations incorporated into plan

## Revision History

- 2025-10-21: Initial plan draft
- 2025-10-21: Updated with consultation feedback from GPT-5 Pro and Gemini 2.5 Pro
