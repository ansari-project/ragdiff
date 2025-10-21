"""Command-line interface for RAGDiff.

New CLI structure (Phase 3):
- query: Run a single query against ONE RAG system
- run: Run batch queries from a file
- compare: Compare multiple RAG systems on the same query (live)

Legacy commands (deprecated):
- batch: Use 'run' instead
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

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
    name="ragdiff",
    help="RAGDiff - Compare and evaluate RAG systems",
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
def query(
    query_text: str = typer.Argument(..., help="Search query to run"),
    tool: str = typer.Option(..., "--tool", "-t", help="RAG tool to query"),
    config_file: str = typer.Option(
        "configs/tafsir.yaml", "--config", "-c", help="Path to configuration file"
    ),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results to retrieve"),
    output_format: str = typer.Option(
        "display",
        "--format",
        "-f",
        help="Output format: display, json",
    ),
    output_file: Optional[str] = typer.Option(
        None, "--output", "-o", help="Save output to file"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
):
    """Run a single query against ONE RAG system.

    Examples:
        ragdiff query "What is RAG?" --tool vectara --config config.yaml
        ragdiff query "coral meaning" -t goodmem -k 10 --format json
    """
    setup_logging(verbose)

    try:
        # Load configuration
        if not Path(config_file).exists():
            console.print(f"[red]Configuration file not found: {config_file}[/red]")
            raise typer.Exit(1)

        config = Config(Path(config_file))
        config.validate()

        # Check tool exists
        if tool not in config.tools:
            console.print(f"[red]Tool '{tool}' not found in configuration[/red]")
            console.print(f"Available tools: {', '.join(config.tools.keys())}")
            raise typer.Exit(1)

        # Create adapter
        console.print(f"[cyan]Querying {tool}...[/cyan]")
        adapter = create_adapter(tool, config.tools[tool])

        # Run query
        with console.status("[bold cyan]Running query...[/bold cyan]"):
            results = adapter.search(query_text, top_k=top_k)

        # Format output
        if output_format == "json":
            output_data = {
                "query": query_text,
                "tool": tool,
                "top_k": top_k,
                "results": [
                    {
                        "id": r.id,
                        "text": r.text,
                        "score": r.score,
                        "source": r.source,
                        "metadata": r.metadata,
                    }
                    for r in results
                ],
            }
            output = json.dumps(output_data, indent=2, ensure_ascii=False)
        else:  # display
            # Create simple table
            table = Table(title=f"Results for: {query_text}")
            table.add_column("Rank", style="cyan", width=6)
            table.add_column("Score", style="green", width=8)
            table.add_column("Source", style="yellow", width=20)
            table.add_column("Text", style="white")

            for idx, result in enumerate(results, 1):
                table.add_row(
                    str(idx),
                    f"{result.score:.3f}",
                    result.source or "N/A",
                    result.text[:200] + "..."
                    if len(result.text) > 200
                    else result.text,
                )

            console.print(table)
            console.print(
                f"\n[green]✓ Retrieved {len(results)} results from {tool}[/green]"
            )
            return  # Don't save display output to file

        # Output results
        if output_file:
            Path(output_file).write_text(output)
            console.print(f"[green]Results saved to {output_file}[/green]")
        else:
            console.print(output)

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        if verbose:
            console.print_exception()
        raise typer.Exit(1) from e


@app.command()
def run(
    queries_file: str = typer.Argument(
        ..., help="File containing queries (one per line)"
    ),
    config_file: str = typer.Option(
        "configs/tafsir.yaml", "--config", "-c", help="Path to configuration file"
    ),
    tools: list[str] = typer.Option(
        None,
        "--tool",
        "-t",
        help="Tools to query (can specify multiple). If not specified, uses all configured tools.",
    ),
    top_k: int = typer.Option(
        5, "--top-k", "-k", help="Number of results to retrieve from each tool"
    ),
    output_format: str = typer.Option(
        "jsonl",
        "--format",
        "-f",
        help="Output format: jsonl, json",
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
    """Run batch queries from a file.

    The queries file should contain one query per line.

    Examples:
        ragdiff run queries.txt --config config.yaml
        ragdiff run queries.txt -t vectara -t goodmem --evaluate
    """
    setup_logging(verbose)

    try:
        # Load configuration
        if not Path(config_file).exists():
            console.print(f"[red]Configuration file not found: {config_file}[/red]")
            raise typer.Exit(1)

        config = Config(Path(config_file))
        config.validate()

        # Load queries
        if not Path(queries_file).exists():
            console.print(f"[red]Queries file not found: {queries_file}[/red]")
            raise typer.Exit(1)

        queries = [
            line.strip()
            for line in Path(queries_file).read_text().splitlines()
            if line.strip()
        ]

        if not queries:
            console.print("[red]No queries found in file[/red]")
            raise typer.Exit(1)

        console.print(f"[cyan]Loaded {len(queries)} queries from {queries_file}[/cyan]")

        # Determine which tools to use
        if tools:
            tool_names = tools
        else:
            tool_names = list(config.tools.keys())

        # Create adapters
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
                    raise typer.Exit(1) from e

        if not adapters:
            console.print("[red]No tools available[/red]")
            raise typer.Exit(1)

        # Create comparison engine
        engine = ComparisonEngine(adapters)

        # Run batch comparison
        results = []
        for idx, query in enumerate(queries, 1):
            console.print(f"\n[cyan]Query {idx}/{len(queries)}: {query}[/cyan]")

            with console.status("[bold cyan]Running comparison...[/bold cyan]"):
                result = engine.run_comparison(query, top_k=top_k, parallel=parallel)

            # Run LLM evaluation if requested
            if evaluate:
                llm_config = config.get_llm_config()
                if llm_config:
                    with console.status(
                        "[bold cyan]Running LLM evaluation...[/bold cyan]"
                    ):
                        try:
                            evaluator = LLMEvaluator(
                                model=llm_config.get(
                                    "model", "claude-sonnet-4-20250514"
                                ),
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

            results.append(result)
            console.print(f"[green]✓ Query {idx} complete[/green]")

        # Format output
        if output_format == "json":
            output = json.dumps(
                [r.to_dict() for r in results], indent=2, ensure_ascii=False
            )
        else:  # jsonl
            output = "\n".join(
                json.dumps(r.to_dict(), ensure_ascii=False) for r in results
            )

        # Output results
        if output_file:
            Path(output_file).write_text(output)
            console.print(f"\n[green]Results saved to {output_file}[/green]")
        else:
            console.print(output)

        # Summary
        console.print(
            f"\n[green]✓ Completed {len(queries)} queries across {len(adapters)} tools[/green]"
        )

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        if verbose:
            console.print_exception()
        raise typer.Exit(1) from e


@app.command()
def compare(
    query: str = typer.Argument(..., help="Search query to run against all tools"),
    tools: list[str] = typer.Option(
        None,
        "--tool",
        "-t",
        help="Tools to compare (can specify multiple). If not specified, uses all configured tools.",
    ),
    top_k: int = typer.Option(
        5, "--top-k", "-k", help="Number of results to retrieve from each tool"
    ),
    config_file: str = typer.Option(
        "configs/tafsir.yaml", "--config", "-c", help="Path to configuration file"
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
    """Compare multiple RAG systems on the same query.

    Runs the query against all specified tools and shows results side-by-side.

    Examples:
        ragdiff compare "What is RAG?" --config config.yaml
        ragdiff compare "coral meaning" -t vectara -t goodmem --evaluate
    """
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
                    raise typer.Exit(1) from e

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
            tool_names_list = list(result.tool_results.keys())
            header: list[str] = ["query", "timestamp"]
            for tool_name in tool_names_list:
                header.extend([f"{tool_name}_count", f"{tool_name}_latency_ms"])
            writer.writerow(header)
            row: list[str] = [result.query, result.timestamp.isoformat()]
            for tool_name in tool_names_list:
                tool_results = result.tool_results.get(tool_name, [])
                count = len(tool_results)
                latency = tool_results[0].latency_ms if tool_results else 0
                row.extend([str(count), f"{latency:.1f}"])
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
        raise typer.Exit(1) from e


# Legacy command - deprecated
@app.command(name="batch", deprecated=True, hidden=True)
def batch_deprecated(
    queries_file: str = typer.Argument(
        ..., help="File containing queries (one per line)"
    ),
    config_file: str = typer.Option(
        "configs/tafsir.yaml", "--config", "-c", help="Path to configuration file"
    ),
    tools: list[str] = typer.Option(
        None,
        "--tool",
        "-t",
        help="Tools to query",
    ),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results"),
    output_format: str = typer.Option("jsonl", "--format", "-f", help="Output format"),
    output_file: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file"
    ),
    parallel: bool = typer.Option(
        True, "--parallel/--sequential", help="Parallel execution"
    ),
    evaluate: bool = typer.Option(
        False, "--evaluate/--no-evaluate", help="LLM evaluation"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
):
    """[DEPRECATED] Use 'run' instead. Run batch queries from a file."""
    console.print(
        "[yellow]Warning: 'batch' command is deprecated. Use 'run' instead.[/yellow]"
    )

    # Forward to run command
    from typer.testing import CliRunner

    runner = CliRunner()

    args = ["run", queries_file, "--config", config_file]
    if tools:
        for t in tools:
            args.extend(["--tool", t])
    args.extend(["--top-k", str(top_k)])
    args.extend(["--format", output_format])
    if output_file:
        args.extend(["--output", output_file])
    args.append("--parallel" if parallel else "--sequential")
    args.append("--evaluate" if evaluate else "--no-evaluate")
    if verbose:
        args.append("--verbose")

    result = runner.invoke(app, args)
    raise typer.Exit(result.exit_code)


@app.command()
def list_tools(
    config_file: str = typer.Option(
        "configs/tafsir.yaml", "--config", "-c", help="Path to configuration file"
    ),
):
    """List all available and configured tools."""
    try:
        # Show available adapters
        available = get_available_adapters()
        console.print("\n[bold cyan]Available Adapters:[/bold cyan]")
        for adapter_name in sorted(available):
            console.print(f"  • {adapter_name}")

        # Show configured tools
        if Path(config_file).exists():
            config = Config(Path(config_file))
            console.print(
                f"\n[bold cyan]Configured Tools in {config_file}:[/bold cyan]"
            )
            for tool_name, tool_config in config.tools.items():
                adapter_used = tool_config.adapter or tool_name
                console.print(f"  • {tool_name} (uses {adapter_used} adapter)")
        else:
            console.print(f"\n[yellow]Config file not found: {config_file}[/yellow]")

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1) from e


@app.command()
def validate_config(
    config_file: str = typer.Argument(
        ..., help="Path to configuration file to validate"
    ),
):
    """Validate a configuration file."""
    try:
        if not Path(config_file).exists():
            console.print(f"[red]Configuration file not found: {config_file}[/red]")
            raise typer.Exit(1)

        console.print(f"[cyan]Validating {config_file}...[/cyan]")
        config = Config(Path(config_file))
        config.validate()

        console.print("[green]✓ Configuration is valid[/green]")

        # Show summary
        console.print("\n[bold]Summary:[/bold]")
        console.print(f"  Tools: {len(config.tools)}")
        for tool_name in config.tools:
            console.print(f"    • {tool_name}")

    except Exception as e:
        console.print(f"[red]✗ Validation failed: {str(e)}[/red]")
        raise typer.Exit(1) from e


@app.command()
def quick_test(
    config_file: str = typer.Option(
        "configs/tafsir.yaml", "--config", "-c", help="Path to configuration file"
    ),
    query: str = typer.Option("test", "--query", "-q", help="Test query to use"),
):
    """Quick test to verify all configured tools are working."""
    try:
        # Load configuration
        if not Path(config_file).exists():
            console.print(f"[red]Configuration file not found: {config_file}[/red]")
            raise typer.Exit(1)

        config = Config(Path(config_file))
        config.validate()

        console.print(
            f"[cyan]Testing {len(config.tools)} tools with query: '{query}'[/cyan]\n"
        )

        # Test each tool
        results = {}
        for tool_name, tool_config in config.tools.items():
            console.print(f"[cyan]Testing {tool_name}...[/cyan]")

            try:
                adapter = create_adapter(tool_name, tool_config)
                search_results = adapter.search(query, top_k=1)

                if search_results:
                    results[tool_name] = "✓ Working"
                    console.print(
                        f"  [green]✓ {tool_name}: Retrieved {len(search_results)} results[/green]"
                    )
                else:
                    results[tool_name] = "⚠ No results"
                    console.print(
                        f"  [yellow]⚠ {tool_name}: No results returned[/yellow]"
                    )

            except Exception as e:
                results[tool_name] = f"✗ Error: {str(e)}"
                console.print(f"  [red]✗ {tool_name}: {str(e)}[/red]")

        # Summary
        console.print("\n[bold]Summary:[/bold]")
        working = sum(1 for v in results.values() if v.startswith("✓"))
        total = len(results)
        console.print(f"  {working}/{total} tools working")

        if working < total:
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1) from e


# Display helper functions (from old CLI)
def _display_rich_results(result: ComparisonResult):
    """Display comparison results with rich formatting."""
    # Create panels for each tool's results
    for tool_name, tool_results in result.tool_results.items():
        if not tool_results:
            continue

        # Create table for this tool
        table = Table(
            title=f"{tool_name} Results", show_header=True, header_style="bold cyan"
        )
        table.add_column("Rank", style="cyan", width=6)
        table.add_column("Score", style="green", width=8)
        table.add_column("Source", style="yellow", width=20)
        table.add_column("Text", style="white")

        for idx, r in enumerate(tool_results, 1):
            table.add_row(
                str(idx),
                f"{r.score:.3f}",
                r.source or "N/A",
                r.text[:200] + "..." if len(r.text) > 200 else r.text,
            )

        console.print(table)
        console.print()


def _display_llm_evaluation(evaluation):
    """Display LLM evaluation results."""
    if not evaluation:
        return

    panel_content = Text()
    panel_content.append("Winner: ", style="bold")
    panel_content.append(f"{evaluation.winner or 'Tie'}\n\n", style="bold green")

    if evaluation.analysis:
        panel_content.append("Analysis:\n", style="bold")
        panel_content.append(f"{evaluation.analysis}\n")

    if evaluation.quality_scores:
        panel_content.append("\nQuality Scores:\n", style="bold")
        for tool, score in evaluation.quality_scores.items():
            panel_content.append(f"  {tool}: {score}/100\n", style="cyan")

    console.print(Panel(panel_content, title="LLM Evaluation", border_style="blue"))


def _display_stats_table(stats: dict):
    """Display summary statistics table."""
    table = Table(
        title="Summary Statistics", show_header=True, header_style="bold cyan"
    )
    table.add_column("Tool", style="cyan")
    table.add_column("Results", style="green", justify="right")
    table.add_column("Avg Score", style="yellow", justify="right")
    table.add_column("Latency (ms)", style="magenta", justify="right")

    for tool_name, tool_stats in stats.items():
        table.add_row(
            tool_name,
            str(tool_stats.get("count", 0)),
            f"{tool_stats.get('avg_score', 0):.3f}",
            f"{tool_stats.get('latency_ms', 0):.1f}",
        )

    console.print(table)


if __name__ == "__main__":
    app()
