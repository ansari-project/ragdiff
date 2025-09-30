"""Command-line interface for RAG comparison tool."""

import sys
import os
from pathlib import Path
from typing import Optional, List
import logging
import json

from dotenv import load_dotenv
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import print as rprint

from .core.config import Config
from .core.models import ComparisonResult
from .adapters.factory import create_adapter, get_available_adapters
from .comparison.engine import ComparisonEngine
from .display.formatter import ComparisonFormatter
from .evaluation.evaluator import LLMEvaluator

# Load environment variables from .env file
load_dotenv()

# Initialize Typer app
app = typer.Typer(
    name="rag-compare",
    help="Compare RAG tool results side-by-side",
    add_completion=False
)

console = Console()
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S"
    )


@app.command()
def compare(
    query: str = typer.Argument(..., help="Search query to run against all tools"),
    tools: List[str] = typer.Option(
        None,
        "--tool", "-t",
        help="Tools to compare (can specify multiple). If not specified, uses all configured tools."
    ),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results to retrieve from each tool"),
    config_file: str = typer.Option("configs/mawsuah.yaml", "--config", "-c", help="Path to configuration file"),
    output_format: str = typer.Option(
        "display",
        "--format", "-f",
        help="Output format: display, json, jsonl, csv, markdown, summary"
    ),
    output_file: Optional[str] = typer.Option(None, "--output", "-o", help="Save output to file"),
    parallel: bool = typer.Option(True, "--parallel/--sequential", help="Run searches in parallel or sequential"),
    evaluate: bool = typer.Option(False, "--evaluate/--no-evaluate", help="Enable LLM evaluation using Claude"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
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
            console.print("[yellow]Warning: Comparison works best with 2 or more tools[/yellow]")

        # Create adapters for selected tools
        console.print(f"[cyan]Initializing {len(tool_names)} tools...[/cyan]")
        adapters = {}
        for tool_name in tool_names:
            if tool_name not in config.tools:
                console.print(f"[red]Tool '{tool_name}' not found in configuration[/red]")
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
                            api_key=os.getenv(llm_config.get("api_key_env", "ANTHROPIC_API_KEY"))
                        )
                        result.llm_evaluation = evaluator.evaluate(result)
                        console.print("[green]✓ LLM evaluation complete[/green]")
                    except Exception as e:
                        console.print(f"[yellow]Warning: LLM evaluation failed: {e}[/yellow]")
            else:
                console.print("[yellow]LLM evaluation requested but not configured[/yellow]")

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
                header.extend([f"{tool_name}_count", f"{tool_name}_avg_score", f"{tool_name}_latency_ms"])
            writer.writerow(header)
            row = [result.query, result.timestamp.isoformat()]
            for tool_name in tool_names:
                tool_results = result.tool_results.get(tool_name, [])
                count = len(tool_results)
                avg_score = sum(r.score for r in tool_results) / count if count > 0 else 0
                latency = tool_results[0].latency_ms if tool_results else 0
                row.extend([count, f"{avg_score:.3f}", f"{latency:.1f}"])
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
    config_file: str = typer.Option("configs/mawsuah.yaml", "--config", "-c", help="Path to configuration file"),
):
    """List all available and configured tools."""
    console.print("[bold]Available Tool Adapters:[/bold]")
    for adapter_name in get_available_adapters():
        console.print(f"  • {adapter_name}")

    if Path(config_file).exists():
        config = Config(Path(config_file))
        console.print("\n[bold]Configured Tools:[/bold]")
        for tool_name, tool_config in config.tools.items():
            status = "[green]✓[/green]" if os.getenv(tool_config.api_key_env) else "[red]✗ (missing API key)[/red]"
            console.print(f"  {status} {tool_name} - {tool_config.api_key_env}")


