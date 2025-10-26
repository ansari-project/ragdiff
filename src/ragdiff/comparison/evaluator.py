"""Comparison engine for RAGDiff v2.0.

This module compares runs using LLM evaluation via LiteLLM.

Key features:
- Load and compare multiple runs
- LLM evaluation using LiteLLM (supports 100+ providers)
- Retry logic with exponential backoff
- Cost tracking per evaluation
- Error handling (per-query evaluation errors don't crash)
- Comparison file storage

Example:
    >>> comparison = compare_runs(
    ...     domain="tafsir",
    ...     run_ids=["550e8400-...", "660e8400-..."],
    ...     model="claude-3-5-sonnet-20241022"
    ... )
    >>> print(f"Comparison {comparison.id}: {len(comparison.evaluations)} evaluations")
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import UUID, uuid4

from ..core.errors import ComparisonError
from ..core.loaders import load_domain
from ..core.logging import get_logger
from ..core.models_v2 import Comparison, EvaluationResult, EvaluatorConfig
from ..core.storage import load_run, save_comparison

logger = get_logger(__name__)

# Try to import LiteLLM
try:
    import litellm

    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    logger.warning(
        "LiteLLM not installed. Install with: pip install litellm. "
        "Comparison functionality will not work without it."
    )


def compare_runs(
    domain: str,
    run_ids: list[str | UUID],
    label: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_retries: int = 3,
    concurrency: int = 1,
    progress_callback: Callable[[int, int, int, int], None] | None = None,
    domains_dir: Path = Path("domains"),
) -> Comparison:
    """Compare multiple runs using LLM evaluation.

    This function:
    1. Loads all runs from disk
    2. Validates runs are from the same domain and query set
    3. Loads domain evaluator config (or uses provided model/temperature)
    4. For each query, evaluates results from all runs using LLM
    5. Tracks costs per evaluation
    6. Saves comparison to file

    Args:
        domain: Domain name (e.g., "tafsir")
        run_ids: List of run IDs (full UUID or short prefix)
        model: Optional LLM model override (default: use domain evaluator config)
        temperature: Optional temperature override (default: use domain evaluator config)
        max_retries: Maximum retries for LLM calls (default: 3)
        concurrency: Maximum number of concurrent evaluations (default: 1 for sequential)
        progress_callback: Optional callback for progress updates (current, total, successes, failures)
        domains_dir: Root directory containing all domains

    Returns:
        Comparison object with evaluation results

    Raises:
        ComparisonError: If runs are from different domains, query sets don't match,
                        or LiteLLM is not available

    Example:
        >>> comparison = compare_runs(
        ...     domain="tafsir",
        ...     run_ids=["550e", "660e"],  # Short prefixes work
        ...     model="claude-3-5-sonnet-20241022"
        ... )
        >>> for eval in comparison.evaluations:
        ...     print(f"Query: {eval.query}")
        ...     print(f"Winner: {eval.evaluation.get('winner')}")
    """
    if not LITELLM_AVAILABLE:
        raise ComparisonError(
            "LiteLLM is required for comparisons. Install with: pip install litellm"
        )

    logger.info(
        f"Starting comparison: domain={domain}, run_ids={run_ids}, model={model}"
    )

    comparison_id = uuid4()
    created_at = datetime.now(timezone.utc)

    # Generate label if not provided
    if label is None:
        from ..core.storage import generate_comparison_label

        date_str = created_at.strftime("%Y-%m-%d")
        label = generate_comparison_label(domain, date_str, domains_dir)
        logger.info(f"Auto-generated label: {label}")

    try:
        # Load domain
        domain_obj = load_domain(domain, domains_dir)

        # Load all runs
        runs = []
        run_uuids = []
        for run_id in run_ids:
            run = load_run(domain, run_id, domains_dir)
            runs.append(run)
            run_uuids.append(run.id)

        logger.info(f"Loaded {len(runs)} runs")

        # Validate runs are from same domain
        if not all(r.domain == domain for r in runs):
            domains = {r.domain for r in runs}
            raise ComparisonError(
                f"Cannot compare runs from different domains: {domains}"
            )

        # Validate runs use compatible query sets
        query_set_names = {r.query_set for r in runs}
        if len(query_set_names) > 1:
            raise ComparisonError(
                f"Cannot compare runs with different query sets: {query_set_names}"
            )

        # Get evaluator config
        if model or temperature is not None:
            # Use provided overrides
            evaluator_config = EvaluatorConfig(
                model=model or domain_obj.evaluator.model,
                temperature=(
                    temperature
                    if temperature is not None
                    else domain_obj.evaluator.temperature
                ),
                prompt_template=domain_obj.evaluator.prompt_template,
            )
        else:
            # Use domain evaluator config
            evaluator_config = domain_obj.evaluator

        logger.info(f"Using evaluator: model={evaluator_config.model}")

    except ComparisonError:
        raise
    except Exception as e:
        logger.error(f"Failed to initialize comparison: {e}")
        raise ComparisonError(f"Failed to initialize comparison: {e}") from e

    # Evaluate each query
    evaluations = _evaluate_all_queries(
        runs=runs,
        evaluator_config=evaluator_config,
        max_retries=max_retries,
        concurrency=concurrency,
        progress_callback=progress_callback,
    )

    # Create comparison object
    comparison = Comparison(
        id=comparison_id,
        label=label,
        domain=domain,
        runs=run_uuids,
        evaluations=evaluations,
        evaluator_config=evaluator_config,
        created_at=created_at,
        metadata={
            "total_evaluations": len(evaluations),
            "successful_evaluations": sum(
                1 for e in evaluations if "error" not in e.evaluation
            ),
            "failed_evaluations": sum(
                1 for e in evaluations if "error" in e.evaluation
            ),
        },
    )

    # Save comparison to file
    try:
        comparison_path = save_comparison(comparison, domains_dir)
        logger.info(f"Saved comparison to {comparison_path}")
    except Exception as e:
        logger.error(f"Failed to save comparison: {e}")
        raise ComparisonError(f"Failed to save comparison: {e}") from e

    return comparison


def _evaluate_all_queries(
    runs,
    evaluator_config: EvaluatorConfig,
    max_retries: int,
    concurrency: int,
    progress_callback: Callable[[int, int, int, int], None] | None,
) -> list[EvaluationResult]:
    """Evaluate all queries across runs (parallel or sequential).

    Args:
        runs: List of Run objects
        evaluator_config: Evaluator configuration
        max_retries: Maximum retries for LLM calls
        concurrency: Maximum concurrent evaluations (1 = sequential)
        progress_callback: Optional progress callback

    Returns:
        List of EvaluationResult objects
    """
    # Get query set from first run (all runs have same query set)
    query_set = runs[0].query_set_snapshot
    total_queries = len(query_set.queries)

    logger.info(
        f"Evaluating {total_queries} queries across {len(runs)} runs "
        f"(concurrency={concurrency})"
    )

    if concurrency == 1:
        # Sequential execution
        return _evaluate_queries_sequential(
            runs=runs,
            queries=query_set.queries,
            evaluator_config=evaluator_config,
            max_retries=max_retries,
            progress_callback=progress_callback,
        )
    else:
        # Parallel execution
        return _evaluate_queries_parallel(
            runs=runs,
            queries=query_set.queries,
            evaluator_config=evaluator_config,
            max_retries=max_retries,
            concurrency=concurrency,
            progress_callback=progress_callback,
        )


def _evaluate_queries_sequential(
    runs,
    queries,
    evaluator_config: EvaluatorConfig,
    max_retries: int,
    progress_callback: Callable[[int, int, int, int], None] | None,
) -> list[EvaluationResult]:
    """Execute evaluations sequentially (original behavior).

    Args:
        runs: List of Run objects
        queries: List of Query objects
        evaluator_config: Evaluator configuration
        max_retries: Maximum retries for LLM calls
        progress_callback: Optional progress callback

    Returns:
        List of EvaluationResult objects
    """
    evaluations = []
    total_queries = len(queries)
    successes = 0
    failures = 0

    for i, query in enumerate(queries):
        logger.debug(f"Evaluating query {i+1}/{total_queries}: {query.text[:50]}...")

        # Gather results from all runs for this query
        run_results = {}
        for run in runs:
            # Find matching result for this query
            matching_results = [r for r in run.results if r.query == query.text]
            if matching_results:
                run_results[run.provider] = matching_results[0].retrieved

        # Evaluate this query
        evaluation_result = _evaluate_single_query(
            query=query.text,
            reference=query.reference,
            run_results=run_results,
            evaluator_config=evaluator_config,
            max_retries=max_retries,
        )

        evaluations.append(evaluation_result)

        # Update progress
        if "error" not in evaluation_result.evaluation:
            successes += 1
        else:
            failures += 1

        # Call progress callback
        if progress_callback:
            progress_callback(i + 1, total_queries, successes, failures)

    logger.info(f"Completed {len(evaluations)} evaluations")
    return evaluations


def _evaluate_queries_parallel(
    runs,
    queries,
    evaluator_config: EvaluatorConfig,
    max_retries: int,
    concurrency: int,
    progress_callback: Callable[[int, int, int, int], None] | None,
) -> list[EvaluationResult]:
    """Execute evaluations in parallel using ThreadPoolExecutor.

    Args:
        runs: List of Run objects
        queries: List of Query objects
        evaluator_config: Evaluator configuration
        max_retries: Maximum retries for LLM calls
        concurrency: Maximum number of concurrent evaluations
        progress_callback: Optional progress callback

    Returns:
        List of EvaluationResult objects (in same order as queries)
    """
    total = len(queries)
    results = [None] * total  # Pre-allocate results list
    successes = 0
    failures = 0

    logger.info(f"Executing {total} evaluations with concurrency={concurrency}")

    # Create thread pool
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        # Submit all evaluations
        future_to_index = {}
        for i, query in enumerate(queries):
            # Gather results from all runs for this query
            run_results = {}
            for run in runs:
                # Find matching result for this query
                matching_results = [r for r in run.results if r.query == query.text]
                if matching_results:
                    run_results[run.provider] = matching_results[0].retrieved

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

    logger.info(f"Evaluation complete: {successes} successes, {failures} failures")
    return results


def _evaluate_single_query(
    query: str,
    reference: str | None,
    run_results: dict,
    evaluator_config: EvaluatorConfig,
    max_retries: int,
) -> EvaluationResult:
    """Evaluate a single query using LLM.

    Args:
        query: Query text
        reference: Optional reference answer
        run_results: Dict mapping system name -> list[RetrievedChunk]
        evaluator_config: Evaluator configuration
        max_retries: Maximum retries

    Returns:
        EvaluationResult with evaluation or error
    """
    # Format prompt
    prompt = _format_evaluation_prompt(
        query=query,
        reference=reference,
        run_results=run_results,
        prompt_template=evaluator_config.prompt_template,
    )

    # Call LLM with retry logic
    evaluation = _call_llm_with_retry(
        prompt=prompt,
        model=evaluator_config.model,
        temperature=evaluator_config.temperature,
        max_retries=max_retries,
    )

    return EvaluationResult(
        query=query,
        reference=reference,
        run_results=run_results,
        evaluation=evaluation,
    )


def _format_evaluation_prompt(
    query: str,
    reference: str | None,
    run_results: dict,
    prompt_template: str,
) -> str:
    """Format the evaluation prompt.

    Args:
        query: Query text
        reference: Optional reference answer
        run_results: Dict mapping system name -> list[RetrievedChunk]
        prompt_template: Prompt template string

    Returns:
        Formatted prompt
    """
    # Build results section
    results_text = ""
    for provider_name, chunks in run_results.items():
        results_text += f"\n\n## System: {provider_name}\n"
        if chunks:
            for i, chunk in enumerate(chunks, 1):
                score_text = f" (score: {chunk.score:.3f})" if chunk.score else ""
                results_text += f"{i}. {chunk.content[:200]}...{score_text}\n"
        else:
            results_text += "No results\n"

    # Format template
    # Simple replacement for now - could be extended with Jinja2 later
    prompt = prompt_template.replace("{query}", query)
    prompt = prompt.replace("{results}", results_text)

    if reference:
        prompt = prompt.replace("{reference}", f"\n\nReference Answer:\n{reference}\n")
    else:
        prompt = prompt.replace("{reference}", "")

    return prompt


def _call_llm_with_retry(
    prompt: str,
    model: str,
    temperature: float,
    max_retries: int,
) -> dict[str, Any]:
    """Call LLM with retry logic and cost tracking.

    Args:
        prompt: Prompt text
        model: Model name (LiteLLM format)
        temperature: Temperature
        max_retries: Maximum retries

    Returns:
        Dict with evaluation results and metadata (cost, tokens, etc.)
    """
    for attempt in range(max_retries + 1):
        try:
            start_time = time.time()

            # Call LiteLLM
            response = litellm.completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )

            duration_ms = (time.time() - start_time) * 1000

            # Extract response
            content = response.choices[0].message.content

            # Calculate cost
            try:
                cost = litellm.completion_cost(completion_response=response)
            except Exception as e:
                logger.warning(f"Failed to calculate cost: {e}")
                cost = 0.0

            # Parse response (simple JSON parsing for now)
            try:
                import json

                evaluation = json.loads(content)
            except json.JSONDecodeError:
                # If not JSON, treat as raw text
                evaluation = {
                    "response": content,
                    "winner": "unknown",
                    "reasoning": content,
                }

            # Add metadata
            evaluation["_metadata"] = {
                "model": model,
                "temperature": temperature,
                "duration_ms": duration_ms,
                "cost": cost,
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

            logger.debug(
                f"LLM evaluation successful: cost=${cost:.4f}, "
                f"tokens={response.usage.total_tokens}"
            )

            return evaluation

        except Exception as e:
            if attempt < max_retries:
                # Exponential backoff: 2s, 4s, 8s
                wait_time = 2**attempt
                logger.warning(
                    f"LLM call failed (attempt {attempt+1}/{max_retries+1}): {e}. "
                    f"Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)
            else:
                logger.error(f"LLM call failed after {max_retries+1} attempts: {e}")
                return {
                    "error": str(e),
                    "winner": "unknown",
                    "reasoning": f"Evaluation failed: {e}",
                }

    # Should never reach here, but just in case
    return {
        "error": "Max retries exceeded",
        "winner": "unknown",
        "reasoning": "Evaluation failed after max retries",
    }
