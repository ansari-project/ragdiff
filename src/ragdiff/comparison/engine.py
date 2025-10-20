"""Comparison engine for running parallel RAG searches."""

import time
import logging
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..core.models import RagResult, ComparisonResult, LLMEvaluation
from ..adapters.base import BaseRagTool

logger = logging.getLogger(__name__)


class ComparisonEngine:
    """Engine for comparing multiple RAG tools."""

    def __init__(self, tools: Dict[str, BaseRagTool]):
        """Initialize comparison engine.

        Args:
            tools: Dictionary mapping tool names to initialized adapters
        """
        if not tools:
            raise ValueError("At least one tool must be provided")

        self.tools = tools
        logger.info(f"Initialized comparison engine with tools: {list(tools.keys())}")

    def run_comparison(
        self,
        query: str,
        top_k: int = 5,
        parallel: bool = True
    ) -> ComparisonResult:
        """Run the same query against all tools and compare results.

        Args:
            query: Search query to run
            top_k: Number of results to retrieve from each tool
            parallel: Whether to run searches in parallel

        Returns:
            ComparisonResult with results from all tools
        """
        logger.info(f"Running comparison for query: '{query}' with top_k={top_k}")

        # Initialize result container
        tool_results = {}
        errors = {}

        # Run searches
        if parallel:
            tool_results, errors = self._run_parallel(query, top_k)
        else:
            tool_results, errors = self._run_sequential(query, top_k)

        # Create comparison result
        result = ComparisonResult(
            query=query,
            tool_results=tool_results,
            errors=errors,
            llm_evaluation=None  # Will be added in Phase 5
        )

        logger.info(
            f"Comparison complete. Tools: {len(tool_results)}, "
            f"Errors: {len(errors)}"
        )

        return result

    def _run_parallel(
        self,
        query: str,
        top_k: int
    ) -> tuple[Dict[str, List[RagResult]], Dict[str, str]]:
        """Run searches in parallel using ThreadPoolExecutor.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            Tuple of (tool_results, errors)
        """
        tool_results = {}
        errors = {}

        with ThreadPoolExecutor(max_workers=len(self.tools)) as executor:
            # Submit all tasks
            future_to_tool = {
                executor.submit(
                    self._run_single_search,
                    tool_name,
                    tool,
                    query,
                    top_k
                ): tool_name
                for tool_name, tool in self.tools.items()
            }

            # Collect results as they complete
            for future in as_completed(future_to_tool):
                tool_name = future_to_tool[future]
                try:
                    results = future.result()
                    tool_results[tool_name] = results
                except Exception as e:
                    error_msg = f"Failed to get results: {str(e)}"
                    errors[tool_name] = error_msg
                    logger.error(f"Error in {tool_name}: {error_msg}")

        return tool_results, errors

    def _run_sequential(
        self,
        query: str,
        top_k: int
    ) -> tuple[Dict[str, List[RagResult]], Dict[str, str]]:
        """Run searches sequentially.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            Tuple of (tool_results, errors)
        """
        tool_results = {}
        errors = {}

        for tool_name, tool in self.tools.items():
            try:
                results = self._run_single_search(tool_name, tool, query, top_k)
                tool_results[tool_name] = results
            except Exception as e:
                error_msg = f"Failed to get results: {str(e)}"
                errors[tool_name] = error_msg
                logger.error(f"Error in {tool_name}: {error_msg}")

        return tool_results, errors

    def _run_single_search(
        self,
        tool_name: str,
        tool: BaseRagTool,
        query: str,
        top_k: int
    ) -> List[RagResult]:
        """Run a single search with timing.

        Args:
            tool_name: Name of the tool
            tool: Tool adapter instance
            query: Search query
            top_k: Number of results

        Returns:
            List of search results with latency info
        """
        logger.debug(f"Starting search with {tool_name}")
        start_time = time.time()

        try:
            # Run the search
            results = tool.search(query, top_k)

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Add latency to each result
            for result in results:
                if result.latency_ms is None:
                    result.latency_ms = latency_ms

            logger.debug(
                f"{tool_name} returned {len(results)} results "
                f"in {latency_ms:.2f}ms"
            )

            return results

        except Exception as e:
            logger.error(f"Error in {tool_name} search: {str(e)}")
            raise

    def get_summary_stats(self, result: ComparisonResult) -> Dict[str, Any]:
        """Get summary statistics for a comparison.

        Args:
            result: Comparison result to analyze

        Returns:
            Dictionary with summary statistics
        """
        stats = {
            "query": result.query,
            "tools_compared": list(result.tool_results.keys()),
            "tools_with_errors": list(result.errors.keys()),
            "result_counts": {},
            "average_scores": {},
            "latencies_ms": {}
        }

        for tool_name, results in result.tool_results.items():
            if results:
                stats["result_counts"][tool_name] = len(results)

                # Calculate average score
                scores = [r.score for r in results if r.score is not None]
                if scores:
                    stats["average_scores"][tool_name] = sum(scores) / len(scores)

                # Get latency (use first result's latency as proxy)
                if results[0].latency_ms is not None:
                    stats["latencies_ms"][tool_name] = results[0].latency_ms

        return stats