@app.command()
def validate_config(
    config_file: str = typer.Option("configs/mawsuah.yaml", "--config", "-c", help="Path to configuration file"),
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

        console.print(f"\n[bold]LLM configuration:[/bold]")
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
    queries_file: str = typer.Argument(..., help="Path to file with queries (one per line)"),
    tools: List[str] = typer.Option(
        None,
        "--tool", "-t",
        help="Tools to compare (can specify multiple). If not specified, uses all configured tools."
    ),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results to retrieve from each tool"),
    config_file: str = typer.Option("configs/mawsuah.yaml", "--config", "-c", help="Path to configuration file"),
    output_dir: str = typer.Option("outputs", "--output-dir", "-o", help="Directory to save batch results"),
    output_format: str = typer.Option("jsonl", "--format", "-f", help="Output format: json, jsonl, csv"),
    evaluate: bool = typer.Option(False, "--evaluate/--no-evaluate", help="Enable LLM evaluation using Claude"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
):
    """Run batch comparison on multiple queries from a file."""
    setup_logging(verbose)

    try:
        # Load queries
        queries_path = Path(queries_file)
        if not queries_path.exists():
            console.print(f"[red]Queries file not found: {queries_file}[/red]")
            raise typer.Exit(1)

        queries = [line.strip() for line in queries_path.read_text().split('\n') if line.strip()]
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
                console.print(f"[red]Tool '{tool_name}' not found in configuration[/red]")
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
                    api_key=os.getenv(llm_config.get("api_key_env", "ANTHROPIC_API_KEY"))
                )

        # Process queries
        results = []
        import csv
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_path / f"batch_results_{timestamp}.{output_format}"

        with console.status("[bold cyan]Processing queries...[/bold cyan]") as status:
            for idx, query in enumerate(queries, 1):
                status.update(f"[bold cyan]Processing query {idx}/{len(queries)}: {query[:50]}...[/bold cyan]")

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
            with open(output_file, 'w') as f:
                json.dump([result.to_dict() for result in results], f, indent=2)
        elif output_format == "jsonl":
            with open(output_file, 'w') as f:
                for result in results:
                    json.dump(result.to_dict(), f)
                    f.write('\n')
        elif output_format == "csv":
            with open(output_file, 'w', newline='') as f:
                writer = csv.writer(f)
                # Header
                header = ["query", "timestamp"]
                for tool_name in tool_names:
                    header.extend([f"{tool_name}_count", f"{tool_name}_avg_score", f"{tool_name}_latency_ms"])
                if evaluate:
                    header.extend(["llm_winner"] + [f"llm_score_{name}" for name in tool_names])
                writer.writerow(header)

                # Data rows
                for result in results:
                    row = [result.query, result.timestamp.isoformat()]
                    for tool_name in tool_names:
                        tool_results = result.tool_results.get(tool_name, [])
                        count = len(tool_results)
                        avg_score = sum(r.score for r in tool_results) / count if count > 0 else 0
                        latency = tool_results[0].latency_ms if tool_results else 0
                        row.extend([count, f"{avg_score:.3f}", f"{latency:.1f}"])

                    if evaluate and result.llm_evaluation:
                        row.append(result.llm_evaluation.winner or "tie")
                        for tool_name in tool_names:
                            row.append(result.llm_evaluation.quality_scores.get(tool_name, ""))

                    writer.writerow(row)

        console.print(f"\n[green]✓ Processed {len(queries)} queries[/green]")
        console.print(f"[green]✓ Results saved to {output_file}[/green]")

        # Calculate and display percentile latencies
        _display_batch_latency_stats(results, tool_names)

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


@app.command()
def quick_test(
    config_file: str = typer.Option("configs/mawsuah.yaml", "--config", "-c", help="Path to configuration file"),
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
        verbose=False
    )


def _display_rich_results(result: ComparisonResult):
    """Display results using rich formatting."""
    # Header
    console.print(Panel.fit(
        f"[bold cyan]Query:[/bold cyan] {result.query}",
        title="RAG Comparison Results"
    ))

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

                console.print(Panel(
                    panel_content,
                    title=f"[bold]{tool_name.upper()}[/bold]",
                    border_style="cyan"
                ))


def _display_llm_evaluation(evaluation):
    """Display LLM evaluation results."""
    from .core.models import LLMEvaluation

    eval_text = Text()

    # Winner
    if evaluation.winner:
        eval_text.append(f"🏆 Winner: ", style="bold")
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

    console.print(Panel(eval_text, title="[bold]LLM Evaluation[/bold]", border_style="green"))


def _display_batch_latency_stats(results: List[ComparisonResult], tool_names: List[str]):
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
                f"{mean_lat:.1f}"
            )
        else:
            table.add_row(tool_name, "0", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A")

    console.print(table)


def _display_stats_table(stats: dict):
    """Display statistics in a table format."""
    table = Table(title="Performance Statistics", show_header=True)
    table.add_column("Tool", style="cyan")
    table.add_column("Results", justify="right")
    table.add_column("Avg Score", justify="right")
    table.add_column("Latency (ms)", justify="right")

    for tool_name in stats.get("tools_compared", []):
        count = stats["result_counts"].get(tool_name, 0)
        avg_score = stats["average_scores"].get(tool_name, 0)
        latency = stats["latencies_ms"].get(tool_name, "N/A")

        if isinstance(latency, float):
            latency_str = f"{latency:.1f}"
        else:
            latency_str = str(latency)

        table.add_row(
            tool_name,
            str(count),
            f"{avg_score:.3f}" if avg_score else "N/A",
            latency_str
        )

    console.print(table)


def main():
    """Main entry point for CLI."""
    app()


if __name__ == "__main__":
    main()