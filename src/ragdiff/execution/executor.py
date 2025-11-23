"""Run execution engine for RAGDiff v2.0.

This module executes query sets against providers and saves the results as Runs.

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
    ...     provider="vectara-default",
    ...     query_set="test-queries",
    ...     concurrency=10
    ... )
    >>> print(f"Run {run.id}: {run.status}, {len(run.results)} queries")
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Union
from uuid import uuid4

from ..core.errors import RunError
from ..core.loaders import load_domain, load_provider_for_snapshot, load_query_set
from ..core.logging import get_logger
from ..core.models import (
    Domain,
    ProviderConfig,
    QueryResult,
    QuerySet,
    Run,
    RunStatus,
    SearchResult,
)
from ..core.storage import save_run
from ..providers import create_provider

logger = get_logger(__name__)

# Type alias for progress callback
ProgressCallback = Callable[[int, int, int, int], None]
# Parameters: (current_index, total_queries, successes, failures)


def execute_run(
    domain: Union[str, Domain],
    provider: Union[str, ProviderConfig],
    query_set: Union[str, QuerySet],
    label: str | None = None,
    concurrency: int = 10,
    per_query_timeout: float = 30.0,
    progress_callback: ProgressCallback | None = None,
    domains_dir: Path = Path("domains"),
) -> Run:
    """Execute a query set against a system and save the run.

    This function supports both file-based and object-based configuration:
    1. File-based: Loads domain, system config, and query set from files
    2. Object-based: Uses provided configuration objects directly
    3. Creates config snapshots (preserving ${VAR_NAME} placeholders)
    4. Creates System instance (resolving secrets)
    5. Executes queries in parallel with error handling
    6. Tracks run state (pending → running → completed/failed/partial)
    7. Saves run to file

    Args:
        domain: Domain name (str) to load from files, or Domain object
        provider: Provider name (str) to load from files, or ProviderConfig object
        query_set: Query set name (str) to load from files, or QuerySet object
        label: Optional label for the run (auto-generated if not provided)
        concurrency: Maximum number of concurrent queries (default: 10)
        per_query_timeout: Timeout per query in seconds (default: 30.0)
        progress_callback: Optional callback for progress updates
        domains_dir: Root directory containing all domains (only used for string parameters)

    Returns:
        Completed Run object with all results

    Raises:
        RunError: If provider initialization fails or run cannot be saved

    Examples:
        File-based (existing usage):
        >>> run = execute_run(
        ...     domain="tafsir",
        ...     provider="vectara-default",
        ...     query_set="test-queries"
        ... )

        Object-based (new usage for web apps):
        >>> domain_obj = Domain(name="tafsir", evaluator={...})
        >>> provider_obj = ProviderConfig(name="vectara", tool="vectara", config={...})
        >>> query_set_obj = QuerySet(name="queries", domain="tafsir", queries=[...])
        >>> run = execute_run(domain_obj, provider_obj, query_set_obj)

        Hybrid (mix strings and objects):
        >>> run = execute_run(domain_obj, "vectara-backup", query_set_obj)
    """
    logger.info(
        f"Starting run: domain={domain}, provider={provider}, query_set={query_set}, "
        f"concurrency={concurrency}"
    )

    run_id = uuid4()
    started_at = datetime.now(timezone.utc)

    # Extract names for use throughout function
    domain_name = domain if isinstance(domain, str) else domain.name
    provider_name = provider if isinstance(provider, str) else provider.name
    query_set_name = query_set if isinstance(query_set, str) else query_set.name

    # Generate label if not provided
    if label is None:
        from ..core.storage import generate_run_label

        date_str = started_at.strftime("%Y-%m-%d")
        label = generate_run_label(domain_name, provider_name, date_str, domains_dir)
        logger.info(f"Auto-generated label: {label}")

    try:
        # Load or use provided domain configuration
        if isinstance(domain, str):
            # Validate domain exists (we only need the name)
            load_domain(domain, domains_dir)
            domain_name = domain
        else:
            domain_name = domain.name
            logger.debug(f"Using provided Domain object: {domain_name}")

        # Load or use provided provider configuration
        if isinstance(provider, str):
            # Load provider config for snapshot (preserves ${VAR_NAME})
            provider_config_snapshot = load_provider_for_snapshot(
                domain_name, provider, domains_dir
            )
            provider_name = provider
            logger.debug("Loaded provider config snapshot (secrets preserved)")

            # Load provider config WITH resolved secrets for creating instance
            from ..core.loaders import load_provider

            provider_config_resolved = load_provider(domain_name, provider, domains_dir)
        else:
            # Use provided ProviderConfig object
            provider_config_snapshot = provider
            provider_config_resolved = provider
            provider_name = provider.name
            logger.debug(f"Using provided ProviderConfig object: {provider_name}")

        # Load or use provided query set
        if isinstance(query_set, str):
            query_set_obj = load_query_set(domain_name, query_set, domains_dir)
            query_set_name = query_set
            logger.info(f"Loaded query set with {len(query_set_obj.queries)} queries")
        else:
            query_set_obj = query_set
            query_set_name = query_set.name
            logger.info(
                f"Using provided QuerySet object with {len(query_set_obj.queries)} queries"
            )

        # Validate query set domain matches execution domain
        if query_set_obj.domain != domain_name:
            raise RunError(
                f"Query set domain '{query_set_obj.domain}' does not match "
                f"execution domain '{domain_name}'"
            )

        # Create Provider instance (resolves ${VAR_NAME})
        provider_instance = create_provider(provider_config_resolved)
        logger.info(f"Created provider instance: {provider_instance}")

    except Exception as e:
        logger.error(f"Failed to initialize run: {e}")
        raise RunError(f"Failed to initialize run: {e}") from e

    # Initialize run with pending status
    # specific model name extraction
    model_name = None
    if provider_config_resolved and provider_config_resolved.config:
        # Try common keys for model name
        for key in ["model", "model_name", "embedding_model", "llm_model"]:
            if key in provider_config_resolved.config:
                model_name = provider_config_resolved.config[key]
                break

    run = Run(
        id=run_id,
        label=label,
        domain=domain_name,
        provider=provider_name,
        query_set=query_set_name,
        status=RunStatus.PENDING,
        results=[],
        model_name=model_name,
        provider_config=provider_config_snapshot,  # Snapshot with ${VAR_NAME}
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
        provider_instance=provider_instance,
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
    total_cost = sum((r.cost or 0.0) for r in results)
    avg_latency = sum(r.duration_ms for r in results) / len(results) if results else 0.0

    run.metadata.update(
        {
            "total_queries": len(results),
            "successes": successes,
            "failures": failures,
            "duration_seconds": (run.completed_at - run.started_at).total_seconds(),
            "total_cost": total_cost,
            "avg_latency_ms": avg_latency,
        }
    )

    # Save run to file
    try:
        run_path = save_run(run, domains_dir)
        logger.info(f"Saved run to {run_path}")
    except Exception as e:
        logger.error(f"Failed to save run: {e}")
        raise RunError(f"Failed to save run: {e}") from e

    return run


def _execute_queries_parallel(
    provider_instance,
    queries,
    concurrency: int,
    per_query_timeout: float,
    progress_callback: ProgressCallback | None,
) -> list[QueryResult]:
    """Execute queries in parallel using ThreadPoolExecutor.

    Args:
        provider_instance: System instance to use for queries
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
                provider_instance,
                query.text,
                query.reference,
                per_query_timeout,
            )
            future_to_index[future] = i

        # Process completed queries
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            query_result = (
                future.result()
            )  # This won't raise since we catch in _execute_single_query

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
    provider_instance,
    query_text: str,
    reference: str | None,
    timeout: float,
) -> QueryResult:
    """Execute a single query with timeout and error handling.

    Args:
        provider_instance: System instance
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
        result = provider_instance.search(query_text, top_k=5)

        duration_ms = (time.time() - start_time) * 1000

        # Handle both list (legacy) and SearchResult (new) return types
        if isinstance(result, SearchResult):
            retrieved = result.chunks
            cost = result.cost
            total_tokens_returned = result.total_tokens_returned
        else:
            # Legacy behavior: provider returns list of RetrievedChunk
            retrieved = result
            cost = None
            total_tokens_returned = sum(
                c.token_count for c in retrieved if c.token_count is not None
            )

        return QueryResult(
            query=query_text,
            retrieved=retrieved,
            reference=reference,
            duration_ms=duration_ms,
            cost=cost,
            total_tokens_returned=total_tokens_returned,
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
