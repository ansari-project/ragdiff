"Formatting utilities for v2.0 comparison results."

from pathlib import Path
from typing import Optional

from ..core.models import Comparison


def format_comparison_markdown(
    comparison: Comparison,
    provider_stats: Optional[dict] = None,
    max_evaluations: Optional[int] = 20,
) -> str:
    """Format a v2.0 Comparison as Markdown.

    Args:
        comparison: The comparison result to format
        provider_stats: Optional dict with provider statistics including:
            - wins: Number of wins
            - losses: Number of losses
            - ties: Number of ties
            - scores: List of scores
            - latencies: List of latencies in ms
            - costs: List of costs in USD (optional)
        max_evaluations: Maximum number of evaluations to include (default: 20, None for all)

    Returns:
        Markdown-formatted string
    """
    lines = [
        f"# Comparison: {comparison.label}",
        "",
        f"**Domain:** {comparison.domain}",
        f"**Comparison ID:** {str(comparison.id)[:8]}...",
        f"**Evaluator Model:** {comparison.evaluator_config.model}",
        f"**Temperature:** {comparison.evaluator_config.temperature}",
        "",
        "## Summary",
        "",
        f"- Total Evaluations: {comparison.metadata.get('total_evaluations', 0)}",
        f"- Successful: {comparison.metadata.get('successful_evaluations', 0)}",
        f"- Failed: {comparison.metadata.get('failed_evaluations', 0)}",
        "",
    ]

    # Add provider statistics if provided
    if provider_stats:
        lines.extend(
            [
                "## Provider Statistics",
                "",
                "| Provider | Model | Wins | Losses | Ties | Avg Score | Avg Latency | Avg Cost | Avg Tokens Returned |",
                "|----------|-------|------|--------|------|-----------|-------------|----------|---------------------|",
            ]
        )

        for provider, stats in provider_stats.items():
            avg_score = (
                sum(stats.get("scores", [])) / len(stats.get("scores", []))
                if stats.get("scores")
                else 0
            )
            avg_latency = (
                sum(stats.get("latencies", [])) / len(stats.get("latencies", []))
                if stats.get("latencies")
                else 0
            )

            # Handle cost (might be empty or None)
            costs = [c for c in stats.get("costs", []) if c is not None]
            avg_cost = sum(costs) / len(costs) if costs else 0.0
            cost_str = f"${avg_cost:.4f}" if costs else "N/A"

            model_name = stats.get("model_name", "N/A")

            tokens_returned = [
                t for t in stats.get("tokens_returned", []) if t is not None
            ]
            avg_tokens_returned = (
                sum(tokens_returned) / len(tokens_returned) if tokens_returned else 0
            )
            tokens_returned_str = (
                f"{avg_tokens_returned:.0f}" if tokens_returned else "N/A"
            )

            lines.append(
                f"| {provider} | {model_name} | {stats.get('wins', 0)} | {stats.get('losses', 0)} | "
                f"{stats.get('ties', 0)} | {avg_score:.1f} | {avg_latency:.1f}ms | {cost_str} | {tokens_returned_str} |"
            )

        lines.append("")

    # Add evaluations section
    lines.extend(["## Evaluations", ""])

    # Determine which evaluations to show
    evaluations_to_show = (
        comparison.evaluations
        if max_evaluations is None
        else comparison.evaluations[:max_evaluations]
    )

    # Add individual evaluations
    for i, eval_result in enumerate(evaluations_to_show, 1):
        lines.append(f"### {i}. {eval_result.query}")
        lines.append("")

        if eval_result.reference:
            lines.append(f"**Reference:** {eval_result.reference}")
            lines.append("")

        evaluation = eval_result.evaluation

        if "winner" in evaluation:
            winner_key = evaluation.get("winner", "unknown")
            # Map 'a', 'b' back to provider names if possible
            winner_display = winner_key
            if winner_key == "a" and len(provider_stats) >= 1:
                winner_display = list(provider_stats.keys())[0]
            elif winner_key == "b" and len(provider_stats) >= 2:
                winner_display = list(provider_stats.keys())[1]

            lines.append(f"**Winner:** {winner_display}")
            lines.append("")

        if "reasoning" in evaluation:
            reasoning = evaluation.get("reasoning", "")
            lines.append(f"**Reasoning:** {reasoning}")
            lines.append("")

        # Add scores - handle both score_{provider} and score_a/score_b formats
        score_keys = [k for k in evaluation.keys() if k.startswith("score_")]
        for key in sorted(score_keys):
            if evaluation[key] is not None:
                # Extract provider name from key
                if key == "score_a" and len(provider_stats) >= 1:
                    provider_name = list(provider_stats.keys())[0]
                elif key == "score_b" and len(provider_stats) >= 2:
                    provider_name = list(provider_stats.keys())[1]
                else:
                    provider_name = key.replace("score_", "")

                lines.append(f"**Score {provider_name}:** {evaluation[key]}")

        lines.append("")

        # Add evaluation metadata (cost/tokens for the JUDGE)
        if "_metadata" in evaluation:
            metadata = evaluation["_metadata"]
            if metadata.get("cost") or metadata.get("total_tokens"):
                lines.append(
                    f"**Evaluation Cost:** ${metadata.get('cost', 0):.4f} "
                    f"({metadata.get('total_tokens', 0)} tokens)"
                )

        lines.append("")

    # Add note if there are more evaluations
    if max_evaluations is not None and len(comparison.evaluations) > max_evaluations:
        lines.append(
            f"*... and {len(comparison.evaluations) - max_evaluations} more evaluations*"
        )
        lines.append("")

    return "\n".join(lines)


