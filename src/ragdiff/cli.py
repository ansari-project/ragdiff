"""Command-line interface for RAG comparison tool."""

import json
import logging
import os
from pathlib import Path
from typing import List, Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .adapters.factory import create_adapter, get_available_adapters
from .comparison.engine import ComparisonEngine
from .core.config import Config
from .core.models import ComparisonResult
from .display.formatter import ComparisonFormatter
from .evaluation.evaluator import LLMEvaluator

# Load environment variables from .env file
load_dotenv()

# Initialize Typer app
app = typer.Typer(
    name="rag-compare",
    help="Compare RAG tool results side-by-side",
    add_completion=False,
)

console = Console()
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )


@app.command()
def compare(
    query: str = typer.Argument(..., help="Search query to run against all tools"),
    tools: List[str] = typer.Option(
        None,
        "--tool",
        "-t",
        help="Tools to compare (can specify multiple). If not specified, uses all configured tools.",
    ),
    top_k: int = typer.Option(
        5, "--top-k", "-k", help="Number of results to retrieve from each tool"
    ),
    config_file: str = typer.Option(
        "configs/mawsuah.yaml", "--config", "-c", help="Path to configuration file"
    ),
    output_format: str = typer.Option(
        "display",
        "--format",
        "-f",
        help="Output format: display, json, jsonl, csv, markdown, summary",
    ),
    output_file: Optional[str] = typer.Option(
        None, "--output", "-o", help="Save output to file"
    ),
    parallel: bool = typer.Option(
        True, "--parallel/--sequential", help="Run searches in parallel or sequential"
    ),
    evaluate: bool = typer.Option(
        False, "--evaluate/--no-evaluate", help="Enable LLM evaluation using Claude"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
):
    """Run a comparison query against configured RAG tools."""
    setup_logging(verbose)

    try:
        # Load configuration
        if not Path(config_file).exists():
            console.print(f"[red]Configuration file not found: {config_file}[/red]")
            raise typer.Exit(1)

        config = Config(Path(config_file))
        config.validate()

        # Determine which tools to use
        if tools:
            # Use specified tools
            tool_names = tools
        else:
            # Use all configured tools
            tool_names = list(config.tools.keys())

        if len(tool_names) < 2:
            console.print(
                "[yellow]Warning: Comparison works best with 2 or more tools[/yellow]"
            )

        # Create adapters for selected tools
        console.print(f"[cyan]Initializing {len(tool_names)} tools...[/cyan]")
        adapters = {}
        for tool_name in tool_names:
            if tool_name not in config.tools:
                console.print(
                    f"[red]Tool '{tool_name}' not found in configuration[/red]"
                )
                raise typer.Exit(1)

            try:
                adapters[tool_name] = create_adapter(tool_name, config.tools[tool_name])
                console.print(f"  ✓ {tool_name}")
            except Exception as e:
                console.print(f"  ✗ {tool_name}: {str(e)}")
                if not typer.confirm("Continue without this tool?"):
                    raise typer.Exit(1)

        if not adapters:
            console.print("[red]No tools available for comparison[/red]")
            raise typer.Exit(1)

        # Create comparison engine
        engine = ComparisonEngine(adapters)

        # Run comparison
        with console.status(f"[bold cyan]Running query: {query}...[/bold cyan]"):
            result = engine.run_comparison(query, top_k=top_k, parallel=parallel)

        # Run LLM evaluation if requested
        if evaluate:
            llm_config = config.get_llm_config()
            if llm_config:
                with console.status("[bold cyan]Running LLM evaluation...[/bold cyan]"):
                    try:
                        evaluator = LLMEvaluator(
                            model=llm_config.get("model", "claude-sonnet-4-20250514"),
                            api_key=os.getenv(
                                llm_config.get("api_key_env", "ANTHROPIC_API_KEY")
                            ),
                        )
                        result.llm_evaluation = evaluator.evaluate(result)
                        console.print("[green]✓ LLM evaluation complete[/green]")
                    except Exception as e:
                        console.print(
                            f"[yellow]Warning: LLM evaluation failed: {e}[/yellow]"
                        )
            else:
                console.print(
                    "[yellow]LLM evaluation requested but not configured[/yellow]"
                )

        # Format output
        formatter = ComparisonFormatter(width=console.width)

        if output_format == "json":
            output = formatter.format_json(result, pretty=True)
        elif output_format == "jsonl":
            output = json.dumps(result.to_dict())
        elif output_format == "csv":
            import csv
            from io import StringIO

            buf = StringIO()
            writer = csv.writer(buf)
            tool_names = list(result.tool_results.keys())
            header = ["query", "timestamp"]
            for tool_name in tool_names:
                header.extend([f"{tool_name}_count", f"{tool_name}_latency_ms"])
            writer.writerow(header)
            row = [result.query, result.timestamp.isoformat()]
            for tool_name in tool_names:
                tool_results = result.tool_results.get(tool_name, [])
                count = len(tool_results)
                latency = tool_results[0].latency_ms if tool_results else 0
                row.extend([count, f"{latency:.1f}"])
            writer.writerow(row)
            output = buf.getvalue()
        elif output_format == "markdown":
            output = formatter.format_markdown(result)
        elif output_format == "summary":
            output = formatter.format_summary(result)
        else:  # display
            output = formatter.format_side_by_side(result)

        # Output results
        if output_file:
            Path(output_file).write_text(output)
            console.print(f"[green]Results saved to {output_file}[/green]")
        else:
            if output_format == "json":
                console.print_json(output)
            elif output_format == "display":
                # Use rich formatting for display mode
                _display_rich_results(result)
            else:
                console.print(output)

        # Show LLM evaluation if available
        if result.llm_evaluation and output_format == "display":
            _display_llm_evaluation(result.llm_evaluation)

        # Show summary statistics
        if output_format != "summary":
            stats = engine.get_summary_stats(result)
            _display_stats_table(stats)

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


@app.command()
def list_tools(
    config_file: str = typer.Option(
        "configs/mawsuah.yaml", "--config", "-c", help="Path to configuration file"
    ),
):
    """List all available and configured tools."""
    console.print("[bold]Available Tool Adapters:[/bold]")
    for adapter_name in get_available_adapters():
        console.print(f"  • {adapter_name}")

    if Path(config_file).exists():
        config = Config(Path(config_file))
        console.print("\n[bold]Configured Tools:[/bold]")
        for tool_name, tool_config in config.tools.items():
            status = (
                "[green]✓[/green]"
                if os.getenv(tool_config.api_key_env)
                else "[red]✗ (missing API key)[/red]"
            )
            console.print(f"  {status} {tool_name} - {tool_config.api_key_env}")


@app.command()
def validate_config(
    config_file: str = typer.Option(
        "configs/mawsuah.yaml", "--config", "-c", help="Path to configuration file"
    ),
):
    """Validate the configuration file."""
    try:
        if not Path(config_file).exists():
            console.print(f"[red]Configuration file not found: {config_file}[/red]")
            raise typer.Exit(1)

        config = Config(Path(config_file))
        config.validate()

        console.print("[green]✓ Configuration is valid[/green]")

        # Show details
        console.print(f"\n[bold]Tools configured:[/bold] {len(config.tools)}")
        for tool_name in config.tools:
            console.print(f"  • {tool_name}")

        console.print("\n[bold]LLM configuration:[/bold]")
        if config.llm:
            console.print(f"  • Model: {config.llm.model}")
            api_key_status = "✓" if os.getenv(config.llm.api_key_env) else "✗ (not set)"
            console.print(f"  • API key: {api_key_status}")
        else:
            console.print("  • Not configured (LLM evaluation disabled)")

    except Exception as e:
        console.print(f"[red]Configuration validation failed: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def batch(
    queries_file: str = typer.Argument(
        ..., help="Path to file with queries (one per line)"
    ),
    tools: List[str] = typer.Option(
        None,
        "--tool",
        "-t",
        help="Tools to compare (can specify multiple). If not specified, uses all configured tools.",
    ),
    top_k: int = typer.Option(
        5, "--top-k", "-k", help="Number of results to retrieve from each tool"
    ),
    config_file: str = typer.Option(
        "configs/mawsuah.yaml", "--config", "-c", help="Path to configuration file"
    ),
    output_dir: str = typer.Option(
        "outputs", "--output-dir", "-o", help="Directory to save batch results"
    ),
    output_format: str = typer.Option(
        "jsonl", "--format", "-f", help="Output format: json, jsonl, csv"
    ),
    evaluate: bool = typer.Option(
        False, "--evaluate/--no-evaluate", help="Enable LLM evaluation using Claude"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
):
    """Run batch comparison on multiple queries from a file."""
    setup_logging(verbose)

    try:
        # Load queries
        queries_path = Path(queries_file)
        if not queries_path.exists():
            console.print(f"[red]Queries file not found: {queries_file}[/red]")
            raise typer.Exit(1)

        queries = [
            line.strip()
            for line in queries_path.read_text().split("\n")
            if line.strip()
        ]
        console.print(f"[cyan]Loaded {len(queries)} queries from {queries_file}[/cyan]")

        # Load configuration
        if not Path(config_file).exists():
            console.print(f"[red]Configuration file not found: {config_file}[/red]")
            raise typer.Exit(1)

        config = Config(Path(config_file))
        config.validate()

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Determine which tools to use
        tool_names = tools if tools else list(config.tools.keys())

        # Create adapters
        console.print(f"[cyan]Initializing {len(tool_names)} tools...[/cyan]")
        adapters = {}
        for tool_name in tool_names:
            if tool_name not in config.tools:
                console.print(
                    f"[red]Tool '{tool_name}' not found in configuration[/red]"
                )
                raise typer.Exit(1)
            adapters[tool_name] = create_adapter(tool_name, config.tools[tool_name])
            console.print(f"  ✓ {tool_name}")

        # Create comparison engine
        engine = ComparisonEngine(adapters)

        # Setup LLM evaluator if needed
        evaluator = None
        if evaluate:
            llm_config = config.get_llm_config()
            if llm_config:
                evaluator = LLMEvaluator(
                    model=llm_config.get("model", "claude-sonnet-4-20250514"),
                    api_key=os.getenv(
                        llm_config.get("api_key_env", "ANTHROPIC_API_KEY")
                    ),
                )

        # Process queries
        results = []
        import csv
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_path / f"batch_results_{timestamp}.{output_format}"

        with console.status("[bold cyan]Processing queries...[/bold cyan]") as status:
            for idx, query in enumerate(queries, 1):
                status.update(
                    f"[bold cyan]Processing query {idx}/{len(queries)}: {query[:50]}...[/bold cyan]"
                )

                result = engine.run_comparison(query, top_k=top_k, parallel=True)

                # Add LLM evaluation if requested
                if evaluator:
                    try:
                        result.llm_evaluation = evaluator.evaluate(result)
                    except Exception as e:
                        logger.warning(f"LLM evaluation failed for query {idx}: {e}")

                results.append(result)

        # Save results
        if output_format == "json":
            with open(output_file, "w") as f:
                json.dump([result.to_dict() for result in results], f, indent=2)
        elif output_format == "jsonl":
            with open(output_file, "w") as f:
                for result in results:
                    json.dump(result.to_dict(), f)
                    f.write("\n")
        elif output_format == "csv":
            with open(output_file, "w", newline="") as f:
                writer = csv.writer(f)
                # Header
                header = ["query", "timestamp"]
                for tool_name in tool_names:
                    header.extend([f"{tool_name}_count", f"{tool_name}_latency_ms"])
                if evaluate:
                    header.extend(
                        ["llm_winner"] + [f"llm_score_{name}" for name in tool_names]
                    )
                writer.writerow(header)

                # Data rows
                for result in results:
                    row = [result.query, result.timestamp.isoformat()]
                    for tool_name in tool_names:
                        tool_results = result.tool_results.get(tool_name, [])
                        count = len(tool_results)
                        latency = tool_results[0].latency_ms if tool_results else 0
                        row.extend([count, f"{latency:.1f}"])

                    if evaluate and result.llm_evaluation:
                        row.append(result.llm_evaluation.winner or "tie")
                        for tool_name in tool_names:
                            row.append(
                                result.llm_evaluation.quality_scores.get(tool_name, "")
                            )

                    writer.writerow(row)

        console.print(f"\n[green]✓ Processed {len(queries)} queries[/green]")
        console.print(f"[green]✓ Results saved to {output_file}[/green]")

        # Calculate and display percentile latencies
        _display_batch_latency_stats(results, tool_names)

        # Display LLM evaluation summary if enabled
        if evaluate:
            _display_llm_evaluation_summary(results, tool_names)

            # Generate and display holistic summary
            summary_file = output_path / f"holistic_summary_{timestamp}.md"
            _generate_and_display_holistic_summary(results, tool_names, summary_file)

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


@app.command()
def quick_test(
    config_file: str = typer.Option(
        "configs/mawsuah.yaml", "--config", "-c", help="Path to configuration file"
    ),
):
    """Run a quick test query to verify setup."""
    query = "What is the ruling on prayer times?"
    console.print(f"[cyan]Running test query: '{query}'[/cyan]\n")

    # Run comparison with minimal settings
    compare(
        query=query,
        tools=None,
        top_k=2,
        config_file=config_file,
        output_format="summary",
        output_file=None,
        parallel=True,
        evaluate=False,
        verbose=False,
    )


def _display_rich_results(result: ComparisonResult):
    """Display results using rich formatting."""
    # Header
    console.print(
        Panel.fit(
            f"[bold cyan]Query:[/bold cyan] {result.query}",
            title="RAG Comparison Results",
        )
    )

    # Errors if any
    if result.has_errors():
        error_text = Text()
        for tool_name, error_msg in result.errors.items():
            error_text.append(f"{tool_name}: ", style="bold red")
            error_text.append(f"{error_msg}\n")
        console.print(Panel(error_text, title="[red]Errors[/red]", border_style="red"))

    # Results side by side
    for idx in range(max(len(results) for results in result.tool_results.values())):
        console.print(f"\n[bold]Result #{idx + 1}[/bold]")

        for tool_name, results in sorted(result.tool_results.items()):
            if idx < len(results):
                res = results[idx]
                panel_content = Text()
                panel_content.append(res.text[:200])
                if len(res.text) > 200:
                    panel_content.append("...", style="dim")
                panel_content.append(f"\n\nScore: {res.score:.3f}", style="cyan")
                if res.source:
                    panel_content.append(f"\nSource: {res.source}", style="dim")

                console.print(
                    Panel(
                        panel_content,
                        title=f"[bold]{tool_name.upper()}[/bold]",
                        border_style="cyan",
                    )
                )


def _display_llm_evaluation(evaluation):
    """Display LLM evaluation results."""

    eval_text = Text()

    # Winner
    if evaluation.winner:
        eval_text.append("🏆 Winner: ", style="bold")
        eval_text.append(f"{evaluation.winner.upper()}\n\n", style="bold green")
    else:
        eval_text.append("🏆 Winner: ", style="bold")
        eval_text.append("TIE\n\n", style="bold yellow")

    # Quality scores
    if evaluation.quality_scores:
        eval_text.append("Quality Scores (0-10):\n", style="bold")
        for tool, score in evaluation.quality_scores.items():
            eval_text.append(f"  • {tool}: ", style="cyan")
            eval_text.append(f"{score}/10\n")
        eval_text.append("\n")

    # Analysis
    eval_text.append("Analysis:\n", style="bold")
    eval_text.append(evaluation.analysis)

    console.print(
        Panel(eval_text, title="[bold]LLM Evaluation[/bold]", border_style="green")
    )


def _display_batch_latency_stats(
    results: List[ComparisonResult], tool_names: List[str]
):
    """Display latency percentile statistics for batch processing."""
    import statistics

    # Collect latencies per tool
    latencies_by_tool = {tool_name: [] for tool_name in tool_names}

    for result in results:
        for tool_name in tool_names:
            tool_results = result.tool_results.get(tool_name, [])
            if tool_results and tool_results[0].latency_ms:
                latencies_by_tool[tool_name].append(tool_results[0].latency_ms)

    # Create table with percentile statistics
    table = Table(title="Latency Statistics (ms)", show_header=True)
    table.add_column("Tool", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Min", justify="right")
    table.add_column("P50 (Median)", justify="right", style="bold")
    table.add_column("P95", justify="right", style="bold")
    table.add_column("P99", justify="right")
    table.add_column("Max", justify="right")
    table.add_column("Mean", justify="right")

    for tool_name in tool_names:
        latencies = latencies_by_tool[tool_name]
        if latencies:
            latencies_sorted = sorted(latencies)
            count = len(latencies)

            # Calculate percentiles
            p50 = statistics.median(latencies_sorted)
            p95 = latencies_sorted[int(0.95 * count)] if count > 0 else 0
            p99 = latencies_sorted[int(0.99 * count)] if count > 0 else 0
            min_lat = min(latencies_sorted)
            max_lat = max(latencies_sorted)
            mean_lat = statistics.mean(latencies_sorted)

            table.add_row(
                tool_name,
                str(count),
                f"{min_lat:.1f}",
                f"{p50:.1f}",
                f"{p95:.1f}",
                f"{p99:.1f}",
                f"{max_lat:.1f}",
                f"{mean_lat:.1f}",
            )
        else:
            table.add_row(tool_name, "0", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A")

    console.print(table)


def _display_llm_evaluation_summary(results: List, tool_names: List[str]):
    """Display summary of LLM evaluations across all queries."""
    # Map internal names to display names
    display_names = {"tafsir": "vectara", "goodmem": "goodmem"}

    # Collect evaluation data
    total_scores = {name: 0 for name in tool_names}
    win_counts = {name: 0 for name in tool_names}
    tie_count = 0
    evaluated_count = 0

    for result in results:
        if result.llm_evaluation:
            evaluated_count += 1

            # Count wins
            winner = result.llm_evaluation.winner
            if winner:
                winner_lower = winner.lower()
                matched = False
                for name in tool_names:
                    if (
                        name.lower() in winner_lower
                        or display_names.get(name, name).lower() in winner_lower
                    ):
                        win_counts[name] += 1
                        matched = True
                        break
                if not matched:
                    tie_count += 1
            else:
                tie_count += 1

            # Sum scores
            for name in tool_names:
                score = result.llm_evaluation.quality_scores.get(name, 0)
                # Normalize to 100 scale if needed
                if score > 0 and score <= 10:
                    score *= 10
                total_scores[name] += score

    if evaluated_count == 0:
        console.print("\n[yellow]No LLM evaluations available[/yellow]")
        return

    # Create summary table
    table = Table(title="LLM Evaluation Summary", show_header=True)
    table.add_column("Tool", style="cyan")
    table.add_column("Wins", justify="right", style="bold")
    table.add_column("Avg Quality", justify="right")

    for tool_name in tool_names:
        avg_score = total_scores[tool_name] / evaluated_count
        wins = win_counts[tool_name]

        # Use display name
        display_name = display_names.get(tool_name, tool_name)

        # Style the row based on performance
        if wins == max(win_counts.values()) and wins > 0:
            tool_display = f"🏆 {display_name}"
        else:
            tool_display = display_name

        table.add_row(tool_display, f"{wins}/{evaluated_count}", f"{avg_score:.1f}/100")

    if tie_count > 0:
        table.add_row("TIE", f"{tie_count}/{evaluated_count}", "-")

    console.print()
    console.print(table)

    # Determine overall winner
    max_wins = max(win_counts.values())
    winners = [
        display_names.get(name, name)
        for name, count in win_counts.items()
        if count == max_wins
    ]

    if len(winners) == 1 and max_wins > 0:
        console.print(
            f"\n[bold green]Overall Winner: {winners[0].upper()}[/bold green]"
        )
    elif len(winners) > 1:
        console.print(f"\n[yellow]Tie between: {', '.join(winners)}[/yellow]")


def _generate_and_display_holistic_summary(
    results: List, tool_names: List[str], output_file: Path
):
    """Generate comprehensive holistic summary and save to file."""
    from collections import Counter, defaultdict

    # Map internal names to display names
    display_names = {"tafsir": "vectara", "goodmem": "goodmem"}

    # Collect comprehensive statistics
    query_details = []
    issue_tracker = defaultdict(int)
    theme_tracker = defaultdict(list)

    for result in results:
        if not result.llm_evaluation:
            continue

        query_info = {
            "query": result.query,
            "winner": result.llm_evaluation.winner,
            "scores": {},
            "analysis": result.llm_evaluation.analysis,
        }

        # Extract scores
        for tool_name in tool_names:
            score = result.llm_evaluation.quality_scores.get(tool_name, 0)
            # Normalize to 100 scale if needed
            if score > 0 and score <= 10:
                score *= 10
            query_info["scores"][tool_name] = score

        query_details.append(query_info)

        # Track issues mentioned in analysis
        analysis_lower = result.llm_evaluation.analysis.lower()
        if "duplicate" in analysis_lower or "repetition" in analysis_lower:
            issue_tracker["duplicates"] += 1
            theme_tracker["duplicates"].append(result.query)
        if (
            "fragment" in analysis_lower
            or "incomplete" in analysis_lower
            or "truncat" in analysis_lower
        ):
            issue_tracker["fragmentation"] += 1
            theme_tracker["fragmentation"].append(result.query)
        if "citation" in analysis_lower:
            issue_tracker["citation_issues"] += 1
            theme_tracker["citation_issues"].append(result.query)
        if "coherent" in analysis_lower or "cohesive" in analysis_lower:
            issue_tracker["coherence_mentioned"] += 1
            theme_tracker["coherence"].append(result.query)

    # Generate markdown summary
    md_lines = ["# RAG Comparison: Holistic Summary\n"]
    md_lines.append(f"**Total Queries Evaluated:** {len(query_details)}\n")
    md_lines.append(
        f"**Tools Compared:** {', '.join(display_names.get(n, n) for n in tool_names)}\n"
    )
    md_lines.append("\n---\n")

    # Section 1: Query-by-Query Breakdown
    md_lines.append("\n## 1. Query-by-Query Results\n")
    for i, qinfo in enumerate(query_details, 1):
        md_lines.append(f"\n### Query {i}: \"{qinfo['query']}\"\n")

        # Winner
        winner_display = qinfo["winner"] if qinfo["winner"] else "TIE"
        if qinfo["winner"]:
            for tool_name in tool_names:
                winner_lower = qinfo["winner"].lower()
                if (
                    tool_name.lower() in winner_lower
                    or display_names.get(tool_name, tool_name).lower() in winner_lower
                ):
                    winner_display = f"🏆 {display_names.get(tool_name, tool_name)}"
                    break
        md_lines.append(f"**Winner:** {winner_display}\n")

        # Scores
        md_lines.append("**Quality Scores:**\n")
        for tool_name in tool_names:
            score = qinfo["scores"].get(tool_name, 0)
            display_name = display_names.get(tool_name, tool_name)
            md_lines.append(f"- {display_name}: {score:.1f}/100\n")

        # Full analysis (no truncation)
        md_lines.append(f"\n**Analysis:**\n\n{qinfo['analysis']}\n")

    # Section 2: Common Themes
    md_lines.append("\n---\n\n## 2. Common Themes\n")

    # Calculate win distribution
    win_counts = Counter()
    for qinfo in query_details:
        if qinfo["winner"]:
            winner_lower = qinfo["winner"].lower()
            for tool_name in tool_names:
                if (
                    tool_name.lower() in winner_lower
                    or display_names.get(tool_name, tool_name).lower() in winner_lower
                ):
                    win_counts[tool_name] += 1
                    break

    md_lines.append("\n### Win Distribution\n")
    for tool_name in tool_names:
        display_name = display_names.get(tool_name, tool_name)
        wins = win_counts.get(tool_name, 0)
        percentage = (wins / len(query_details) * 100) if query_details else 0
        md_lines.append(
            f"- **{display_name}**: {wins}/{len(query_details)} queries ({percentage:.1f}%)\n"
        )

    # Calculate average scores
    md_lines.append("\n### Average Quality Scores\n")
    for tool_name in tool_names:
        display_name = display_names.get(tool_name, tool_name)
        avg_score = (
            sum(q["scores"].get(tool_name, 0) for q in query_details)
            / len(query_details)
            if query_details
            else 0
        )
        md_lines.append(f"- **{display_name}**: {avg_score:.1f}/100\n")

    # Issue frequency
    if issue_tracker:
        md_lines.append("\n### Recurring Issues\n")
        for issue_type, count in sorted(
            issue_tracker.items(), key=lambda x: x[1], reverse=True
        ):
            percentage = (count / len(query_details) * 100) if query_details else 0
            issue_name = issue_type.replace("_", " ").title()
            md_lines.append(
                f"- **{issue_name}**: {count}/{len(query_details)} queries ({percentage:.1f}%)\n"
            )
            # List affected queries
            if theme_tracker[issue_type]:
                affected = theme_tracker[issue_type][:3]  # Show first 3
                examples = ", ".join(f'"{q}"' for q in affected)
                md_lines.append(f"  - Examples: {examples}\n")

    # Section 3: Key Differentiators
    md_lines.append("\n---\n\n## 3. Key Differentiators\n")

    # Determine winner
    max_wins = max(win_counts.values()) if win_counts else 0
    overall_winner = None
    for tool_name, wins in win_counts.items():
        if wins == max_wins and max_wins > 0:
            overall_winner = tool_name
            break

    if overall_winner:
        winner_display = display_names.get(overall_winner, overall_winner)
        loser_names = [
            display_names.get(n, n) for n in tool_names if n != overall_winner
        ]
        loser_display = loser_names[0] if loser_names else "other tools"

        md_lines.append(f"\n### What makes {winner_display} better?\n")

        # Analyze winning queries for patterns
        winner_analyses = []
        for qinfo in query_details:
            if qinfo["winner"]:
                winner_lower = qinfo["winner"].lower()
                if (
                    overall_winner.lower() in winner_lower
                    or display_names.get(overall_winner, overall_winner).lower()
                    in winner_lower
                ):
                    winner_analyses.append(qinfo["analysis"].lower())

        # Look for common positive terms in winner
        positive_terms = {
            "complete": 0,
            "comprehensive": 0,
            "coherent": 0,
            "cohesive": 0,
            "structured": 0,
            "organized": 0,
            "clear": 0,
            "relevant": 0,
            "detailed": 0,
            "thorough": 0,
            "accurate": 0,
        }

        for analysis in winner_analyses:
            for term in positive_terms:
                if term in analysis:
                    positive_terms[term] += 1

        # Show top 3 positive attributes
        top_positives = sorted(
            positive_terms.items(), key=lambda x: x[1], reverse=True
        )[:3]
        for term, count in top_positives:
            if count > 0:
                percentage = (
                    (count / len(winner_analyses) * 100) if winner_analyses else 0
                )
                md_lines.append(
                    f"- **{term.title()}**: mentioned in {count}/{len(winner_analyses)} winning queries ({percentage:.1f}%)\n"
                )

        md_lines.append(f"\n### What's wrong with {loser_display}?\n")

        # Analyze losing queries for patterns
        loser_analyses = []
        for qinfo in query_details:
            if qinfo["winner"]:
                winner_lower = qinfo["winner"].lower()
                is_loser = True
                for tool_name in tool_names:
                    if tool_name == overall_winner:
                        continue
                    if (
                        tool_name.lower() in winner_lower
                        or display_names.get(tool_name, tool_name).lower()
                        in winner_lower
                    ):
                        loser_analyses.append(qinfo["analysis"].lower())
                        break

        # Look for common negative terms
        negative_terms = {
            "duplicate": 0,
            "repetition": 0,
            "fragment": 0,
            "incomplete": 0,
            "truncat": 0,
            "disjointed": 0,
            "confusing": 0,
            "irrelevant": 0,
        }

        for analysis in loser_analyses:
            for term in negative_terms:
                if term in analysis:
                    negative_terms[term] += 1

        # Show top 3 negative attributes
        top_negatives = sorted(
            negative_terms.items(), key=lambda x: x[1], reverse=True
        )[:3]
        for term, count in top_negatives:
            if count > 0:
                percentage = (count / len(query_details) * 100) if query_details else 0
                md_lines.append(
                    f"- **{term.title()}**: mentioned in {count}/{len(query_details)} queries ({percentage:.1f}%)\n"
                )

    # Section 4: Overall Verdict
    md_lines.append("\n---\n\n## 4. Overall Verdict\n")

    if overall_winner:
        winner_display = display_names.get(overall_winner, overall_winner)
        wins = win_counts.get(overall_winner, 0)
        win_pct = (wins / len(query_details) * 100) if query_details else 0
        avg_winner_score = (
            sum(q["scores"].get(overall_winner, 0) for q in query_details)
            / len(query_details)
            if query_details
            else 0
        )

        md_lines.append(f"\n**🏆 Clear Winner: {winner_display.upper()}**\n")
        md_lines.append(
            f"\n{winner_display} won {wins} out of {len(query_details)} queries ({win_pct:.1f}%) "
        )
        md_lines.append(
            f"with an average quality score of {avg_winner_score:.1f}/100.\n"
        )

        # Recommendation
        md_lines.append(
            f"\n**Recommendation:** Use {winner_display} for production queries based on superior "
        )
        md_lines.append("result quality, coherence, and completeness.\n")
    else:
        md_lines.append("\n**Result:** No clear winner - further evaluation needed.\n")

    # Write to file
    summary_content = "".join(md_lines)
    output_file.write_text(summary_content)

    # Display in terminal
    console.print("\n" + "=" * 80)
    console.print(
        Panel.fit(
            "[bold cyan]Holistic Summary Generated[/bold cyan]", border_style="cyan"
        )
    )
    console.print(f"[green]✓ Full summary saved to: {output_file}[/green]\n")

    # Display condensed version in terminal
    console.print("[bold]== Quick Summary ==[/bold]\n")

    # Show win counts
    for tool_name in tool_names:
        display_name = display_names.get(tool_name, tool_name)
        wins = win_counts.get(tool_name, 0)
        percentage = (wins / len(query_details) * 100) if query_details else 0
        avg_score = (
            sum(q["scores"].get(tool_name, 0) for q in query_details)
            / len(query_details)
            if query_details
            else 0
        )

        if wins == max_wins and max_wins > 0:
            console.print(
                f"🏆 [bold green]{display_name}[/bold green]: {wins}/{len(query_details)} wins ({percentage:.1f}%), avg score {avg_score:.1f}/100"
            )
        else:
            console.print(
                f"   [cyan]{display_name}[/cyan]: {wins}/{len(query_details)} wins ({percentage:.1f}%), avg score {avg_score:.1f}/100"
            )

    # Show top issues
    if issue_tracker:
        console.print("\n[bold]Top Issues:[/bold]")
        for issue_type, count in sorted(
            issue_tracker.items(), key=lambda x: x[1], reverse=True
        )[:3]:
            percentage = (count / len(query_details) * 100) if query_details else 0
            issue_name = issue_type.replace("_", " ").title()
            console.print(
                f"  • {issue_name}: {count}/{len(query_details)} queries ({percentage:.1f}%)"
            )

    console.print("\n" + "=" * 80 + "\n")


def _display_stats_table(stats: dict):
    """Display statistics in a table format."""
    table = Table(title="Performance Statistics", show_header=True)
    table.add_column("Tool", style="cyan")
    table.add_column("Results", justify="right")
    table.add_column("Latency (ms)", justify="right")

    for tool_name in stats.get("tools_compared", []):
        count = stats["result_counts"].get(tool_name, 0)
        latency = stats["latencies_ms"].get(tool_name, "N/A")

        if isinstance(latency, float):
            latency_str = f"{latency:.1f}"
        else:
            latency_str = str(latency)

        table.add_row(tool_name, str(count), latency_str)

    console.print(table)


def main():
    """Main entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
