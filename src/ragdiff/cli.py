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
    domain: str = typer.Argument(..., help="Domain name (e.g., 'tafsir')"),
    provider: str = typer.Argument(..., help="Provider name (e.g., 'vectara-default')"),
    query_set: str = typer.Argument(..., help="Query set name (e.g., 'test-queries')"),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        "-n",
        help="Human-readable name for this run (default: auto-numbered like 'run-0001')",
    ),
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


# ============================================================================
# Compare Command
# ============================================================================


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
    concurrency: int = typer.Option(
        5, help="Maximum concurrent evaluations (default: 5)"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file path (default: print to console)"
    ),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format: table, json, markdown"
    ),
    details: bool = typer.Option(
        False, "--details", "-d", help="Include individual query evaluations in output"
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
        $ ragdiff compare tafsir 550e 660e --concurrency 10
        $ ragdiff compare tafsir 550e 660e --format json --output comparison.json
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
                task = progress.add_task(f"Comparing {len(run_ids)} runs", total=100)

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
                    run_ids=run_ids,
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
                run_ids=run_ids,
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
            _output_markdown(result, output, details=details, domains_dir=domains_path)
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


def _output_markdown(
    comparison, output_path, details=False, domains_dir=Path("domains")
):
    """Output comparison results as Markdown with aggregate analysis (v1-inspired)."""
    import statistics
    from collections import defaultdict

    from .core.storage import load_run

    # Get provider names
    provider_names = (
        list(comparison.evaluations[0].run_results.keys())
        if comparison.evaluations
        else []
    )
    provider_a = provider_names[0] if len(provider_names) > 0 else "A"
    provider_b = provider_names[1] if len(provider_names) > 1 else "B"

    # Load runs to get latency and chunk count data
    runs_data = {}
    for run_id in comparison.runs:
        try:
            run = load_run(comparison.domain, str(run_id), domains_dir=domains_dir)
            runs_data[run.provider] = run
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load run {run_id}: {e}[/yellow]")

    # Calculate latency and chunk statistics from runs
    latency_stats = {}
    chunk_stats = {}
    for provider_name, run in runs_data.items():
        latencies = []
        chunk_counts = []
        for result in run.results:
            if result.duration_ms is not None:
                latencies.append(result.duration_ms)
            if result.retrieved is not None:
                chunk_counts.append(len(result.retrieved))

        if latencies:
            latency_stats[provider_name] = {
                "avg": statistics.mean(latencies),
                "min": min(latencies),
                "max": max(latencies),
                "median": statistics.median(latencies),
            }
        if chunk_counts:
            chunk_stats[provider_name] = {
                "avg": statistics.mean(chunk_counts),
                "min": min(chunk_counts),
                "max": max(chunk_counts),
            }

    # Calculate aggregate statistics
    wins_a = 0
    wins_b = 0
    ties = 0
    scores_a = []
    scores_b = []
    total_cost = 0.0

    # Track issues and themes (v1 style)
    issue_tracker = defaultdict(int)
    theme_tracker = defaultdict(list)
    winner_analyses = {provider_a: [], provider_b: []}

    for eval_result in comparison.evaluations:
        winner = eval_result.evaluation.get("winner", "unknown")
        if winner == "a":
            wins_a += 1
            winner_analyses[provider_a].append(
                eval_result.evaluation.get("reasoning", "").lower()
            )
        elif winner == "b":
            wins_b += 1
            winner_analyses[provider_b].append(
                eval_result.evaluation.get("reasoning", "").lower()
            )
        elif winner == "tie":
            ties += 1

        if (
            "score_a" in eval_result.evaluation
            and eval_result.evaluation["score_a"] is not None
        ):
            scores_a.append(eval_result.evaluation["score_a"])
        if (
            "score_b" in eval_result.evaluation
            and eval_result.evaluation["score_b"] is not None
        ):
            scores_b.append(eval_result.evaluation["score_b"])

        if "_metadata" in eval_result.evaluation:
            total_cost += eval_result.evaluation["_metadata"].get("cost", 0)

        # Track recurring issues (v1 style)
        reasoning = eval_result.evaluation.get("reasoning", "").lower()
        if reasoning:
            if "duplicate" in reasoning or "repetition" in reasoning:
                issue_tracker["duplicates"] += 1
                theme_tracker["duplicates"].append(eval_result.query)
            if (
                "fragment" in reasoning
                or "incomplete" in reasoning
                or "truncat" in reasoning
            ):
                issue_tracker["fragmentation"] += 1
                theme_tracker["fragmentation"].append(eval_result.query)
            if "accurate" in reasoning or "correct" in reasoning:
                issue_tracker["accuracy_mentioned"] += 1
            if "complete" in reasoning or "comprehensive" in reasoning:
                issue_tracker["completeness_mentioned"] += 1
            if "relevant" in reasoning:
                issue_tracker["relevance_mentioned"] += 1

    avg_score_a = sum(scores_a) / len(scores_a) if scores_a else 0
    avg_score_b = sum(scores_b) / len(scores_b) if scores_b else 0

    # Find examples with biggest margins
    margins = []
    for eval_result in comparison.evaluations:
        score_a = eval_result.evaluation.get("score_a")
        score_b = eval_result.evaluation.get("score_b")
        if score_a is not None and score_b is not None:
            margin = score_a - score_b
            margins.append((eval_result, margin, score_a, score_b))

    # Sort by margin (positive = A wins, negative = B wins)
    margins_sorted = sorted(margins, key=lambda x: abs(x[1]), reverse=True)
    top_a_wins = [m for m in margins_sorted if m[1] > 0][:3]
    top_b_wins = [m for m in margins_sorted if m[1] < 0][:3]

    # Analyze positive attributes for winner (v1 style)
    winner_provider = (
        provider_a if wins_a > wins_b else provider_b if wins_b > wins_a else None
    )
    positive_terms = {}
    if winner_provider and winner_provider in winner_analyses:
        terms_to_check = {
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
            "precise": 0,
        }
        for analysis in winner_analyses[winner_provider]:
            for term in terms_to_check:
                if term in analysis:
                    terms_to_check[term] += 1
        # Get top 3 positive attributes
        positive_terms = dict(
            sorted(terms_to_check.items(), key=lambda x: x[1], reverse=True)[:3]
        )

    # Build markdown (v1-inspired structure)
    lines = [
        "# RAG Comparison: Holistic Summary",
        "",
        f"**Total Queries Evaluated:** {len(comparison.evaluations)}",
        f"**Domain:** {comparison.domain}",
        f"**Providers Compared:** {provider_a} vs {provider_b}",
        f"**Evaluation Model:** {comparison.evaluator_config.model}",
        f"**Comparison ID:** {comparison.id}",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        "",
        f"**Overall Winner:** {'🏆 ' + provider_a if wins_a > wins_b else '🏆 ' + provider_b if wins_b > wins_a else 'Tie'}",
        "",
        "### Win/Loss Statistics",
        "",
        f"- **{provider_a} wins:** {wins_a}/{len(comparison.evaluations)} ({wins_a/len(comparison.evaluations)*100:.1f}%)",
        f"- **{provider_b} wins:** {wins_b}/{len(comparison.evaluations)} ({wins_b/len(comparison.evaluations)*100:.1f}%)",
        f"- **Ties:** {ties}/{len(comparison.evaluations)} ({ties/len(comparison.evaluations)*100:.1f}%)",
        "",
        "### Average Quality Scores",
        "",
        f"- **{provider_a}:** {avg_score_a:.1f}/100",
        f"- **{provider_b}:** {avg_score_b:.1f}/100",
        f"- **Score difference:** {abs(avg_score_a - avg_score_b):.1f} points",
        "",
    ]

    # Add latency statistics if available
    if latency_stats:
        lines.extend(
            [
                "### Latency Comparison",
                "",
            ]
        )
        for provider_name in [provider_a, provider_b]:
            if provider_name in latency_stats:
                stats = latency_stats[provider_name]
                lines.extend(
                    [
                        f"**{provider_name}:**",
                        f"- Average: {stats['avg']:.2f}ms",
                        f"- Median: {stats['median']:.2f}ms",
                        f"- Min: {stats['min']:.2f}ms",
                        f"- Max: {stats['max']:.2f}ms",
                        "",
                    ]
                )

    # Add chunk count statistics if available
    if chunk_stats:
        lines.extend(
            [
                "### Chunks Returned",
                "",
            ]
        )
        for provider_name in [provider_a, provider_b]:
            if provider_name in chunk_stats:
                stats = chunk_stats[provider_name]
                lines.extend(
                    [
                        f"**{provider_name}:**",
                        f"- Average: {stats['avg']:.1f} chunks/query",
                        f"- Range: {stats['min']}-{stats['max']} chunks",
                        "",
                    ]
                )

    lines.append("")

    # Add Common Themes section (v1 style)
    lines.extend(
        [
            "---",
            "",
            "## 2. Common Themes",
            "",
        ]
    )

    # Recurring issues
    if issue_tracker:
        lines.append("### Recurring Issues")
        lines.append("")
        for issue_type, count in sorted(
            issue_tracker.items(), key=lambda x: x[1], reverse=True
        ):
            if issue_type in theme_tracker:
                percentage = (
                    (count / len(comparison.evaluations) * 100)
                    if comparison.evaluations
                    else 0
                )
                issue_name = issue_type.replace("_", " ").title()
                lines.append(
                    f"- **{issue_name}:** {count}/{len(comparison.evaluations)} queries ({percentage:.1f}%)"
                )
                # Show example queries
                if theme_tracker[issue_type]:
                    examples = theme_tracker[issue_type][:3]
                    examples_str = ", ".join(
                        f'"{q[:50]}..."' if len(q) > 50 else f'"{q}"' for q in examples
                    )
                    lines.append(f"  - Examples: {examples_str}")
        lines.append("")

    # Key Differentiators section (v1 style)
    if winner_provider:
        lines.extend(
            [
                "---",
                "",
                "## 3. Key Differentiators",
                "",
                f"### What makes {winner_provider} better?",
                "",
            ]
        )

        if positive_terms:
            lines.append("**Most frequent positive attributes:**")
            lines.append("")
            for term, count in positive_terms.items():
                if count > 0:
                    percentage = (
                        (count / len(winner_analyses[winner_provider]) * 100)
                        if winner_analyses[winner_provider]
                        else 0
                    )
                    lines.append(
                        f"- **{term.title()}**: mentioned in {count} winning evaluations ({percentage:.1f}%)"
                    )
            lines.append("")
    else:
        lines.extend(
            [
                "---",
                "",
                "## 3. Key Differentiators",
                "",
                "**Result:** Too close to call - both providers performed similarly across most queries.",
                "",
            ]
        )

    # Add top examples section
    lines.extend(
        [
            "## 4. Representative Examples",
            "",
        ]
    )

    # Add top examples for provider A
    if top_a_wins:
        lines.extend(
            [
                f"### Top {provider_a} Wins (Biggest Margins)",
                "",
            ]
        )
        for i, (eval_result, margin, score_a, score_b) in enumerate(top_a_wins, 1):
            query_display = (
                eval_result.query
                if len(eval_result.query) <= 100
                else eval_result.query[:97] + "..."
            )
            lines.extend(
                [
                    f"**{i}. {query_display}**",
                    "",
                    f"- **Scores:** {provider_a}={score_a}/100, {provider_b}={score_b}/100 (margin: +{margin:.1f})",
                    f"- **Reasoning:** {eval_result.evaluation.get('reasoning', 'N/A')}",
                    "",
                ]
            )

    # Add top examples for provider B
    if top_b_wins:
        lines.extend(
            [
                f"### Top {provider_b} Wins (Biggest Margins)",
                "",
            ]
        )
        for i, (eval_result, margin, score_a, score_b) in enumerate(top_b_wins, 1):
            query_display = (
                eval_result.query
                if len(eval_result.query) <= 100
                else eval_result.query[:97] + "..."
            )
            lines.extend(
                [
                    f"**{i}. {query_display}**",
                    "",
                    f"- **Scores:** {provider_a}={score_a}/100, {provider_b}={score_b}/100 (margin: {margin:.1f})",
                    f"- **Reasoning:** {eval_result.evaluation.get('reasoning', 'N/A')}",
                    "",
                ]
            )

    lines.append("---")
    lines.append("")

    # Add detailed evaluations if requested (v1 style)
    if details:
        lines.extend(
            [
                "## 5. Query-by-Query Results",
                "",
                "*Full breakdown of all evaluations*",
                "",
            ]
        )
        for i, eval_result in enumerate(comparison.evaluations, 1):
            query_display = (
                eval_result.query
                if len(eval_result.query) <= 80
                else eval_result.query[:77] + "..."
            )
            lines.append(f'### Query {i}: "{query_display}"')
            lines.append("")

            # Winner with emoji
            winner = eval_result.evaluation.get("winner", "unknown")
            if winner == "a":
                winner_display = f"🏆 {provider_a}"
            elif winner == "b":
                winner_display = f"🏆 {provider_b}"
            elif winner == "tie":
                winner_display = "TIE"
            else:
                winner_display = winner
            lines.append(f"**Winner:** {winner_display}")
            lines.append("")

            # Quality scores
            score_a = eval_result.evaluation.get("score_a")
            score_b = eval_result.evaluation.get("score_b")
            if score_a is not None and score_b is not None:
                lines.append("**Quality Scores:**")
                lines.append(f"- {provider_a}: {score_a:.1f}/100")
                lines.append(f"- {provider_b}: {score_b:.1f}/100")
                lines.append("")

            # Analysis/reasoning
            reasoning = eval_result.evaluation.get("reasoning", "")
            if reasoning:
                # Truncate if too long
                reasoning_display = (
                    reasoning if len(reasoning) <= 300 else reasoning[:297] + "..."
                )
                lines.append(f"**Analysis:** {reasoning_display}")
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
