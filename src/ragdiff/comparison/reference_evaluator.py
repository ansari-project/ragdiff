"""Reference-based evaluation for RAGDiff.

This module provides single-run evaluation by comparing retrieved results
against ground truth reference answers. Uses LLM to assess correctness,
relevance, and quality of retrieved information.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

try:
    from litellm import completion
except ImportError:
    completion = None

from ..core.errors import ComparisonError
from ..core.logging import get_logger
from ..core.models import EvaluatorConfig, QueryResult, Run
from ..core.storage import load_run

logger = get_logger(__name__)


def evaluate_result_against_reference(
    query: str,
    reference: str,
    result: QueryResult,
    evaluator_config: EvaluatorConfig,
) -> dict[str, Any]:
    """Evaluate a single result against its reference answer using LLM.

    Args:
        query: The original query
        reference: Ground truth answer
        result: The query result with retrieved chunks
        evaluator_config: LLM evaluator configuration

    Returns:
        Dictionary with evaluation scores and reasoning:
        - correctness: 0-100 score for factual correctness
        - relevance: 0-100 score for relevance to query
        - completeness: 0-100 score for coverage of reference answer
        - overall_quality: 0-100 overall quality score
        - reasoning: Explanation of the scores
        - _metadata: LLM usage metadata (tokens, cost, etc.)

    Raises:
        ComparisonError: If LiteLLM is not available or LLM call fails
    """
    if completion is None:
        raise ComparisonError(
            "LiteLLM is not installed. Install with: pip install litellm"
        )

    # Combine all retrieved chunks
    # Handle both Pydantic QueryResult and dict from JSON
    chunks = (
        result.retrieved
        if hasattr(result, "retrieved")
        else result.chunks
        if hasattr(result, "chunks")
        else result.get("retrieved", [])
    )
    retrieved_text = "\n\n".join(
        [
            f"[Chunk {i+1}] {chunk.get('content', chunk) if isinstance(chunk, dict) else chunk.content}"
            for i, chunk in enumerate(chunks)
        ]
    )

    # Create evaluation prompt
    prompt = f"""Evaluate the quality of the retrieved information for answering the given query.

Query: {query}

Reference Answer (Ground Truth): {reference}

Retrieved Information:
{retrieved_text}

Please evaluate the retrieved information on the following criteria (0-100 scale):

1. **Correctness**: Does the retrieved information contain the correct answer? Is it factually accurate?
2. **Relevance**: Is the retrieved information relevant to the query?
3. **Completeness**: Does the retrieved information provide sufficient coverage of the reference answer?
4. **Overall Quality**: Overall assessment considering all factors.

