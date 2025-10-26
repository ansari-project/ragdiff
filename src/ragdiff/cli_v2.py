"""RAGDiff v2.0 CLI commands.

This module provides CLI commands for the v2.0 domain-based architecture:
- run: Execute a query set against a provider
- compare: Compare multiple runs using LLM evaluation

Example:
    # Execute a run
    $ ragdiff run tafsir vectara-default test-queries --concurrency 10

    # Compare runs
    $ ragdiff compare tafsir 550e 660e --model claude-3-5-sonnet-20241022
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from .comparison import compare_runs
from .core.errors import ComparisonError, RunError
from .execution import execute_run

app = typer.Typer(
    name="ragdiff-v2",
    help="RAGDiff v2.0 - Domain-based RAG provider comparison",
    no_args_is_help=True,
)

console = Console()


@app.command()
def run(
    domain: str = typer.Argument(..., help="Domain name (e.g., 'tafsir')"),
    provider: str = typer.Argument(..., help="Provider name (e.g., 'vectara-default')"),
    query_set: str = typer.Argument(..., help="Query set name (e.g., 'test-queries')"),
    concurrency: int = typer.Option(10, help="Maximum concurrent queries"),
    timeout: float = typer.Option(30.0, help="Timeout per query in seconds"),
    domains_dir: Optional[Path] = typer.Option(
        None, help="Domains directory (default: ./domains)"
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress progress output"),
):
    """Execute a query set against a provider.

    This command:
    1. Loads the domain, provider config, and query set
    2. Creates the provider instance
    3. Executes queries in parallel
    4. Saves the run to disk

    Example:
        $ ragdiff run tafsir vectara-default test-queries
        $ ragdiff run tafsir vectara-default test-queries --concurrency 20
    """
    domains_path = Path(domains_dir) if domains_dir else Path("domains")

    try:
        # Show progress bar unless quiet mode
        if not quiet:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                # Track progress
                task = progress.add_task(
                    f"Executing run: {domain}/{provider}/{query_set}", total=100
                )

                completed_queries = 0
                total_queries = 0

                def progress_callback(current, total, successes, failures):
                    nonlocal completed_queries, total_queries
                    completed_queries = current
                    total_queries = total
                    progress.update(
                        task,
                        completed=current,
                        total=total,
                        description=f"Query {current}/{total} ({successes} ok, {failures} failed)",
                    )

                # Execute run
                result = execute_run(
                    domain=domain,
                    provider=provider,
                    query_set=query_set,
                    concurrency=concurrency,
                    per_query_timeout=timeout,
                    progress_callback=progress_callback,
                    domains_dir=domains_path,
                )

                progress.update(task, completed=total_queries, total=total_queries)
        else:
            # Quiet mode - no progress bar
            result = execute_run(
                domain=domain,
                provider=provider,
                query_set=query_set,
                concurrency=concurrency,
                per_query_timeout=timeout,
                progress_callback=None,
                domains_dir=domains_path,
            )

        # Display results
        console.print()
        console.print(f"[bold green]✓[/bold green] Run completed: {result.id}")
        console.print()

        # Summary table
        table = Table(title="Run Summary", show_header=False)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Run ID", str(result.id))
        table.add_row("Domain", result.domain)
        table.add_row("Provider", result.provider)
        table.add_row("Query Set", result.query_set)
        table.add_row("Status", f"[bold]{result.status.value}[/bold]")
        table.add_row("Total Queries", str(result.metadata.get("total_queries", 0)))
        table.add_row(
            "Successes", f"[green]{result.metadata.get('successes', 0)}[/green]"
        )
        table.add_row("Failures", f"[red]{result.metadata.get('failures', 0)}[/red]")
        table.add_row(
            "Duration",
            f"{result.metadata.get('duration_seconds', 0):.2f}s",
        )

        console.print(table)
        console.print()
        console.print(
            f"[dim]Run saved to: domains/{domain}/runs/"
            f"{result.started_at.strftime('%Y-%m-%d')}/{result.id}.json[/dim]"
        )

    except RunError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1) from e
    except Exception as e:
        console.print(f"[bold red]Unexpected error:[/bold red] {e}")
        raise typer.Exit(code=1) from e


@app.command()
def compare(
    domain: str = typer.Argument(..., help="Domain name (e.g., 'tafsir')"),
    run_ids: list[str] = typer.Argument(
        ..., help="Run IDs to compare (full UUID or short prefix like '550e')"
    ),
    model: Optional[str] = typer.Option(
        None, help="LLM model override (default: use domain config)"
    ),
    temperature: Optional[float] = typer.Option(
        None, help="Temperature override (default: use domain config)"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file path (default: print to console)"
    ),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format: table, json, markdown"
    ),
    domains_dir: Optional[Path] = typer.Option(
        None, help="Domains directory (default: ./domains)"
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress progress output"),
):
    """Compare multiple runs using LLM evaluation.

    This command:
    1. Loads all runs from disk
    2. Validates runs are from same domain and query set
    3. For each query, evaluates results using LLM
    4. Saves comparison to disk
    5. Displays or exports results

    Example:
        $ ragdiff compare tafsir 550e 660e
        $ ragdiff compare tafsir run1 run2 --model claude-3-5-sonnet-20241022
        $ ragdiff compare tafsir 550e 660e --format json --output comparison.json
    """
    domains_path = Path(domains_dir) if domains_dir else Path("domains")

    try:
        # Show spinner unless quiet mode
        if not quiet:
            with console.status(
                f"[bold green]Comparing {len(run_ids)} runs...", spinner="dots"
            ):
                result = compare_runs(
                    domain=domain,
                    run_ids=run_ids,
                    model=model,
                    temperature=temperature,
                    domains_dir=domains_path,
                )
        else:
            result = compare_runs(
                domain=domain,
                run_ids=run_ids,
                model=model,
                temperature=temperature,
                domains_dir=domains_path,
            )

        # Display or export results based on format
        if format == "json":
            _output_json(result, output)
        elif format == "markdown":
            _output_markdown(result, output)
        else:  # table
            _output_table(result, output)

        # Show completion message
        if not output:
            console.print()
            console.print(
                f"[dim]Comparison saved to: domains/{domain}/comparisons/"
                f"{result.created_at.strftime('%Y-%m-%d')}/{result.id}.json[/dim]"
            )

    except ComparisonError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1) from e
    except Exception as e:
        console.print(f"[bold red]Unexpected error:[/bold red] {e}")
        raise typer.Exit(code=1) from e


def _output_table(comparison, output_path):
    """Output comparison results as a table."""
    if output_path:
        console.print(
            "[yellow]Warning:[/yellow] Table format only supports console output"
        )
        console.print(
            "[dim]Use --format json or --format markdown for file output[/dim]"
        )

    console.print()
    console.print(f"[bold]Comparison {comparison.id}[/bold]")
    console.print(f"Domain: {comparison.domain}")
    console.print(f"Runs: {', '.join(str(r)[:8] for r in comparison.runs)}")
    console.print()

    # Summary
    table = Table(title="Comparison Summary", show_header=False)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    table.add_row(
        "Total Evaluations", str(comparison.metadata.get("total_evaluations", 0))
    )
    table.add_row(
        "Successful",
        f"[green]{comparison.metadata.get('successful_evaluations', 0)}[/green]",
    )
    table.add_row(
        "Failed", f"[red]{comparison.metadata.get('failed_evaluations', 0)}[/red]"
    )
    table.add_row("Model", comparison.evaluator_config.model)
    table.add_row("Temperature", str(comparison.evaluator_config.temperature))

    console.print(table)
    console.print()

    # Show sample evaluations
    console.print("[bold]Sample Evaluations:[/bold]")
    for i, eval_result in enumerate(comparison.evaluations[:5], 1):
        console.print(f"\n[cyan]{i}. Query:[/cyan] {eval_result.query[:80]}...")
        if "winner" in eval_result.evaluation:
            winner = eval_result.evaluation.get("winner", "unknown")
            console.print(f"   [green]Winner:[/green] {winner}")
        if "reasoning" in eval_result.evaluation:
            reasoning = eval_result.evaluation.get("reasoning", "")[:150]
            console.print(f"   [dim]Reasoning:[/dim] {reasoning}...")
        if "_metadata" in eval_result.evaluation:
            metadata = eval_result.evaluation["_metadata"]
            cost = metadata.get("cost", 0)
            tokens = metadata.get("total_tokens", 0)
            console.print(f"   [dim]Cost: ${cost:.4f}, Tokens: {tokens}[/dim]")

    if len(comparison.evaluations) > 5:
        console.print(f"\n[dim]... and {len(comparison.evaluations) - 5} more[/dim]")


def _output_json(comparison, output_path):
    """Output comparison results as JSON."""

    json_str = comparison.model_dump_json(indent=2)

    if output_path:
        with open(output_path, "w") as f:
            f.write(json_str)
        console.print(f"[green]✓[/green] Comparison exported to {output_path}")
    else:
        console.print(json_str)


def _output_markdown(comparison, output_path):
    """Output comparison results as Markdown."""
    lines = [
        f"# Comparison {comparison.id}",
        "",
        f"**Domain:** {comparison.domain}",
        f"**Runs:** {', '.join(str(r)[:8] for r in comparison.runs)}",
        f"**Model:** {comparison.evaluator_config.model}",
        f"**Temperature:** {comparison.evaluator_config.temperature}",
        "",
        "## Summary",
        "",
        f"- Total Evaluations: {comparison.metadata.get('total_evaluations', 0)}",
        f"- Successful: {comparison.metadata.get('successful_evaluations', 0)}",
        f"- Failed: {comparison.metadata.get('failed_evaluations', 0)}",
        "",
        "## Evaluations",
        "",
    ]

    for i, eval_result in enumerate(comparison.evaluations, 1):
        lines.append(f"### {i}. {eval_result.query}")
        lines.append("")

        if eval_result.reference:
            lines.append(f"**Reference:** {eval_result.reference}")
            lines.append("")

        if "winner" in eval_result.evaluation:
            lines.append(
                f"**Winner:** {eval_result.evaluation.get('winner', 'unknown')}"
            )
            lines.append("")

        if "reasoning" in eval_result.evaluation:
            lines.append(
                f"**Reasoning:** {eval_result.evaluation.get('reasoning', '')}"
            )
            lines.append("")

        if "_metadata" in eval_result.evaluation:
            metadata = eval_result.evaluation["_metadata"]
            lines.append(
                f"**Cost:** ${metadata.get('cost', 0):.4f}, "
                f"**Tokens:** {metadata.get('total_tokens', 0)}"
            )
            lines.append("")

    markdown = "\n".join(lines)

    if output_path:
        with open(output_path, "w") as f:
            f.write(markdown)
        console.print(f"[green]✓[/green] Comparison exported to {output_path}")
    else:
        console.print(markdown)


if __name__ == "__main__":
    app()
