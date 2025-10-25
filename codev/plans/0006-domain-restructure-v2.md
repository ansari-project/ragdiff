# RAGDiff v2.0.0 - Domain-Based Architecture Implementation Plan

**Status**: Draft
**Version**: 2.0.0
**Created**: 2025-10-25
**SPIDER Phase**: Planning
**Spec**: `codev/specs/0006-domain-restructure-v2.md`

## Overview

This plan breaks down the v2.0.0 restructure into 6 logical phases, each independently testable and deliverable. Each phase ends with evaluation, approval, and a single commit before proceeding to the next.

## Phase Status Tracking

- [ ] Phase 1: Core Data Models & File Loading
- [ ] Phase 2: System Interface & Tool Registry
- [ ] Phase 3: Run Execution Engine
- [ ] Phase 4: Comparison Engine
- [ ] Phase 5: CLI Commands
- [ ] Phase 6: Migration & Documentation

---

## Phase 1: Core Data Models & File Loading

**Objective**: Establish foundational data models and file loading infrastructure.

**Dependencies**: None (starting point)

### Tasks

1. **Custom Exception Hierarchy**
   - `RagDiffError` base exception
   - `ConfigError` for config-related issues
   - `RunError` for execution errors
   - `ComparisonError` for evaluation errors
   - `ValidationError` for input validation
   - Each with helpful error messages

2. **Logging Configuration**
   - Set up Python logging module
   - Configure log levels (DEBUG, INFO, WARNING, ERROR)
   - Log to console and file (configurable)
   - Include timestamps, module names, levels
   - Use throughout all subsequent phases

3. **Create Pydantic Models**
   - `Query` model with text, reference, metadata
   - `QuerySet` model with validation (max 1000 queries)
   - `Domain` model with evaluator config
   - `SystemConfig` model
   - `RetrievedChunk` model
   - `RunStatus` enum
   - `Run` model with snapshots
   - `Comparison` model
   - `EvaluationResult` model
   - `EvaluatorConfig` model
   - Add name validators (alphanumeric, hyphens, underscores only)

4. **Environment Variable Substitution**
   - Function to resolve `${VAR_NAME}` in config
   - Support for .env files (python-dotenv)
   - Validation that required vars exist
   - Raise ConfigError for missing vars with clear messages

5. **File Loaders**
   - `load_domain(domain_name: str) -> Domain`
   - `load_system(domain: str, system_name: str) -> SystemConfig`
   - `load_query_set(domain: str, query_set_name: str) -> QuerySet`
   - Auto-detection of .txt vs .jsonl for query sets
   - YAML parsing with validation
   - Raise ConfigError for missing/invalid files
   - Fail-fast validation (check before processing)

6. **File Structure Utilities**
   - Function to create domain directory structure
   - Function to get run file path (with date organization)
   - Function to get comparison file path (with date organization)
   - Validate directory paths (no traversal attacks)

### Success Criteria

- [ ] Custom exception hierarchy defined
- [ ] Logging configured and working
- [ ] All Pydantic models defined with proper types
- [ ] Field validators working (max queries, non-empty text, name format)
- [ ] Name validation working (no special chars, slashes, spaces)
- [ ] Environment variable substitution working
- [ ] Can load domain.yaml with all fields
- [ ] Can load system YAML with env var resolution
- [ ] Can load .txt query sets → `list[Query]`
- [ ] Can load .jsonl query sets → `list[Query]`
- [ ] 1000 query limit enforced
- [ ] ConfigError raised for missing files with clear messages
- [ ] ConfigError raised for missing env vars
- [ ] All models serialize/deserialize to/from JSON correctly

### Test Coverage

- Unit tests for each Pydantic model
- Unit tests for env var substitution
- Unit tests for each file loader
- Test error cases (missing files, invalid YAML, missing env vars)
- Test max query validation
- Test empty query validation
- Test date-based path generation

### Evaluation Criteria

- All tests pass
- No hardcoded paths
- Clear separation of concerns
- Type hints on all functions
- Error messages are actionable

### Phase Commit

Single commit after user approval:
```
[Spec 0006][Phase 1] feat: Core data models and file loading

- Pydantic models for all entities
- Environment variable substitution
- File loaders for domain, system, query sets
- Date-based file organization
- 1000 query limit validation
```

---

## Phase 2: System Interface & Tool Registry

**Objective**: Define the System ABC and tool registry pattern, validate with at least one working implementation.

