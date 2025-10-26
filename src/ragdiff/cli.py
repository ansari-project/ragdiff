"""Command-line interface for RAGDiff v2.0.

RAGDiff v2.0 uses a domain-based architecture for comparing RAG providers.

Commands:
- run: Execute a query set against a provider
- compare: Compare multiple runs using LLM evaluation
- generate-adapter: Generate OpenAPI adapter configuration
"""

from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
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
from .core.logging import setup_logging
from .execution import execute_run

# Load environment variables from .env file
load_dotenv()

# Initialize Typer app
app = typer.Typer(
    name="ragdiff",
    help="RAGDiff v2.0 - Domain-based RAG provider comparison",
    add_completion=False,
    no_args_is_help=True,
)

# Initialize Rich console for output
console = Console()


# ============================================================================
# Run Command
# ============================================================================


@app.command()
def run(
    domain_dir: Path = typer.Option(
        ...,
        "--domain-dir",
        "-d",
        help="Path to domain directory (e.g., 'examples/squad-demo/domains/squad')",
    ),
    provider: str = typer.Option(
        ..., "--provider", "-p", help="Provider name (e.g., 'vectara-default')"
    ),
    query_set: str = typer.Option(
        ..., "--query-set", "-q", help="Query set name (e.g., 'test-queries')"
    ),
    label: Optional[str] = typer.Option(
        None,
        "--label",
        "-l",
        help="Label for this run (auto-generated if not provided)",
    ),
    concurrency: int = typer.Option(10, help="Maximum concurrent queries"),
    timeout: float = typer.Option(30.0, help="Timeout per query in seconds"),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress progress output"),
):
    """Execute a query set against a provider.

    This command:
    1. Loads the domain, provider config, and query set
    2. Creates the provider instance
    3. Executes queries in parallel
    4. Saves the run to disk

    Example:
        $ ragdiff run --domain-dir domains/tafsir --provider vectara-default --query-set test-queries
        $ ragdiff run -d examples/squad-demo/domains/squad -p faiss-small -q test-queries --concurrency 20
    """
    # Extract domain name from domain_dir path
    domain_dir = Path(domain_dir).resolve()
    domain = domain_dir.name
    domains_path = domain_dir.parent

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
                    label=label,
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
                label=label,
                concurrency=concurrency,
                per_query_timeout=timeout,
                progress_callback=None,
                domains_dir=domains_path,
            )

        # Display results
        console.print()
        console.print(f"[bold green]✓[/bold green] Run completed: {result.label}")
        console.print()

        # Summary table
        table = Table(title="Run Summary", show_header=False)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Label", result.label)
        table.add_row("Run ID", str(result.id)[:8] + "...")
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


# ============================================================================
# Compare Command
# ============================================================================