Respond in JSON format:
{{
  "correctness": <0-100>,
  "relevance": <0-100>,
  "completeness": <0-100>,
  "overall_quality": <0-100>,
  "reasoning": "<detailed explanation>"
}}"""

    try:
        # Call LLM (synchronous)
        response = completion(
            model=evaluator_config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=evaluator_config.temperature,
            response_format={"type": "json_object"},
        )

        # Extract evaluation from response
        import json

        content = response.choices[0].message.content
        evaluation = json.loads(content)

        # Add metadata about LLM usage
        if hasattr(response, "usage") and response.usage:
            evaluation["_metadata"] = {
                "model": evaluator_config.model,
                "total_tokens": getattr(response.usage, "total_tokens", 0),
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(response.usage, "completion_tokens", 0),
            }

        return evaluation

    except Exception as e:
        logger.error(f"LLM evaluation failed: {e}")
        raise ComparisonError(f"LLM evaluation failed: {e}") from e


def evaluate_run_threaded(
    run: Run,
    evaluator_config: EvaluatorConfig,
    concurrency: int = 5,
    progress_callback: Callable[[int, int, int, int], None] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Evaluate all results in a run against their reference answers.

    Args:
        run: The run to evaluate
        evaluator_config: LLM evaluator configuration
        concurrency: Maximum concurrent LLM evaluations
        progress_callback: Optional callback(current, total, successes, failures)
        limit: Optional limit on number of queries to evaluate

    Returns:
        Dictionary with:
        - evaluations: List of per-query evaluation results
        - summary: Aggregate statistics (avg scores, etc.)
        - metadata: Evaluation metadata

    Raises:
        ComparisonError: If run has no references or evaluation fails
    """
    # Check that results have references
    results_with_refs = [result for result in run.results if result.reference]

    if not results_with_refs:
        raise ComparisonError(
            "Run has no reference answers. "
            "Use a query set with references (JSONL format with 'reference' field)"
        )

    # Apply limit if specified
    if limit is not None and limit > 0:
        results_with_refs = results_with_refs[:limit]

    logger.info(
        f"Evaluating {len(results_with_refs)} results against references "
        f"(concurrency={concurrency})"
    )

    # Track progress
    completed = 0
    successes = 0
    failures = 0
    evaluations = []

    def evaluate_one(result):
        """Evaluate a single result."""
        nonlocal completed, successes, failures

        try:
            logger.info(f"Starting evaluation for query: {result.query[:50]}...")
            evaluation = evaluate_result_against_reference(
                result.query, result.reference, result, evaluator_config
            )
            completed += 1
            successes += 1
            logger.info(f"Completed evaluation for query: {result.query[:50]}...")

            if progress_callback:
                progress_callback(
                    completed, len(results_with_refs), successes, failures
                )

            return {
                "query": result.query,
                "reference": result.reference,
                "evaluation": evaluation,
                "status": "success",
            }
        except Exception as e:
            completed += 1
            failures += 1
            logger.error(
                f"Evaluation failed for query '{result.query}': {e}", exc_info=True
            )

            if progress_callback:
                progress_callback(
                    completed, len(results_with_refs), successes, failures
                )

            logger.warning(f"Evaluation failed for query '{result.query}': {e}")
            return {
                "query": result.query,
                "reference": result.reference,
                "evaluation": {},
                "status": "failed",
                "error": str(e),
            }

    # Run evaluations concurrently using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        # Submit all tasks
        future_to_result = {
            executor.submit(evaluate_one, result): result
            for result in results_with_refs
        }

        # Collect results as they complete
        for future in as_completed(future_to_result):
            evaluation = future.result()
            evaluations.append(evaluation)

    # Calculate summary statistics
    successful_evals = [e for e in evaluations if e["status"] == "success"]

    if successful_evals:
        avg_correctness = sum(
            e["evaluation"].get("correctness", 0) for e in successful_evals
        ) / len(successful_evals)
        avg_relevance = sum(
            e["evaluation"].get("relevance", 0) for e in successful_evals
        ) / len(successful_evals)
        avg_completeness = sum(
            e["evaluation"].get("completeness", 0) for e in successful_evals
        ) / len(successful_evals)
        avg_overall = sum(
            e["evaluation"].get("overall_quality", 0) for e in successful_evals
        ) / len(successful_evals)
    else:
        avg_correctness = avg_relevance = avg_completeness = avg_overall = 0.0

    summary = {
        "total_queries": len(results_with_refs),
        "successful_evaluations": successes,
        "failed_evaluations": failures,
        "avg_correctness": round(avg_correctness, 2),
        "avg_relevance": round(avg_relevance, 2),
        "avg_completeness": round(avg_completeness, 2),
        "avg_overall_quality": round(avg_overall, 2),
    }

    return {
        "run_id": str(run.id),
        "run_label": run.label,
        "provider": run.provider,
        "query_set": run.query_set,
        "evaluations": evaluations,
        "summary": summary,
        "evaluator_config": {
            "model": evaluator_config.model,
            "temperature": evaluator_config.temperature,
        },
    }