**Dependencies**: Phase 1 (needs SystemConfig and RetrievedChunk models)

### Tasks

1. **System ABC**
   - Define abstract `System` class
   - `search(query: str, top_k: int) -> list[RetrievedChunk]` method
   - Docstrings and type hints

2. **Tool Registry**
   - `TOOL_REGISTRY: dict[str, type[System]]` global registry
   - `register_tool(name: str, tool_class: type[System])` function
   - `get_tool(name: str) -> type[System]` function
   - Clear error for unknown tools

3. **Tool Factory**
   - `create_system(config: SystemConfig) -> System` function
   - Instantiate tool from registry using config
   - Pass config dict to tool constructor
   - Handle tool initialization errors

4. **Refactor Existing Adapters**
   - Convert VectaraAdapter → VectaraSystem (implements System ABC)
   - Convert MongoDBAdapter → MongoDBSystem
   - Convert AgentsetAdapter → AgentsetSystem
   - Register all tools in registry
   - Update to return `list[RetrievedChunk]` instead of custom types

5. **Tool Base Class** (optional helper)
   - BaseSystem class with common utilities
   - Config validation helpers
   - Error handling helpers

### Success Criteria

- [ ] System ABC defined
- [ ] Tool registry working
- [ ] At least 3 tools registered (Vectara, MongoDB, Agentset)
- [ ] Can instantiate tools from config
- [ ] All tools return `list[RetrievedChunk]`
- [ ] Tools populate content, score, metadata correctly
- [ ] Unknown tool raises clear error
- [ ] Tools handle missing credentials gracefully

### Test Coverage

- Unit test for tool registry (register, get, unknown tool)
- Integration test for create_system factory
- Unit tests for each converted system
- Test that systems return correct RetrievedChunk format
- Test error handling for missing credentials
- Test top_k parameter works correctly

### Evaluation Criteria

- All existing adapters converted to System interface
- No breaking changes to tool functionality
- Clean separation: System ABC → specific implementations
- All tests pass
- Tools work with environment variables from config

### Phase Commit

```
[Spec 0006][Phase 2] feat: System interface and tool registry

- System ABC with search() method
- Tool registry pattern for discovery
- Converted adapters to System implementations
- Returns RetrievedChunk with metadata
- Factory for creating systems from config
```

---

## Phase 3: Run Execution Engine

**Objective**: Execute query sets against systems, handle errors, snapshot configs, save runs.

**Dependencies**: Phase 1 (models, loaders), Phase 2 (System interface)

### Tasks

1. **Run Executor Core**
   - `execute_run(domain: str, system: str, query_set: str) -> Run` function
   - Load domain, system config, query set
   - Create System instance
   - Initialize Run with `pending` status
   - Update to `running` status
   - **Execute queries sequentially** (start simple, safe)
     - Design allows future parallelization
     - Document thread-safety requirements for Systems
     - Parallel execution deferred to future version
   - Handle per-query errors (mark query as failed, continue)
   - Update to `completed`, `failed`, or `partial` status
   - Calculate metadata (duration, success count, etc.)

2. **Config Snapshotting**
   - Store full SystemConfig in Run.system_config
   - Store full QuerySet in Run.query_set_snapshot
   - Ensure immutability of snapshots

3. **Progress Reporting**
   - Optional callback for progress updates
   - Track: current query, total queries, successes, failures
   - Used by CLI for progress bar

4. **File Storage**
   - Save Run to `domains/<domain>/runs/YYYY-MM-DD/<run-id>.json`
   - Create date directories if needed
   - Atomic writes (write to temp, rename)
   - Pretty JSON formatting for readability

