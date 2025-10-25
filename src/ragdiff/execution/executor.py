"""Run execution engine for RAGDiff v2.0.

This module executes query sets against systems and saves the results as Runs.

Key features:
- Parallel query execution with configurable concurrency
- Per-query error handling (don't crash entire run)
- Config snapshotting (preserves ${VAR_NAME} for security)
- Run state management (pending → running → completed/failed/partial)
- Progress reporting callbacks
- Atomic file writes

Example:
    >>> run = execute_run(
    ...     domain="tafsir",
    ...     system="vectara-default",
    ...     query_set="test-queries",
    ...     concurrency=10
    ... )
    >>> print(f"Run {run.id}: {run.status}, {len(run.results)} queries")
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4

from ..core.errors import RunError
from ..core.loaders import load_domain, load_query_set, load_system_for_snapshot
from ..core.logging import get_logger
from ..core.models_v2 import QueryResult, Run, RunStatus
from ..core.storage import save_run
from ..systems import create_system

logger = get_logger(__name__)

# Type alias for progress callback
ProgressCallback = Callable[[int, int, int, int], None]
# Parameters: (current_index, total_queries, successes, failures)


def execute_run(
    domain: str,
    system: str,
    query_set: str,
    concurrency: int = 10,
    per_query_timeout: float = 30.0,
    progress_callback: ProgressCallback | None = None,
    domains_dir: Path = Path("domains"),
) -> Run:
    """Execute a query set against a system and save the run.

    This function:
    1. Loads domain, system config, and query set from files
    2. Creates config snapshots (preserving ${VAR_NAME} placeholders)
    3. Creates System instance (resolving secrets)
    4. Executes queries in parallel with error handling
    5. Tracks run state (pending → running → completed/failed/partial)
    6. Saves run to file

    Args:
        domain: Domain name (e.g., "tafsir")
        system: System name (e.g., "vectara-default")
        query_set: Query set name (e.g., "test-queries")
        concurrency: Maximum number of concurrent queries (default: 10)
        per_query_timeout: Timeout per query in seconds (default: 30.0)
        progress_callback: Optional callback for progress updates
        domains_dir: Root directory containing all domains

    Returns:
        Completed Run object with all results

    Raises:
        RunError: If system initialization fails or run cannot be saved

    Example:
        >>> def progress(current, total, successes, failures):
        ...     print(f"Progress: {current}/{total} ({successes} ok, {failures} failed)")
        >>>
        >>> run = execute_run(
        ...     domain="tafsir",
        ...     system="vectara-default",
        ...     query_set="test-queries",
        ...     concurrency=10,
        ...     progress_callback=progress
        ... )
        >>> print(run.status)
        'completed'
    """
    logger.info(
        f"Starting run: domain={domain}, system={system}, query_set={query_set}, "
        f"concurrency={concurrency}"
    )

    run_id = uuid4()
    started_at = datetime.now(timezone.utc)

    try:
        # Load domain (for validation)
        load_domain(domain, domains_dir)

        # Load system config for snapshot (preserves ${VAR_NAME})
        system_config_snapshot = load_system_for_snapshot(domain, system, domains_dir)
        logger.debug(f"Loaded system config snapshot (secrets preserved)")

        # Load query set
        query_set_obj = load_query_set(domain, query_set, domains_dir)
        logger.info(f"Loaded query set with {len(query_set_obj.queries)} queries")

        # Create System instance (resolves ${VAR_NAME})
        # Note: We need to load the system config WITH resolved secrets
        from ..core.loaders import load_system
        system_config_resolved = load_system(domain, system, domains_dir)
        system_instance = create_system(system_config_resolved)
        logger.info(f"Created system instance: {system_instance}")

    except Exception as e:
        logger.error(f"Failed to initialize run: {e}")
        raise RunError(f"Failed to initialize run: {e}") from e

    # Initialize run with pending status
    run = Run(
        id=run_id,
        domain=domain,
        system=system,
        query_set=query_set,
        status=RunStatus.PENDING,
        results=[],
        system_config=system_config_snapshot,  # Snapshot with ${VAR_NAME}
        query_set_snapshot=query_set_obj,
        started_at=started_at,
        completed_at=None,
        metadata={"concurrency": concurrency, "per_query_timeout": per_query_timeout},
    )

    # Update to running status
    run.status = RunStatus.RUNNING
    logger.info(f"Run {run_id} status: RUNNING")

    # Execute queries in parallel
    results = _execute_queries_parallel(
        system_instance=system_instance,
        queries=query_set_obj.queries,
        concurrency=concurrency,
        per_query_timeout=per_query_timeout,
        progress_callback=progress_callback,
    )

    # Update run with results
    run.results = results
    run.completed_at = datetime.now(timezone.utc)

    # Determine final status
    successes = sum(1 for r in results if r.error is None)
    failures = sum(1 for r in results if r.error is not None)

    if failures == 0:
        run.status = RunStatus.COMPLETED
    elif successes == 0:
        run.status = RunStatus.FAILED
    else:
        run.status = RunStatus.PARTIAL

    logger.info(
        f"Run {run_id} completed: {run.status}, "
        f"{successes} successes, {failures} failures"
    )

    # Calculate metadata
    run.metadata.update({
        "total_queries": len(results),
        "successes": successes,
        "failures": failures,
        "duration_seconds": (run.completed_at - run.started_at).total_seconds(),
    })

    # Save run to file
    try:
        run_path = save_run(run, domains_dir)
        logger.info(f"Saved run to {run_path}")
    except Exception as e:
        logger.error(f"Failed to save run: {e}")
        raise RunError(f"Failed to save run: {e}") from e

    return run


def _execute_queries_parallel(
    system_instance,
    queries,
    concurrency: int,
    per_query_timeout: float,
    progress_callback: ProgressCallback | None,
) -> list[QueryResult]:
    """Execute queries in parallel using ThreadPoolExecutor.

    Args:
        system_instance: System instance to use for queries
        queries: List of Query objects
        concurrency: Maximum number of concurrent queries
        per_query_timeout: Timeout per query in seconds
        progress_callback: Optional progress callback

    Returns:
        List of QueryResult objects (same order as input queries)
    """
    total = len(queries)
    results = [None] * total  # Pre-allocate results list
    successes = 0
    failures = 0

    logger.info(f"Executing {total} queries with concurrency={concurrency}")

    # Create thread pool
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        # Submit all queries
        future_to_index = {}
        for i, query in enumerate(queries):
            future = executor.submit(
                _execute_single_query,
                system_instance,
                query.text,
                query.reference,
                per_query_timeout,
            )
            future_to_index[future] = i

        # Process completed queries
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            query_result = future.result()  # This won't raise since we catch in _execute_single_query

            # Store result
            results[index] = query_result

            # Update progress
            if query_result.error is None:
                successes += 1
            else:
                failures += 1

            # Call progress callback
            if progress_callback:
                progress_callback(index + 1, total, successes, failures)

    logger.info(f"Query execution complete: {successes} successes, {failures} failures")
    return results


def _execute_single_query(
    system_instance,
    query_text: str,
    reference: str | None,
    timeout: float,
) -> QueryResult:
    """Execute a single query with timeout and error handling.

    Args:
        system_instance: System instance
        query_text: Query text
        reference: Optional reference answer
        timeout: Timeout in seconds

    Returns:
        QueryResult with results or error
    """
    start_time = time.time()

    try:
        # Execute search with timeout
        # Note: ThreadPoolExecutor doesn't have built-in timeout for individual tasks,
        # so we rely on the system's internal timeout or HTTP client timeout
        retrieved = system_instance.search(query_text, top_k=5)

        duration_ms = (time.time() - start_time) * 1000

        return QueryResult(
            query=query_text,
            retrieved=retrieved,
            reference=reference,
            duration_ms=duration_ms,
            error=None,
        )

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000

        logger.warning(f"Query failed: '{query_text[:50]}...' - {e}")

        return QueryResult(
            query=query_text,
            retrieved=[],
            reference=reference,
            duration_ms=duration_ms,
            error=str(e),
        )
