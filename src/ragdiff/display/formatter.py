"""Display formatters for comparison results."""

import json
from textwrap import wrap
from typing import List, Optional

from ..core.models import ComparisonResult, RagResult


class ComparisonFormatter:
    """Format comparison results for human-friendly display."""

    def __init__(self, width: int = 80, indent: int = 2):
        """Initialize formatter.

        Args:
            width: Maximum line width for text wrapping
            indent: Number of spaces for indentation
        """
        self.width = width
        self.indent_str = " " * indent

    def format_side_by_side(self, result: ComparisonResult) -> str:
        """Format results in side-by-side comparison.

        Args:
            result: Comparison result to format

        Returns:
            Formatted string for display
        """
        output: List[str] = []
        output.append(self._format_header(result))
        errors_section = self._format_errors(result)
        if errors_section:
            output.append(errors_section)
        output.append(self._format_results_comparison(result))
        output.append(self._format_performance(result))

        if result.llm_evaluation:
            output.append(self._format_llm_evaluation(result))

        return "\n".join(output)

    def _format_header(self, result: ComparisonResult) -> str:
        """Format header section."""
        lines: List[str] = [
            "=" * self.width,
            "RAG TOOL COMPARISON RESULTS",
            "=" * self.width,
            f"Query: {result.query}",
            f"Timestamp: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "-" * self.width,
        ]
        return "\n".join(lines)

    def _format_errors(self, result: ComparisonResult) -> Optional[str]:
        """Format error section if any errors occurred."""
        if not result.has_errors():
            return None

        lines = ["ERRORS:"]
        for tool_name, error_msg in result.errors.items():
            lines.append(f"{self.indent_str}[{tool_name}] {error_msg}")
        lines.append("-" * self.width)
        return "\n".join(lines)

    def _format_results_comparison(self, result: ComparisonResult) -> str:
        """Format main results comparison."""
        lines = ["SEARCH RESULTS:"]

        # Get max number of results from any tool
        max_results = max(
            (len(results) for results in result.tool_results.values()), default=0
        )

        # Create side-by-side comparison for each result position
        for idx in range(max_results):
            lines.append(f"\n{self.indent_str}Result #{idx + 1}:")
            lines.append(self.indent_str + "-" * (self.width - len(self.indent_str)))

            for tool_name, results in sorted(result.tool_results.items()):
                lines.append(f"\n{self.indent_str * 2}[{tool_name.upper()}]")

                if idx < len(results):
                    lines.extend(
                        self._format_single_result(results[idx], indent_level=3)
                    )
                else:
                    lines.append(f"{self.indent_str * 3}(No result at this position)")

        return "\n".join(lines)

    def _format_single_result(
        self, result: RagResult, indent_level: int = 2
    ) -> List[str]:
        """Format a single search result."""
        indent = self.indent_str * indent_level
        lines = []

        # Format text with wrapping
        text_lines = wrap(
            result.text,
            width=self.width - len(indent),
            initial_indent="",
            subsequent_indent="",
        )
        for line in text_lines[:3]:  # Limit to 3 lines
            lines.append(f"{indent}{line}")
        if len(text_lines) > 3:
            lines.append(f"{indent}...")

        # Add metadata
        lines.append(f"{indent}Score: {result.score:.3f}")
        if result.source:
            lines.append(f"{indent}Source: {result.source}")

        return lines

    def _format_performance(self, result: ComparisonResult) -> str:
        """Format performance metrics."""
        lines = ["", "-" * self.width, "PERFORMANCE METRICS:"]

        for tool_name, results in result.tool_results.items():
            count = len(results)

            # Get latency from first result if available
            latency = (
                results[0].latency_ms if results and results[0].latency_ms else None
            )

            perf_str = f"{self.indent_str}[{tool_name}] Results: {count}"
            if latency:
                perf_str += f", Latency: {latency:.1f}ms"

            lines.append(perf_str)

        return "\n".join(lines)

    def _format_llm_evaluation(self, result: ComparisonResult) -> str:
        """Format LLM evaluation section."""
        eval_data = result.llm_evaluation
        if eval_data is None:
            return ""

        lines = [
            "",
            "-" * self.width,
            "LLM EVALUATION:",
            f"{self.indent_str}Model: {eval_data.llm_model}",
            f"{self.indent_str}Winner: {eval_data.winner or 'No clear winner'}",
            "",
            f"{self.indent_str}Analysis:",
        ]

        # Wrap analysis text
        analysis_lines = wrap(
            eval_data.analysis,
            width=self.width - len(self.indent_str * 2),
            initial_indent="",
            subsequent_indent="",
        )
        for line in analysis_lines:
            lines.append(f"{self.indent_str * 2}{line}")

        # Add quality scores
        if eval_data.quality_scores:
            lines.append("")
            lines.append(f"{self.indent_str}Quality Scores:")
            for tool_name, score in eval_data.quality_scores.items():
                lines.append(f"{self.indent_str * 2}{tool_name}: {score}/10")

        return "\n".join(lines)

    def format_json(self, result: ComparisonResult, pretty: bool = True) -> str:
        """Format results as JSON.

        Args:
            result: Comparison result to format
            pretty: Whether to pretty-print the JSON

        Returns:
            JSON string representation
        """
        data = result.to_dict()

        if pretty:
            return json.dumps(data, indent=2, default=str)
        else:
            return json.dumps(data, default=str)

    def format_markdown(self, result: ComparisonResult) -> str:
        """Format results as Markdown.

        Args:
            result: Comparison result to format

        Returns:
            Markdown formatted string
        """
        lines = [
            "# RAG Tool Comparison Results",
            "",
            f"**Query:** {result.query}",
            f"**Timestamp:** {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        # Errors section
        if result.has_errors():
            lines.append("## Errors")
            for tool_name, error_msg in result.errors.items():
                lines.append(f"- **{tool_name}:** {error_msg}")
            lines.append("")

        # Results comparison
        lines.append("## Search Results")

        for tool_name, results in sorted(result.tool_results.items()):
            lines.append(f"\n### {tool_name.upper()}")

            if not results:
                lines.append("*No results returned*")
                continue

            for idx, res in enumerate(results, 1):
                lines.append(f"\n#### Result {idx}")
                lines.append(f"- **Score:** {res.score:.3f}")
                if res.source:
                    lines.append(f"- **Source:** {res.source}")
                lines.append(f"- **Text:** {res.text[:200]}...")

        # Performance metrics
        lines.append("\n## Performance Metrics")
        lines.append("")
        lines.append("| Tool | Results | Latency |")
        lines.append("|------|---------|---------|")

        for tool_name, results in result.tool_results.items():
            count = len(results)
            latency = (
                results[0].latency_ms if results and results[0].latency_ms else "N/A"
            )
            latency_str = f"{latency:.1f}ms" if isinstance(latency, float) else latency
            lines.append(f"| {tool_name} | {count} | {latency_str} |")

        # LLM Evaluation
        if result.llm_evaluation:
            eval_data = result.llm_evaluation
            lines.extend(
                [
                    "",
                    "## LLM Evaluation",
                    "",
                    f"**Model:** {eval_data.llm_model}",
                    f"**Winner:** {eval_data.winner or 'No clear winner'}",
                    "",
                    "### Analysis",
                    eval_data.analysis,
                ]
            )

            if eval_data.quality_scores:
                lines.extend(
                    [
                        "",
                        "### Quality Scores",
                        "",
                        "| Tool | Score |",
                        "|------|-------|",
                    ]
                )
                for tool_name, score in eval_data.quality_scores.items():
                    lines.append(f"| {tool_name} | {score}/10 |")

        return "\n".join(lines)

    def format_summary(self, result: ComparisonResult) -> str:
        """Format a brief summary of the comparison.

        Args:
            result: Comparison result to format

        Returns:
            Brief summary string
        """
        lines = [
            (
                f"Query: {result.query[:50]}..."
                if len(result.query) > 50
                else f"Query: {result.query}"
            ),
        ]

        # Result counts
        counts = []
        for tool_name, results in result.tool_results.items():
            counts.append(f"{tool_name}: {len(results)}")
        lines.append(f"Results: {', '.join(counts)}")

        # Errors
        if result.has_errors():
            error_tools = list(result.errors.keys())
            lines.append(f"Errors: {', '.join(error_tools)}")

        # LLM verdict if available
        if result.llm_evaluation and result.llm_evaluation.winner:
            lines.append(f"Winner: {result.llm_evaluation.winner}")

        return " | ".join(lines)
