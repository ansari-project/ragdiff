# TICK Spec: Evaluation Parallelization Support

**ID**: 0007
**Created**: 2025-10-26
**Status**: 🔄 In Progress
**Protocol**: TICK

---

## T - Task/Specification

### Problem
Currently, the comparison/evaluation engine processes queries sequentially when comparing runs. For large query sets (100+ queries), this can be slow:
- Each query requires an LLM API call (which can take 1-5 seconds)
- With 100 queries, sequential processing takes 100-500 seconds (1.6-8.3 minutes)
- The run execution already supports parallel processing with `--concurrency` flag
- Evaluation should also support parallelization for consistency and performance

### Solution
Add parallelization support to the evaluation engine using ThreadPoolExecutor (similar to run execution):
1. Add `concurrency` parameter to `compare_runs()` function
2. Modify `_evaluate_all_queries()` to process queries in parallel
3. Add `--concurrency` CLI flag to `ragdiff compare` command
4. Add progress reporting for parallel evaluations
5. Maintain error handling (per-query failures don't crash entire comparison)

### Example Use Case
```bash
# Sequential evaluation (current behavior, default)
uv run ragdiff compare tafsir abc123 def456
# Takes 300s for 100 queries

# Parallel evaluation with 10 concurrent evaluations
uv run ragdiff compare tafsir abc123 def456 --concurrency 10
# Takes 30-40s for 100 queries (10x faster)

# Maximum parallelization
uv run ragdiff compare tafsir abc123 def456 --concurrency 50
# Limited by API rate limits
```

### Success Criteria
1. `compare_runs()` accepts `concurrency` parameter (default: 1 for backward compatibility)
2. Evaluations run in parallel using ThreadPoolExecutor
3. CLI has `--concurrency` flag with reasonable default (e.g., 5)
4. Progress bar shows real-time evaluation progress
5. Error handling: individual evaluation failures don't crash comparison
6. Test coverage for parallel evaluation
7. All existing tests still pass
8. Documentation updated with parallelization examples

---

## I - Implementation

### Changes Required

#### 1. Update `compare_runs()` signature (src/ragdiff/comparison/evaluator.py)
Add concurrency parameter:
```python
def compare_runs(
    domain: str,
    run_ids: list[str | UUID],
    model: str | None = None,
    temperature: float | None = None,
    max_retries: int = 3,
    concurrency: int = 1,  # NEW: default to sequential for backward compat
    progress_callback: Callable[[int, int, int, int], None] | None = None,  # NEW
    domains_dir: Path = Path("domains"),
) -> Comparison:
```

#### 2. Update `_evaluate_all_queries()` (src/ragdiff/comparison/evaluator.py)
Add parallel execution using ThreadPoolExecutor:
```python
def _evaluate_all_queries(
    runs,
    evaluator_config: EvaluatorConfig,
    max_retries: int,
    concurrency: int,  # NEW
    progress_callback: Callable[[int, int, int, int], None] | None,  # NEW
) -> list[EvaluationResult]:
    """Evaluate all queries across runs (parallel or sequential)."""
    query_set = runs[0].query_set_snapshot
    total_queries = len(query_set.queries)

    if concurrency == 1:
        # Sequential execution (current behavior)
        return _evaluate_queries_sequential(...)
    else:
        # Parallel execution (new)
        return _evaluate_queries_parallel(...)
```

#### 3. Add `_evaluate_queries_parallel()` (src/ragdiff/comparison/evaluator.py)
Similar pattern to executor.py's `_execute_queries_parallel()`:
```python
def _evaluate_queries_parallel(
    runs,
    queries,
    evaluator_config: EvaluatorConfig,
    max_retries: int,
    concurrency: int,
    progress_callback: Callable[[int, int, int, int], None] | None,
) -> list[EvaluationResult]:
    """Execute evaluations in parallel using ThreadPoolExecutor."""
    total = len(queries)
    results = [None] * total  # Pre-allocate results list
    successes = 0
    failures = 0

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        # Submit all evaluations
        future_to_index = {}
        for i, query in enumerate(queries):
            # Gather results from all runs for this query
            run_results = {}
            for run in runs:
                matching_results = [r for r in run.results if r.query == query.text]
                if matching_results:
                    run_results[run.system] = matching_results[0].retrieved

            future = executor.submit(
                _evaluate_single_query,
                query.text,
                query.reference,
                run_results,
                evaluator_config,
                max_retries,
            )
            future_to_index[future] = i

        # Process completed evaluations
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            evaluation_result = future.result()

            # Store result
            results[index] = evaluation_result

            # Update progress
            if "error" not in evaluation_result.evaluation:
                successes += 1
            else:
                failures += 1

            # Call progress callback
            if progress_callback:
                progress_callback(index + 1, total, successes, failures)

    return results
```

#### 4. Add `_evaluate_queries_sequential()` (src/ragdiff/comparison/evaluator.py)
Extract current sequential logic:
```python
def _evaluate_queries_sequential(
    runs,
    queries,
    evaluator_config: EvaluatorConfig,
    max_retries: int,
    progress_callback: Callable[[int, int, int, int], None] | None,
) -> list[EvaluationResult]:
    """Execute evaluations sequentially (current behavior)."""
    # Move existing loop logic here
    # ...
```

#### 5. Update CLI `compare` command (src/ragdiff/cli.py)
Add concurrency option:
```python
@app.command()
def compare(
    domain: str = typer.Argument(..., help="Domain name (e.g., 'tafsir')"),
    run_ids: list[str] = typer.Argument(...),
    model: Optional[str] = typer.Option(None, help="LLM model override"),
    temperature: Optional[float] = typer.Option(None, help="Temperature override"),
    concurrency: int = typer.Option(5, help="Maximum concurrent evaluations"),  # NEW
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
    format: str = typer.Option("table", "--format", "-f"),
    domains_dir: Optional[Path] = typer.Option(None),
    quiet: bool = typer.Option(False, "--quiet", "-q"),
):
```

#### 6. Add progress reporting (src/ragdiff/cli.py)
Show evaluation progress in CLI:
```python
if not quiet:
    with Progress(...) as progress:
        task = progress.add_task("Evaluating queries", total=100)

        def progress_callback(current, total, successes, failures):
            progress.update(
                task,
                completed=current,
                total=total,
                description=f"Evaluation {current}/{total} ({successes} ok, {failures} failed)",
            )

        result = compare_runs(
            domain=domain,
            run_ids=run_ids,
            concurrency=concurrency,
            progress_callback=progress_callback,
            ...
        )
```

### Files to Modify
- `src/ragdiff/comparison/evaluator.py` - Add parallel evaluation logic
- `src/ragdiff/cli.py` - Add --concurrency flag and progress reporting
- `tests/test_comparison.py` - Add tests for parallel evaluation
- `CLAUDE.md` - Document parallelization option in compare command
- `README.md` - Add examples of parallel evaluation (if README exists)

---

## C - Check/Testing

### Test Cases

#### 1. **Parallel Evaluation Correctness**
   - Parallel results match sequential results (same evaluations)
   - Results maintain query order (index-based storage)
   - All queries evaluated exactly once

#### 2. **Concurrency Control**
   - concurrency=1 uses sequential path
   - concurrency>1 uses parallel path
   - ThreadPoolExecutor respects max_workers limit

#### 3. **Error Handling**
   - Individual evaluation failures don't crash comparison
   - Failed evaluations marked with error in result
   - Successful evaluations continue despite failures

#### 4. **Progress Callback**
   - Callback invoked for each completed evaluation
   - Parameters correct: (current, total, successes, failures)
   - Progress monotonically increases

#### 5. **Backward Compatibility**
   - Existing code calling compare_runs() without concurrency param works
   - Default concurrency=1 maintains sequential behavior
   - All existing tests pass without modification

### Unit Tests (tests/test_comparison.py)
```python
def test_parallel_evaluation_correctness():
    """Parallel evaluation produces same results as sequential."""
    # Compare concurrency=1 vs concurrency=5 results
    # Assert evaluations are identical (modulo ordering)
    pass

def test_parallel_evaluation_error_handling():
    """Individual evaluation errors don't crash comparison."""
    # Mock LLM to fail on some queries
    # Assert comparison completes with partial results
    pass

def test_progress_callback_invoked():
    """Progress callback called for each evaluation."""
    # Track callback invocations
    # Assert called len(queries) times
    pass

def test_concurrency_default():
    """Default concurrency=1 for backward compatibility."""
    # Call compare_runs() without concurrency param
    # Assert uses sequential path
    pass
```

### Integration Tests
```python
def test_cli_concurrency_flag():
    """CLI --concurrency flag passed to compare_runs()."""
    # Run: ragdiff compare domain run1 run2 --concurrency 10
    # Assert concurrency parameter set correctly
    pass

def test_parallel_evaluation_performance():
    """Parallel evaluation faster than sequential for large query sets."""
    # Create comparison with 50 queries
    # Compare time: concurrency=1 vs concurrency=10
    # Assert parallel is significantly faster (>5x)
    pass
```

### Manual Testing
```bash
# Test sequential (default)
uv run ragdiff compare tafsir run1 run2

# Test parallel with progress
uv run ragdiff compare tafsir run1 run2 --concurrency 10

# Test with quiet mode
uv run ragdiff compare tafsir run1 run2 --concurrency 10 --quiet

# Test error handling (with invalid run IDs)
uv run ragdiff compare tafsir invalid1 invalid2 --concurrency 10
```

---

## K - Knowledge/Documentation

### Configuration/Usage

Add to CLAUDE.md under "Compare Command":

```bash
# Sequential evaluation (default for backward compatibility)
uv run ragdiff compare tafsir abc123 def456

# Parallel evaluation (recommended for large query sets)
uv run ragdiff compare tafsir abc123 def456 --concurrency 10

# Maximum parallelization (may hit API rate limits)
uv run ragdiff compare tafsir abc123 def456 --concurrency 50

# With all options
uv run ragdiff compare tafsir abc123 def456 \
  --concurrency 10 \
  --model gpt-4 \
  --format json \
  --output comparison.json
```

### Performance Guidance

**When to use parallelization:**
- Large query sets (>20 queries)
- Fast LLM APIs with high rate limits
- Multiple runs being compared (more work per query)

**When to use sequential:**
- Small query sets (<10 queries)
- APIs with strict rate limits
- Debugging (easier to trace issues)

**Recommended concurrency values:**
- Default: 5 (balanced performance/reliability)
- OpenAI/Anthropic: 10-20 (high rate limits)
- Local/self-hosted LLMs: 50+ (no rate limits)
- Rate-limited APIs: 1-5 (avoid throttling)

### Design Rationale

**Why default to concurrency=1:**
- Backward compatibility with existing code
- Safer default (no rate limit issues)
- Easier debugging for new users

**Why use ThreadPoolExecutor:**
- Consistent with run execution engine
- Simple, proven approach
- Good for I/O-bound LLM API calls
- Python GIL not an issue (waiting on network)

**Why support sequential path:**
- Debugging (simpler to trace)
- Very small query sets (overhead not worth it)
- Strict rate-limited APIs

**Why add progress callback:**
- Consistent API with execute_run()
- Enables real-time progress reporting in CLI
- Useful for monitoring long-running comparisons

### Migration Guide
- No migration needed - fully backward compatible
- Existing calls to `compare_runs()` work unchanged
- Add `concurrency` parameter to improve performance
- CLI users: add `--concurrency` flag for faster comparisons