def save_comparison_markdown(
    comparison: Comparison,
    output_path: Path,
    provider_stats: Optional[dict] = None,
    max_evaluations: Optional[int] = 20,
) -> None:
    """Save a v2.0 Comparison as a Markdown file.

    Args:
        comparison: The comparison result to save
        output_path: Path to write the markdown file
        provider_stats: Optional provider statistics dict
        max_evaluations: Maximum number of evaluations to include (None for all)
    """
    markdown = format_comparison_markdown(
        comparison, provider_stats=provider_stats, max_evaluations=max_evaluations
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)


def calculate_provider_stats(comparison: Comparison, providers: list[str]) -> dict:
    """Calculate provider statistics from a comparison.

    Args:
        comparison: The comparison result
        providers: List of provider names

    Returns:
        Dict mapping provider names to their statistics
    """
    stats = {
        provider: {
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "scores": [],
            "latencies": [],
            "costs": [],
            "tokens_returned": [],
        }
        for provider in providers
    }

    for eval_result in comparison.evaluations:
        evaluation = eval_result.evaluation
        winner = evaluation.get("winner", "unknown").lower()

        # Handle different winner formats
        if winner == "tie":
            for provider in providers:
                stats[provider]["ties"] += 1
        elif winner == "a" and len(providers) >= 1:
            stats[providers[0]]["wins"] += 1
            if len(providers) >= 2:
                stats[providers[1]]["losses"] += 1
        elif winner == "b" and len(providers) >= 2:
            stats[providers[1]]["wins"] += 1
            stats[providers[0]]["losses"] += 1
        elif winner in stats:
            # Winner is actual provider name
            stats[winner]["wins"] += 1
            for provider in providers:
                if provider != winner:
                    stats[provider]["losses"] += 1

        # Collect scores - handle both formats
        for idx, provider in enumerate(providers):
            score = None

            # Try provider name first
            if f"score_{provider}" in evaluation:
                score = evaluation[f"score_{provider}"]
            # Then try a/b notation
            elif idx == 0 and "score_a" in evaluation:
                score = evaluation["score_a"]
            elif idx == 1 and "score_b" in evaluation:
                score = evaluation["score_b"]

            if score is not None:
                stats[provider]["scores"].append(score)

    return stats


def calculate_provider_stats_from_runs(runs: dict, comparison: Comparison) -> dict:
    """Calculate provider statistics including latencies and costs from runs.

    Args:
        runs: Dict mapping provider names to Run objects
        comparison: The comparison result

    Returns:
        Dict mapping provider names to their statistics
    """
    providers = list(runs.keys())
    stats = calculate_provider_stats(comparison, providers)

    # Add latencies, costs, and tokens from runs
    for provider, run in runs.items():
        # Add model name if available
        if hasattr(run, "model_name") and run.model_name:
            stats[provider]["model_name"] = run.model_name

        for result in run.results:
            if result.duration_ms:
                stats[provider]["latencies"].append(result.duration_ms)
            if result.cost is not None:
                stats[provider]["costs"].append(result.cost)
            if result.total_tokens_returned is not None:
                stats[provider]["tokens_returned"].append(result.total_tokens_returned)

    return stats