def evaluate_run(
    run_id: str,
    domain_name: str,
    evaluator_config: EvaluatorConfig | None = None,
    concurrency: int = 5,
    progress_callback: Callable[[int, int, int, int], None] | None = None,
    domains_dir: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Evaluate a run against reference answers.

    Args:
        run_id: Run ID or label to evaluate
        domain_name: Domain name
        evaluator_config: Optional evaluator config override
        concurrency: Maximum concurrent evaluations
        progress_callback: Optional callback(current, total, successes, failures)
        domains_dir: Optional domains directory path
        limit: Optional limit on number of queries to evaluate

    Returns:
        Evaluation results dictionary

    Raises:
        ComparisonError: If run not found or evaluation fails
    """
    from pathlib import Path

    from ..core.loaders import load_domain

    # Load run
    run = load_run(
        domain_name, run_id, domains_dir=Path(domains_dir) if domains_dir else None
    )

    # Load domain config if evaluator not provided
    if evaluator_config is None:
        domain = load_domain(
            domain_name, domains_dir=Path(domains_dir) if domains_dir else None
        )
        evaluator_config = domain.evaluator

    # Run threaded evaluation
    return evaluate_run_threaded(
        run, evaluator_config, concurrency, progress_callback, limit
    )


def compare_multiple_runs_batched(
    runs: list[Run],
    evaluator_config: EvaluatorConfig,
    concurrency: int = 5,
    progress_callback: Callable[[int, int, int, int], None] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Compare multiple runs using batched LLM calls.

    Instead of evaluating each run separately (300 LLM calls for 3 runs × 100 queries),
    this makes ONE LLM call per query with all runs' results bundled (100 calls total).

    This is 3x faster, 3x cheaper, and gives better comparative results since the LLM
    directly compares results side-by-side rather than evaluating independently.

    Args:
        runs: List of runs to compare (all must use same query set)
        evaluator_config: LLM evaluator configuration
        concurrency: Maximum concurrent LLM evaluations
        progress_callback: Optional callback(current, total, successes, failures)
        limit: Optional limit on number of queries to evaluate

    Returns:
        Dictionary with:
        - comparisons: List of per-query comparison results
        - summary: Aggregate statistics showing which run performed best
        - metadata: Comparison metadata

    Raises:
        ComparisonError: If runs don't have references or are from different query sets
    """
    if completion is None:
        raise ComparisonError(
            "LiteLLM is not installed. Install with: pip install litellm"
        )

    if len(runs) < 2:
        raise ComparisonError("Need at least 2 runs to compare")

    # Verify all runs have same query set
    query_sets = {run.query_set for run in runs}
    if len(query_sets) > 1:
        raise ComparisonError(
            f"All runs must use the same query set. Found: {query_sets}"
        )

    # Verify all runs have same number of results
    result_counts = {len(run.results) for run in runs}
    if len(result_counts) > 1:
        raise ComparisonError(
            f"All runs must have the same number of results. Found: {result_counts}"
        )

    # Get queries from first run (they should all be the same)
    num_queries = len(runs[0].results)

    # Verify all queries have references
    first_run_refs = [r.reference for r in runs[0].results]
    if not all(first_run_refs):
        raise ComparisonError(
            "All queries must have reference answers. "
            "Use a query set with references (JSONL format with 'reference' field)"
        )

    # Apply limit if specified
    queries_to_compare = num_queries
    if limit is not None and limit > 0:
        queries_to_compare = min(limit, num_queries)

    logger.info(
        f"Comparing {len(runs)} runs on {queries_to_compare} queries "
        f"(concurrency={concurrency})"
    )

    # Track progress
    completed = 0
    successes = 0
    failures = 0
    comparisons = []

    def compare_one_query(query_index: int):
        """Compare all runs' results for a single query."""
        nonlocal completed, successes, failures

        try:
            # Get results from all runs for this query
            query = runs[0].results[query_index].query
            reference = runs[0].results[query_index].reference

            # Build comparison prompt with all runs' results
            runs_text = []
            for _i, run in enumerate(runs):
                result = run.results[query_index]
                chunks = result.retrieved
                retrieved_text = "\n".join(
                    [
                        f"  [Chunk {j+1}] {chunk.content}"
                        for j, chunk in enumerate(chunks)
                    ]
                )

                runs_text.append(
                    f"**{run.provider}** (Run: {run.label or str(run.id)[:8]}...):\n{retrieved_text}"
                )

            all_results = "\n\n".join(runs_text)

            # Create comparison prompt
            provider_names = [run.provider for run in runs]
            prompt = f"""Compare the quality of retrieved information from {len(runs)} different RAG systems for answering the given query.

Query: {query}

Reference Answer (Ground Truth): {reference}

Retrieved Information from Each System:

{all_results}

Please compare and rank these systems based on:
1. **Correctness**: Which results contain the correct answer?
2. **Relevance**: Which results are most relevant to the query?
3. **Completeness**: Which results provide best coverage of the reference answer?

Respond in JSON format:
{{
  "rankings": {{
    {", ".join([f'"{name}": {{"rank": <1-{len(runs)}>, "score": <0-100>, "reasoning": "..."}}'  for name in provider_names])}
  }},
  "winner": "<provider_name>",
  "overall_reasoning": "<detailed comparison explanation>"
}}

Note: Rank 1 is best, {len(runs)} is worst. Ties are allowed."""

            logger.info(f"Starting comparison for query: {query[:50]}...")

            # Call LLM (synchronous)
            response = completion(
                model=evaluator_config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=evaluator_config.temperature,
                response_format={"type": "json_object"},
            )

            # Extract comparison from response
            import json

            content = response.choices[0].message.content
            comparison = json.loads(content)

            # Add metadata
            if hasattr(response, "usage") and response.usage:
                comparison["_metadata"] = {
                    "model": evaluator_config.model,
                    "total_tokens": getattr(response.usage, "total_tokens", 0),
                    "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(
                        response.usage, "completion_tokens", 0
                    ),
                }

            completed += 1
            successes += 1
            logger.info(f"Completed comparison for query: {query[:50]}...")

            if progress_callback:
                progress_callback(completed, queries_to_compare, successes, failures)

            return {
                "query": query,
                "reference": reference,
                "comparison": comparison,
                "status": "success",
            }

        except Exception as e:
            completed += 1
            failures += 1
            logger.error(
                f"Comparison failed for query index {query_index}: {e}", exc_info=True
            )

            if progress_callback:
                progress_callback(completed, queries_to_compare, successes, failures)

            return {
                "query": runs[0].results[query_index].query
                if query_index < len(runs[0].results)
                else f"Query {query_index}",
                "reference": runs[0].results[query_index].reference
                if query_index < len(runs[0].results)
                else None,
                "comparison": {},
                "status": "failed",
                "error": str(e),
            }

    # Run comparisons concurrently using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        # Submit all tasks
        future_to_index = {
            executor.submit(compare_one_query, i): i for i in range(queries_to_compare)
        }

        # Collect results as they complete
        for future in as_completed(future_to_index):
            comparison = future.result()
            comparisons.append(comparison)

    # Calculate summary statistics
    successful_comps = [c for c in comparisons if c["status"] == "success"]

    # Count wins per provider
    provider_wins = {run.provider: 0 for run in runs}
    provider_scores = {run.provider: [] for run in runs}

    for comp in successful_comps:
        if "comparison" in comp and "winner" in comp["comparison"]:
            winner = comp["comparison"]["winner"]
            if winner in provider_wins:
                provider_wins[winner] += 1

        # Collect scores
        if "comparison" in comp and "rankings" in comp["comparison"]:
            for provider, data in comp["comparison"]["rankings"].items():
                if provider in provider_scores and "score" in data:
                    provider_scores[provider].append(data["score"])

    # Calculate average scores
    provider_avg_scores = {
        provider: (sum(scores) / len(scores) if scores else 0.0)
        for provider, scores in provider_scores.items()
    }

    summary = {
        "total_queries": queries_to_compare,
        "successful_comparisons": successes,
        "failed_comparisons": failures,
        "provider_wins": provider_wins,
        "provider_avg_scores": {
            provider: round(score, 2) for provider, score in provider_avg_scores.items()
        },
        "runs_compared": [
            {
                "provider": run.provider,
                "run_id": str(run.id),
                "label": run.label,
            }
            for run in runs
        ],
    }

    return {
        "comparisons": comparisons,
        "summary": summary,
        "evaluator_config": {
            "model": evaluator_config.model,
            "temperature": evaluator_config.temperature,
        },
    }
