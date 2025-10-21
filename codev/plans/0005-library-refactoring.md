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

### Phase 1: Foundation

**Objective**: Create core infrastructure for library interface

**Deliverables**:
- `ragdiff/version.py` - Centralized version strings
- `ragdiff/core/errors.py` - Exception taxonomy
- `ragdiff/adapters/base.py` - Abstract `RagAdapter` class
- `ragdiff/adapters/registry.py` - Adapter discovery mechanism
- `ragdiff/adapters/__init__.py` - Auto-registration of built-in adapters

**Dependencies**: None

**Success Criteria**:
- All modules created and importable
- Version strings centralized
- Error hierarchy established
- Adapter ABC defined with proper signatures
- Registry can register and list adapters

**Tests**:
- Unit tests for registry operations
- Import tests for all new modules
- ABC enforcement tests

**Evaluation**:
- All foundation modules in place
- No circular imports
- Clean module structure

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

**Dependencies**: Phase 1 (base adapter class and registry)

**Success Criteria**:
- All adapters inherit from `RagAdapter`
- All adapters auto-register on import
- `get_available_adapters()` returns all three adapters
- All adapter tests pass

**Tests**:
- Adapter registration tests
- Adapter validation tests
- Backward compatibility tests

**Evaluation**:
- All adapters properly registered
- No breaking changes to adapter functionality
- Tests green

**Commit**: Single commit after phase evaluation

**Status**: pending

---

### Phase 3: Public Library Interface

**Objective**: Implement and export 6 core library functions

**Deliverables**:
- `ragdiff/__init__.py` with complete `__all__` exports
- Implementation of 6 core functions:
  - `run_single_query()`
  - `run_batch_queries()` (with Union return type)
  - `create_comparison()`
  - `evaluate_with_llm()`
  - `get_available_adapters()`
  - `validate_config()`
- Export `load_config` utility
- Export all error classes
- Export common models (RagResult, ToolConfig, LLMConfig, etc.)
- `LLMConfig` dataclass implementation
- `QueryErrorResult` dataclass (JSON-serializable)

**Dependencies**: Phase 2 (adapters ready)

**Success Criteria**:
- All 6 functions implemented and working
- Clean top-level imports work: `from ragdiff import run_single_query`
- `run_batch_queries` returns `List[Union[RagResult, QueryErrorResult]]`
- `QueryErrorResult` is JSON-serializable
- `LLMConfig` decouples from Anthropic-only

**Tests**:
- Unit tests for each function
- Integration tests with mocked adapters
- Error handling tests
- Type checking tests

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

### Phase 5: Determinism & Stability

**Objective**: Ensure deterministic behavior for production use

**Deliverables**:
- Audit and fix global state issues
- Implement deterministic sorting with tie-breakers
- Float normalization in serialization
- Thread-safety verification
- Remove any non-deterministic behavior

**Dependencies**: Phase 3 (library interface)

**Success Criteria**:
- No global mutable state
- Sorting uses `(-score, doc_id)` tie-breaker
- Float serialization normalized to 6-8 digits
- Concurrent calls work correctly
- Reentrancy tests pass

**Tests**:
- Concurrent execution tests
- Determinism tests (same input → same output)
- Float precision tests

**Evaluation**:
- Library safe for multi-threaded use
- Results are deterministic
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
- Phase 5 (Determinism) can start after Phase 3
- Documentation (Phase 7) can be drafted during implementation

## Notes

- Each phase follows IDE cycle: Implement → Defend → Evaluate
- Each phase ends with single atomic commit
- No phase begins until previous phase is committed
- User approval required at Evaluate step before commit

## Consultation Log

### Initial Plan Consultation
*Pending - will consult GPT-5 and Gemini Pro after plan creation*

## Revision History

- 2025-10-21: Initial plan draft