5. **Error Handling**
   - Per-query timeout
   - Per-query error capture (don't crash entire run)
   - System initialization errors
   - File write errors
   - Clear error messages

6. **Run Loading**
   - `load_run(domain: str, run_id: str) -> Run` function
   - Support full UUID and short prefixes
   - Support aliases (@latest, @2, etc.)
   - Search in date subdirectories

### Success Criteria

- [ ] Can execute a query set against a system
- [ ] Run saved to correct file path with date
- [ ] Run contains config snapshots
- [ ] Run status tracked correctly
- [ ] Partial failures handled (some queries succeed, some fail)
- [ ] Query results include retrieved chunks with metadata
- [ ] Duration tracked per query and overall
- [ ] Can load run by full UUID
- [ ] Can load run by short prefix
- [ ] Can load run by alias (@latest)

### Test Coverage

- Unit test for execute_run with mock system
- Integration test with real system
- Test partial failure handling
- Test config snapshotting (verify immutability)
- Test file storage (verify JSON format)
- Test run loading (full UUID, short prefix, alias)
- Test error handling (missing system, timeout, etc.)
- Test date directory creation

### Evaluation Criteria

- All tests pass
- Runs are reproducible from snapshots
- Error handling is robust
- Progress tracking works
- File organization is clean
- No data loss on errors

### Phase Commit

```
[Spec 0006][Phase 3] feat: Run execution engine

- Execute query sets against systems
- Config snapshotting for reproducibility
- Run state management (pending/running/completed/failed/partial)
- Per-query error handling
- Date-organized file storage
- Run loading with UUID/prefix/alias support
```

---

## Phase 4: Comparison Engine

**Objective**: Compare runs using LLM evaluation, format output.

**Dependencies**: Phase 1 (models), Phase 3 (run loading)

### Tasks

1. **Comparison Core**
   - `compare_runs(domain: str, run_ids: list[str]) -> Comparison` function
   - Load all runs (using load_run from Phase 3)
   - Validate all runs from same domain
   - Validate all runs use same query set (or compatible)
   - Extract evaluator config from domain
   - Snapshot evaluator config in comparison

2. **LLM Evaluation**
   - For each query in runs:
     - Load reference answer (if exists)
     - Load retrieved chunks from each run
     - Format prompt using evaluator.prompt_template
     - Call LLM (using Anthropic API) with error handling:
       - **Retry logic**: Max 3 retries with exponential backoff (2s, 4s, 8s)
       - **Rate limits**: Catch and retry with backoff
       - **Parse errors**: Mark evaluation as error, log details, continue
       - **Unparseable responses**: Mark as tie or error, don't crash
       - **"I don't know" responses**: Mark as tie
       - **Timeouts**: Fail after max retries
     - Parse response for winner, scores, reasoning
   - Raise ComparisonError only for fatal errors (auth failure, etc.)
   - Log non-fatal errors, continue with remaining queries

3. **Result Aggregation**
   - Count wins/ties/losses per system
   - Calculate win percentages
   - Create EvaluationResult for each query
   - Store in Comparison model

4. **File Storage**
   - Save Comparison to `domains/<domain>/comparisons/YYYY-MM-DD/<comparison-id>.json`
   - Pretty JSON formatting

5. **Output Formatting**
   - JSON formatter (default)
   - Markdown formatter (table + details)
   - Table formatter (summary only)

6. **Comparison Loading**
   - `load_comparison(domain: str, comparison_id: str) -> Comparison`
   - Support UUID/prefix like runs

### Success Criteria

- [ ] Can compare 2 runs from same domain
- [ ] LLM evaluation working with Claude
- [ ] Evaluator config loaded from domain
- [ ] Prompt template interpolation working
- [ ] Results aggregated correctly
- [ ] Comparison saved with evaluator snapshot
- [ ] JSON output format works
- [ ] Markdown output format works
- [ ] Can handle ties
- [ ] Clear error if runs from different domains
- [ ] Can load comparison by UUID/prefix

### Test Coverage

- Unit test for compare_runs with mock LLM
- Integration test with real LLM
- Test same-domain validation
- Test same-query-set validation
- Test prompt template formatting
- Test result aggregation (wins/ties/losses)
- Test all output formats
- Test comparison loading
- Test error handling (API errors, invalid response)

### Evaluation Criteria

- All tests pass
- LLM integration works reliably
- Output formats are readable
- Comparisons are reproducible (evaluator snapshot)
- Error handling is robust
- No API key leaks in output

### Phase Commit

```
[Spec 0006][Phase 4] feat: Comparison engine with LLM evaluation

- Compare runs using domain evaluator config
- LLM-based evaluation with Claude
- Result aggregation (wins/ties/losses)
- Multiple output formats (JSON, markdown, table)
- Evaluator config snapshotting
- Comparison loading by UUID/prefix
```

---

## Phase 5: CLI Commands

**Objective**: Provide user-friendly CLI for run and compare operations.

**Dependencies**: Phase 3 (run execution), Phase 4 (comparison)

### Tasks

1. **CLI Setup**
   - Convert to Typer-based CLI
   - Main app with subcommands
   - Version command
   - Help text

2. **Run Command**
   - `ragdiff run <domain> <system> <query-set>` command
   - `--verbose` flag for progress
   - `--dry-run` flag for validation only
   - `--output` flag for custom path
   - Progress bar using rich or tqdm
   - Pretty output with tree structure (├─, └─)
   - Print run ID and summary

3. **Compare Command**
   - `ragdiff compare --domain <domain> <run-id-1> <run-id-2>` command
   - `--format` flag (json, markdown, table)
   - `--output` flag for custom path
   - `--verbose` flag
   - Support short UUID prefixes
   - Support aliases (@latest, @2)
   - Progress bar for evaluation
   - Pretty output

4. **Utility Commands**
   - `ragdiff list-domains` - list all domains
   - `ragdiff list-systems <domain>` - list systems in domain
   - `ragdiff list-query-sets <domain>` - list query sets
   - `ragdiff list-runs <domain>` - list recent runs
   - `ragdiff show-run <run-id>` - show run details
   - `ragdiff show-comparison <comparison-id>` - show comparison details

5. **Error Handling**
   - Catch exceptions from library functions
   - Display user-friendly error messages
   - Exit codes (0 = success, 1 = error)
   - Suggestions for common errors

6. **Update pyproject.toml**
   - Entry point: `ragdiff = "ragdiff.cli:app"`
   - Ensure all dependencies included

### Success Criteria

- [ ] `ragdiff run` command works end-to-end
- [ ] `ragdiff compare` command works end-to-end
- [ ] All utility commands work
- [ ] Progress bars display correctly
- [ ] Output formatting is clean and readable
- [ ] Short UUID prefixes work
- [ ] Aliases (@latest) work
- [ ] Error messages are helpful
- [ ] Help text is clear
- [ ] Can install and run CLI globally

### Test Coverage

- CLI tests using Typer testing utilities
- Test all commands with valid inputs
- Test error handling (missing files, invalid UUIDs, etc.)
- Test short UUID resolution
- Test alias resolution
- Test output formatting
- Test dry-run mode
- Integration tests for full workflows

### Evaluation Criteria

- All tests pass
- CLI is intuitive to use
- Error messages are actionable
- Output is visually appealing
- No crashes on invalid input
- Help text is comprehensive

### Phase Commit

```
[Spec 0006][Phase 5] feat: CLI commands with Typer

- run command with progress reporting
- compare command with output formatting
- Utility commands (list-*, show-*)
- Short UUID prefix support
- Alias support (@latest, @2)
- Rich progress bars and pretty output
- Comprehensive error handling
```

---

## Phase 6: Migration & Documentation

**Objective**: Help users migrate from v1.x and document the new system.

**Dependencies**: Phase 5 (complete working system)

### Tasks

1. **Migration Helper** (optional)
   - `ragdiff migrate from-v1 <config-file> --domain <domain>` command
   - Parse v1.x config
   - Create domain.yaml
   - Create system YAML files
   - Suggest query set creation
   - Print instructions for next steps

2. **Update Documentation**
   - Update README.md:
     - Installation instructions
     - Quick start guide
     - Core concepts overview
     - CLI command reference
     - Library API examples
     - Migration guide
   - Update CLAUDE.md:
     - New project structure
     - New CLI commands
     - File organization
     - Development workflow
   - Update codev/resources/arch.md:
     - New architecture overview
     - Component descriptions
     - Data flow diagrams
     - Design decisions

3. **Example Domains**
   - Create `examples/tafsir/` domain:
     - domain.yaml
     - Sample systems (vectara-mmr, mongodb-v1)
     - Sample query sets (basic-test.txt)
     - .env.example file
   - Create `examples/legal/` domain (optional)

4. **Version Update**
   - Update version in `src/ragdiff/version.py` to `2.0.0`
   - Update CHANGELOG.md with breaking changes
   - Add migration notes

5. **Clean Up**
   - Remove deprecated v1.x code (if any)
   - Update tests to remove v1.x references
   - Archive old configs/examples

### Success Criteria

- [ ] Migration helper works (if implemented)
- [ ] README is comprehensive and up-to-date
- [ ] CLAUDE.md reflects new structure
- [ ] Architecture documentation updated
- [ ] Example domains work end-to-end
- [ ] Version bumped to 2.0.0
- [ ] CHANGELOG documents breaking changes
- [ ] No references to deprecated code

### Test Coverage

- Test migration helper with v1.x configs (if implemented)
- Verify example domains work
- Test all examples in README

### Evaluation Criteria

- Documentation is clear and complete
- Examples work without modification
- Migration path is well-documented
- No broken links or outdated info

### Phase Commit

```
[Spec 0006][Phase 6] docs: Migration guide and v2.0.0 documentation

- Migration helper from v1.x
- Updated README with v2.0.0 guide
- Updated CLAUDE.md with new structure
- Example domains (tafsir, legal)
- Version bumped to 2.0.0
- CHANGELOG with breaking changes
```

---

## Testing Strategy

### Unit Tests
- Each model has validation tests
- Each function has tests for happy path and error cases
- Mock external dependencies (file system, LLM API)

### Integration Tests
- End-to-end workflow: create domain → run → compare
- Real file I/O (use temporary directories)
- Real LLM calls (optional, with API key)

### Test Coverage Goals
- Maintain >200 total tests (current baseline)
- 90%+ coverage on core modules
- 100% coverage on critical paths (run execution, comparison)

### Test Organization
```
tests/
  test_models.py         # Pydantic model tests
  test_loaders.py        # File loading tests
  test_env_vars.py       # Environment variable tests
  test_system.py         # System ABC and registry tests
  test_tools.py          # Individual tool tests
  test_run.py            # Run execution tests
  test_comparison.py     # Comparison tests
  test_cli.py            # CLI command tests
  test_integration.py    # End-to-end tests
```

---

## Risk Mitigation

### High-Risk Areas

1. **Config Snapshotting**
   - Risk: Snapshots might not capture everything
   - Mitigation: Comprehensive tests, validate snapshots are complete

2. **LLM Evaluation**
   - Risk: API failures, rate limits, parsing errors
   - Mitigation: Robust error handling, retries, fallbacks

3. **File I/O**
   - Risk: Concurrent writes, file corruption
   - Mitigation: Atomic writes, file locking if needed

4. **Breaking Changes**
   - Risk: Users struggle with migration
   - Mitigation: Clear migration guide, examples, helper tool

### Medium-Risk Areas

1. **Environment Variables**
   - Risk: Missing vars at runtime
   - Mitigation: Fail-fast validation, clear error messages

2. **UUID Resolution**
   - Risk: Ambiguous short prefixes
   - Mitigation: Check uniqueness, error on ambiguity

---

## Success Metrics

### Functional
- [ ] All 6 phases completed and committed
- [ ] All tests passing (>200 tests)
- [ ] Can create domains, systems, query sets
- [ ] Can execute runs successfully
- [ ] Can compare runs with LLM evaluation
- [ ] CLI works end-to-end

### Non-Functional
- [ ] Test coverage >90% on core modules
- [ ] No performance regressions vs v1.x
- [ ] Clear error messages throughout
- [ ] Documentation complete and accurate
- [ ] Code follows project style guide

### User Experience
- [ ] Migration path is clear
- [ ] Examples work out-of-the-box
- [ ] CLI is intuitive
- [ ] Error messages are helpful

---

## Dependencies

- Python 3.11+ (for `| None` syntax)
- pydantic 2.x (for models)
- typer (for CLI)
- python-dotenv (for .env support)
- anthropic (for LLM evaluation)
- rich or tqdm (for progress bars)
- pyyaml (for YAML parsing)

All existing dependencies from v1.x (vectara, mongodb, etc.)

---

## Self-Review Notes

### Critical Gaps Identified

**1. Exception Hierarchy** (CRITICAL)
- **Problem**: No mention of custom exception design
- **Impact**: Error handling will be inconsistent
- **Solution**: Add to Phase 1:
  - `RagDiffError` base exception
  - `ConfigError` (missing files, invalid YAML, missing env vars)
  - `RunError` (system errors, timeouts)
  - `ComparisonError` (LLM errors, incompatible runs)
  - `ValidationError` (query limits, invalid formats)

**2. Phase 3 Too Large**
- **Problem**: Run execution engine has too many responsibilities
- **Impact**: Phase will take too long, hard to test incrementally
- **Solution**: Consider splitting into:
  - Phase 3A: Basic run execution (sequential queries, simple error handling)
  - Phase 3B: Advanced features (progress reporting, partial failures, run loading)
- **Decision**: Keep as one phase for now, but monitor during implementation

**3. Concurrency Model Undefined**
- **Problem**: No decision on parallel query execution
- **Impact**: Performance unclear, thread safety unknown
- **Solution**: Add to Phase 3 notes:
  - Start with sequential execution (simple, safe)
  - Design for future parallelization
  - Document thread-safety requirements

**4. Logging Strategy Missing**
- **Problem**: No mention of logging throughout
- **Impact**: Debugging will be difficult
- **Solution**: Add to Phase 1:
  - Configure Python logging
  - Log levels: DEBUG, INFO, WARNING, ERROR
  - Log to file and console (configurable)
  - Include in all phases going forward

**5. LLM Error Handling Incomplete**
- **Problem**: Phase 4 doesn't fully specify LLM failure modes
- **Impact**: Comparisons might fail unexpectedly
- **Solution**: Add to Phase 4:
  - Handle API rate limits (retry with backoff)
  - Handle unparseable responses (mark as error, not crash)
  - Handle "I don't know" responses (mark as tie or error)
  - Handle cost limits (fail gracefully)
  - Add max retries configuration

**6. Validation Scope Unclear**
- **Problem**: What validation happens when?
- **Impact**: Errors might be caught too late
- **Solution**: Define validation layers:
  - Load-time: YAML syntax, schema validation
  - Pre-run: System exists, query set exists, env vars present
  - Run-time: Per-query errors only
  - Fail-fast: Don't start run if config is invalid

**7. CI/CD Updates Not Mentioned**
- **Problem**: Pre-commit hooks, GitHub Actions might break
- **Impact**: CI might fail after merge
- **Solution**: Add to Phase 6:
  - Update pre-commit hooks if needed
  - Update GitHub Actions workflows
  - Test full CI pipeline before merge

**8. Shell Completion Missing**
- **Problem**: No tab completion for CLI
- **Impact**: UX could be better
- **Solution**: Add to Phase 5 (optional):
  - Typer supports auto-completion
  - Generate completion scripts for bash/zsh
  - Document installation

**9. Name Validation Missing**
- **Problem**: Domain/system/query-set names not validated
- **Impact**: Special characters could break file paths
- **Solution**: Add to Phase 1:
  - Validate names: alphanumeric, hyphens, underscores only
  - No slashes, spaces, or special chars
  - Enforce in Pydantic validators

**10. Migration Helper Complexity Unknown**
- **Problem**: Phase 6 migration helper scope unclear
- **Impact**: Might be harder than expected
- **Solution**: Mark as optional in Phase 6
  - If v1.x config is complex, might be too much work
  - Provide manual migration guide instead
  - User can always migrate manually

### Strengths

- Clear phase boundaries
- Good dependency management
- Comprehensive test coverage plans
- Each phase delivers value
- Success criteria are measurable
- No time estimates (per SPIDER-SOLO)

### Phase-Specific Notes

**Phase 1 Additions Needed**:
- Custom exception hierarchy
- Logging configuration
- Name validation (domain, system, query-set)

**Phase 3 Monitoring**:
- Watch for phase becoming too large
- Consider split if needed during implementation
- Document concurrency decisions

**Phase 4 Additions Needed**:
- LLM retry logic with backoff
- Error classification (rate limit vs. parse error)
- Cost tracking/limits

**Phase 5 Optional Additions**:
- Shell completion scripts
- JSON output mode for scripting

**Phase 6 Adjustments**:
- Mark migration helper as optional
- Add CI/CD updates
- Add pre-commit hook verification

### Updated Success Criteria

In addition to existing criteria:

- [ ] Exception hierarchy is comprehensive
- [ ] Logging works throughout
- [ ] Names are validated (no special chars)
- [ ] LLM errors handled gracefully
- [ ] Validation happens at appropriate times
- [ ] CI/CD pipelines updated and passing

### Remaining Questions

1. **Parallel execution**: Implement in v2.0.0 or defer to v2.1.0?
2. **Migration helper**: Required or optional?
3. **LLM provider**: Support only Claude or allow OpenAI/others?
4. **Cost tracking**: Log LLM costs or ignore for v2.0.0?

## Notes

- **No time estimates** - progress measured by completed phases
- Each phase is independently valuable
- Phases can be demoed to user after completion
- Test-driven development encouraged
- Commit frequently during implementation, but only one commit per phase during evaluation
- Self-review identified 10 gaps - address during implementation
