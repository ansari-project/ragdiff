"""Reference-based evaluation for RAGDiff.

This module provides single-run evaluation by comparing retrieved results
against ground truth reference answers. Uses LLM to assess correctness,
relevance, and quality of retrieved information.
"""

import asyncio
from typing import Any, Callable

try:
    from litellm import acompletion
except ImportError:
    acompletion = None

from ..core.errors import ComparisonError
from ..core.logging import get_logger
from ..core.models_v2 import EvaluatorConfig, QueryResult, Run
from ..core.storage import load_run

logger = get_logger(__name__)


async def evaluate_result_against_reference(
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
    if acompletion is None:
        raise ComparisonError(
            "LiteLLM is not installed. Install with: pip install litellm"
        )

    # Combine all retrieved chunks
    retrieved_text = "\n\n".join(
        [f"[Chunk {i+1}] {chunk.content}" for i, chunk in enumerate(result.chunks)]
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
        # Call LLM
        response = await acompletion(
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


async def evaluate_run_async(
    run: Run,
    evaluator_config: EvaluatorConfig,
    concurrency: int = 5,
    progress_callback: Callable[[int, int, int, int], None] | None = None,
) -> dict[str, Any]:
    """Evaluate all results in a run against their reference answers.

    Args:
        run: The run to evaluate
        evaluator_config: LLM evaluator configuration
        concurrency: Maximum concurrent LLM evaluations
        progress_callback: Optional callback(current, total, successes, failures)

    Returns:
        Dictionary with:
        - evaluations: List of per-query evaluation results
        - summary: Aggregate statistics (avg scores, etc.)
        - metadata: Evaluation metadata

    Raises:
        ComparisonError: If run has no references or evaluation fails
    """
    # Check that queries have references
    queries_with_refs = [
        (query, result)
        for query, result in zip(run.queries.queries, run.results)
        if query.reference
    ]

    if not queries_with_refs:
        raise ComparisonError(
            "Run has no reference answers. "
            "Use a query set with references (JSONL format with 'reference' field)"
        )

    logger.info(
        f"Evaluating {len(queries_with_refs)} results against references "
        f"(concurrency={concurrency})"
    )

    # Track progress
    completed = 0
    successes = 0
    failures = 0
    evaluations = []

    # Semaphore for concurrency control
    sem = asyncio.Semaphore(concurrency)

    async def evaluate_one(query, result):
        nonlocal completed, successes, failures

        async with sem:
            try:
                evaluation = await evaluate_result_against_reference(
                    query.text, query.reference, result, evaluator_config
                )
                completed += 1
                successes += 1

                if progress_callback:
                    progress_callback(
                        completed, len(queries_with_refs), successes, failures
                    )

                return {
                    "query": query.text,
                    "reference": query.reference,
                    "evaluation": evaluation,
                    "status": "success",
                }
            except Exception as e:
                completed += 1
                failures += 1

                if progress_callback:
                    progress_callback(
                        completed, len(queries_with_refs), successes, failures
                    )

                logger.warning(f"Evaluation failed for query '{query.text}': {e}")
                return {
                    "query": query.text,
                    "reference": query.reference,
                    "evaluation": {},
                    "status": "failed",
                    "error": str(e),
                }

    # Run evaluations concurrently
    tasks = [evaluate_one(query, result) for query, result in queries_with_refs]
    evaluations = await asyncio.gather(*tasks)

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
        "total_queries": len(queries_with_refs),
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
) -> dict[str, Any]:
    """Evaluate a run against reference answers (sync wrapper).

    Args:
        run_id: Run ID or label to evaluate
        domain_name: Domain name
        evaluator_config: Optional evaluator config override
        concurrency: Maximum concurrent evaluations
        progress_callback: Optional callback(current, total, successes, failures)
        domains_dir: Optional domains directory path

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

    # Run async evaluation
    return asyncio.run(
        evaluate_run_async(run, evaluator_config, concurrency, progress_callback)
    )