@app.command()
def compare(
    domain_dir: Path = typer.Option(
        ...,
        "--domain-dir",
        "-d",
        help="Path to domain directory (e.g., 'examples/squad-demo/domains/squad')",
    ),
    run: list[str] = typer.Option(
        None,
        "--run",
        "-r",
        help="Run label or ID to compare (can be specified multiple times)",
    ),
    label: Optional[str] = typer.Option(
        None,
        "--label",
        "-l",
        help="Label for this comparison (auto-generated if not provided)",
    ),
    model: Optional[str] = typer.Option(
        None, help="LLM model override (default: use domain config)"
    ),
    temperature: Optional[float] = typer.Option(
        None, help="Temperature override (default: use domain config)"
    ),
    concurrency: int = typer.Option(
        5, help="Maximum concurrent evaluations (default: 5)"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file path (default: print to console)"
    ),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format: table, json, markdown"
    ),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress progress output"),
):
    """Compare multiple runs using LLM evaluation.

    This command:
    1. Loads all runs from disk (or finds latest runs if --run not specified)
    2. Validates runs are from same domain and query set
    3. For each query, evaluates results using LLM
    4. Saves comparison to disk
    5. Displays or exports results

    Example:
        $ ragdiff compare --domain-dir domains/tafsir --run vectara-001 --run mongodb-002
        $ ragdiff compare -d examples/squad-demo/domains/squad -r faiss-small-001 -r faiss-large-001
        $ ragdiff compare -d domains/tafsir --run vectara-001 --run mongodb-002 --model claude-3-5-sonnet-20241022
        $ ragdiff compare -d domains/tafsir --run vectara-001 --run mongodb-002 --format json --output comparison.json
        $ ragdiff compare -d domains/tafsir  # Uses latest run for each provider
    """
    # Extract domain name from domain_dir path
    domain_dir = Path(domain_dir).resolve()
    domain = domain_dir.name
    domains_path = domain_dir.parent

    # If no --run flags provided, find latest runs for each provider
    if not run or len(run) == 0:
        from .core.storage import list_runs

        all_runs = list_runs(domain, domains_dir=domains_path)

        if len(all_runs) == 0:
            console.print(
                f"[bold red]Error:[/bold red] No runs found for domain '{domain}'"
            )
            raise typer.Exit(code=1)

        # Group runs by provider and get the latest for each
        provider_runs = {}
        for r in all_runs:
            if (
                r.provider not in provider_runs
                or r.started_at > provider_runs[r.provider].started_at
            ):
                provider_runs[r.provider] = r

        run = [r.label for r in provider_runs.values()]
        console.print("[dim]No --run flags provided. Using latest runs:[/dim]")
        for r_label in run:
            console.print(f"[dim]  - {r_label}[/dim]")
        console.print()

    # Ensure at least 2 runs to compare
    if len(run) < 2:
        console.print(
            f"[bold red]Error:[/bold red] Need at least 2 runs to compare (got {len(run)})"
        )
        raise typer.Exit(code=1)

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
                task = progress.add_task(f"Comparing {len(run)} runs", total=100)

                completed_evals = 0
                total_evals = 0

                def progress_callback(current, total, successes, failures):
                    nonlocal completed_evals, total_evals
                    completed_evals = current
                    total_evals = total
                    progress.update(
                        task,
                        completed=current,
                        total=total,
                        description=f"Evaluation {current}/{total} ({successes} ok, {failures} failed)",
                    )

                # Execute comparison
                result = compare_runs(
                    domain=domain,
                    run_ids=run,
                    label=label,
                    model=model,
                    temperature=temperature,
                    concurrency=concurrency,
                    progress_callback=progress_callback,
                    domains_dir=domains_path,
                )

                progress.update(task, completed=total_evals, total=total_evals)
        else:
            # Quiet mode - no progress bar
            result = compare_runs(
                domain=domain,
                run_ids=run,
                label=label,
                model=model,
                temperature=temperature,
                concurrency=concurrency,
                progress_callback=None,
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


# ============================================================================
# Generate Adapter Command
# ============================================================================


@app.command()
def generate_adapter(
    openapi_url: str = typer.Option(
        ..., "--openapi-url", help="URL to OpenAPI specification"
    ),
    api_key: str = typer.Option(..., "--api-key", help="API key for authentication"),
    test_query: str = typer.Option(..., "--test-query", help="Test query to execute"),
    adapter_name: str = typer.Option(
        ..., "--adapter-name", help="Name for the adapter"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path (default: stdout)"
    ),
    endpoint: Optional[str] = typer.Option(
        None, "--endpoint", help="Override endpoint path"
    ),
    method: Optional[str] = typer.Option(None, "--method", help="Override HTTP method"),
    model: str = typer.Option(
        "claude-3-5-sonnet-20241022", "--model", "-m", help="LLM model for generation"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
):
    """Generate OpenAPI adapter configuration from specification.

    This command automatically generates a RAGDiff adapter configuration by:
    1. Fetching and parsing the OpenAPI specification
    2. Using AI to identify the search endpoint (or using --endpoint override)
    3. Making a test query to analyze the response structure
    4. Generating JMESPath mappings with AI
    5. Creating a complete YAML configuration file

    Example:
        ragdiff generate-adapter \\
            --openapi-url https://api.example.com/openapi.json \\
            --api-key $MY_API_KEY \\
            --test-query "test search" \\
            --adapter-name my-api \\
            --output configs/my-api.yaml

    Requirements:
        - OpenAPI 3.x specification URL
        - API key with search permissions
        - ANTHROPIC_API_KEY or OPENAI_API_KEY environment variable (for AI generation)
    """
    setup_logging(verbose)

    try:
        import yaml

        from .openapi import ConfigGenerator

        console.print(
            Panel(
                "[cyan]OpenAPI Adapter Generator[/cyan]\n\n"
                f"Spec URL: {openapi_url}\n"
                f"Adapter Name: {adapter_name}\n"
                f"AI Model: {model}",
                title="Starting Generation",
                border_style="cyan",
            )
        )

        # Initialize generator
        console.print("\n[cyan]Initializing AI-powered generator...[/cyan]")
        generator = ConfigGenerator(model=model)

        # Generate configuration
        console.print(
            f"\n[cyan]Generating configuration for '{adapter_name}'...[/cyan]"
        )
        console.print("[dim]This may take 30-60 seconds...[/dim]\n")

        config = generator.generate(
            openapi_url=openapi_url,
            api_key=api_key,
            test_query=test_query,
            adapter_name=adapter_name,
            endpoint=endpoint,
            method=method,
        )

        # Format as YAML with comments
        yaml_content = f"""# Generated by: ragdiff generate-adapter
# OpenAPI Spec: {openapi_url}
# Generated: {__import__('datetime').datetime.now().isoformat()}
#
# Usage:
#   export {config[adapter_name]['api_key_env']}=your_api_key_here
#   ragdiff query "your query" --tool {adapter_name} --config path/to/this/file.yaml

"""
        yaml_content += yaml.dump(config, default_flow_style=False, sort_keys=False)

        # Output configuration
        if output:
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(yaml_content)
            console.print(f"\n[green]✓[/green] Configuration saved to: {output}")
        else:
            console.print("\n[cyan]Generated Configuration:[/cyan]")
            console.print(Panel(yaml_content, border_style="green"))

        # Show usage instructions
        console.print(
            Panel(
                f"[green]✓ Configuration generated successfully![/green]\n\n"
                f"[cyan]Next steps:[/cyan]\n"
                f"1. Set environment variable:\n"
                f"   export {config[adapter_name]['api_key_env']}=your_api_key_here\n\n"
                f"2. Test the adapter:\n"
                f"   ragdiff query \"test\" --tool {adapter_name} --config {output or 'config.yaml'}\n\n"
                f"3. Customize the config if needed (edit response_mapping, auth, etc.)",
                title="Success",
                border_style="green",
            )
        )

    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        if verbose:
            console.print_exception()
        raise typer.Exit(1) from e


# ============================================================================
# Helper Functions
# ============================================================================


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
    console.print(f"[bold]Comparison: {comparison.label}[/bold]")
    console.print(f"Domain: {comparison.domain}")
    console.print(f"Comparison ID: {str(comparison.id)[:8]}...")
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
        f"# Comparison: {comparison.label}",
        "",
        f"**Domain:** {comparison.domain}",
        f"**Comparison ID:** {str(comparison.id)[:8]}...",
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
