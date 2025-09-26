"""Command-line interface for RAG comparison tool."""

import sys
import os
from pathlib import Path
from typing import Optional, List
import logging
import json

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
    config_file: str = typer.Option("configs/tools.yaml", "--config", "-c", help="Path to configuration file"),
    output_format: str = typer.Option(
        "display",
        "--format", "-f",
        help="Output format: display, json, markdown, summary"
    ),
    output_file: Optional[str] = typer.Option(None, "--output", "-o", help="Save output to file"),
    parallel: bool = typer.Option(True, "--parallel/--sequential", help="Run searches in parallel or sequential"),
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

        # Format output
        formatter = ComparisonFormatter(width=console.width)

        if output_format == "json":
            output = formatter.format_json(result, pretty=True)
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
    config_file: str = typer.Option("configs/tools.yaml", "--config", "-c", help="Path to configuration file"),
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
    config_file: str = typer.Option("configs/tools.yaml", "--config", "-c", help="Path to configuration file"),
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
def quick_test(
    config_file: str = typer.Option("configs/tools.yaml", "--config", "-c", help="Path to configuration file"),
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