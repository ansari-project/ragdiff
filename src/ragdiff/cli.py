"""Command-line interface for RAGDiff v2.0.

RAGDiff v2.0 uses a domain-based architecture for comparing RAG providers.

Commands:
- init: Initialize a new domain with directory structure
- run: Execute a query set against a provider
- compare: Compare runs (auto-detects reference-based vs head-to-head evaluation)
- generate-provider: Generate OpenAPI provider configuration
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
from .comparison.reference_evaluator import evaluate_run_threaded
from .core.errors import ComparisonError, RunError
from .core.logging import setup_logging
from .core.storage import load_run
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
        2, help="Maximum concurrent evaluations (default: 2)"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file path (default: print to console)"
    ),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format: table, json, markdown"
    ),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress progress output"),
    limit: Optional[int] = typer.Option(
        None,
        "--limit",
        help="Limit evaluation to first N queries (default: evaluate all)",
    ),
):
    """Compare runs using LLM evaluation (auto-detects reference-based vs head-to-head).

    This command automatically detects the evaluation mode:
    - If runs have reference answers → Reference-based evaluation (correctness scoring)
    - If runs don't have references → Head-to-head LLM comparison

    Workflow:
    1. Loads run(s) from disk (or finds latest runs if --run not specified)
    2. Detects whether runs have reference answers
    3. Performs appropriate evaluation (reference-based or head-to-head)
    4. Saves comparison to disk
    5. Displays or exports results

    Examples:
        # Reference-based evaluation (single run)
        $ ragdiff compare -d examples/squad-demo/domains/squad -r faiss-small-001

        # Reference-based comparison (multiple runs with references)
        $ ragdiff compare -d examples/squad-demo/domains/squad -r faiss-small-001 -r faiss-large-001

        # Head-to-head comparison (no references)
        $ ragdiff compare -d domains/tafsir -r vectara-001 -r mongodb-002

        # With options
        $ ragdiff compare -d domains/squad -r run1 -r run2 --limit 10 --format json --output comparison.json
        $ ragdiff compare -d domains/tafsir --model anthropic/claude-sonnet-4-5
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

    # Load first run to detect if we have references
    try:
        first_run = load_run(domain, run[0], domains_dir=domains_path)
        has_references = any(result.reference for result in first_run.results)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Failed to load run: {e}")
        raise typer.Exit(code=1) from e

    # Route to appropriate evaluation mode
    if has_references:
        # Reference-based evaluation mode
        _compare_with_references(
            domain=domain,
            domains_path=domains_path,
            run_ids=run,
            model=model,
            temperature=temperature,
            concurrency=concurrency,
            output=output,
            format=format,
            quiet=quiet,
            limit=limit,
        )
    else:
        # Head-to-head comparison mode
        # Ensure at least 2 runs to compare
        if len(run) < 2:
            console.print(
                f"[bold red]Error:[/bold red] Need at least 2 runs for head-to-head comparison (got {len(run)})"
            )
            raise typer.Exit(code=1)

        _compare_head_to_head(
            domain=domain,
            domains_path=domains_path,
            run_ids=run,
            label=label,
            model=model,
            temperature=temperature,
            concurrency=concurrency,
            output=output,
            format=format,
            quiet=quiet,
        )


def _compare_head_to_head(
    domain: str,
    domains_path: Path,
    run_ids: list[str],
    label: Optional[str],
    model: Optional[str],
    temperature: Optional[float],
    concurrency: int,
    output: Optional[Path],
    format: str,
    quiet: bool,
):
    """Perform head-to-head comparison (no references)."""
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
                run_ids=run_ids,
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


def _compare_with_references(
    domain: str,
    domains_path: Path,
    run_ids: list[str],
    model: Optional[str],
    temperature: Optional[float],
    concurrency: int,
    output: Optional[Path],
    format: str,
    quiet: bool,
    limit: Optional[int],
):
    """Perform reference-based evaluation for one or more runs."""
    from .comparison.reference_evaluator import compare_multiple_runs_batched
    from .core.loaders import load_domain

    try:
        # Load domain config
        domain_obj = load_domain(domain, domains_dir=domains_path)
        evaluator_config = domain_obj.evaluator

        # Apply overrides
        if model:
            evaluator_config.model = model
        if temperature is not None:
            evaluator_config.temperature = temperature

        # Load all runs
        runs = []
        for run_id in run_ids:
            run_obj = load_run(domain, run_id, domains_dir=domains_path)
            runs.append(run_obj)

        # If multiple runs, use batched comparison (3x faster, better results!)
        if len(runs) >= 2:
            if not quiet:
                console.print(
                    f"\n[cyan]Comparing {len(runs)} runs with batched evaluation...[/cyan]"
                )

            # Run batched comparison with progress
            if not quiet:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    TimeElapsedColumn(),
                    console=console,
                ) as progress:
                    progress_task = progress.add_task(
                        f"Comparing {len(runs)} runs", total=100
                    )

                    completed_evals = 0
                    total_evals = 0

                    def progress_callback(current, total, successes, failures):
                        nonlocal completed_evals, total_evals
                        completed_evals = current
                        total_evals = total
                        progress.update(
                            progress_task,
                            completed=current,
                            total=total,
                            description=f"Comparison {current}/{total} ({successes} ok, {failures} failed)",
                        )

                    comparison_result = compare_multiple_runs_batched(
                        runs=runs,
                        evaluator_config=evaluator_config,
                        concurrency=concurrency,
                        progress_callback=progress_callback,
                        limit=limit,
                    )

                    progress.update(
                        progress_task, completed=total_evals, total=total_evals
                    )
            else:
                # Quiet mode
                comparison_result = compare_multiple_runs_batched(
                    runs=runs,
                    evaluator_config=evaluator_config,
                    concurrency=concurrency,
                    progress_callback=None,
                    limit=limit,
                )

            # Output batched comparison results
            _output_batched_comparison(comparison_result, output, format)

        else:
            # Single run - use traditional evaluation
            run_obj = runs[0]
            if not quiet:
                console.print(f"\n[cyan]Evaluating run: {run_ids[0]}[/cyan]")

            # Evaluate with progress
            if not quiet:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    TimeElapsedColumn(),
                    console=console,
                ) as progress:
                    progress_task = progress.add_task(
                        f"Evaluating {run_ids[0]}", total=100
                    )

                    completed_evals = 0
                    total_evals = 0

                    def progress_callback(current, total, successes, failures):
                        nonlocal completed_evals, total_evals
                        completed_evals = current
                        total_evals = total
                        progress.update(
                            progress_task,
                            completed=current,
                            total=total,
                            description=f"Evaluation {current}/{total} ({successes} ok, {failures} failed)",
                        )

                    eval_result = evaluate_run_threaded(
                        run=run_obj,
                        evaluator_config=evaluator_config,
                        concurrency=concurrency,
                        progress_callback=progress_callback,
                        limit=limit,
                    )

                    progress.update(
                        progress_task, completed=total_evals, total=total_evals
                    )
            else:
                # Quiet mode
                eval_result = evaluate_run_threaded(
                    run=run_obj,
                    evaluator_config=evaluator_config,
                    concurrency=concurrency,
                    progress_callback=None,
                    limit=limit,
                )

            # Output single run evaluation
            if format == "json":
                _output_eval_json(eval_result, output)
            else:  # table
                _output_eval_table(eval_result, output)

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
def init(
    domain: str = typer.Argument(..., help="Name of the domain to initialize"),
    domains_dir: Path = typer.Option(
        Path("domains"),
        "--domains-dir",
        "-d",
        help="Root directory for domains (default: ./domains)",
    ),
    template: str = typer.Option(
        "default",
        "--template",
        "-t",
        help="Template to use: default, minimal, or complete",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing domain directory",
    ),
):
    """Initialize a new RAGDiff domain with directory structure and templates.

    This command creates:
    - Domain directory structure (systems/, query-sets/, runs/, comparisons/)
    - domain.yaml with evaluator configuration
    - Example system configurations
    - Sample query sets
    - .env.example if it doesn't exist

    Examples:
        # Basic initialization
        ragdiff init my-domain

        # With custom domains directory
        ragdiff init my-domain --domains-dir ./custom-domains

        # Use minimal template
        ragdiff init my-domain --template minimal

        # Overwrite existing domain
        ragdiff init my-domain --force
    """
    import shutil
    from textwrap import dedent

    # Validate domain name
    if not domain.replace("-", "").replace("_", "").isalnum():
        console.print(
            "[red]Error:[/red] Domain name must be alphanumeric with hyphens/underscores only"
        )
        raise typer.Exit(code=1)

    # Check if domain already exists
    domain_path = domains_dir / domain
    if domain_path.exists() and not force:
        console.print(
            f"[red]Error:[/red] Domain '{domain}' already exists at {domain_path}"
        )
        console.print("Use --force to overwrite")
        raise typer.Exit(code=1)

    # Create directory structure
    try:
        console.print(f"[cyan]Creating domain:[/cyan] {domain}")

        # Create directories
        for subdir in ["systems", "query-sets", "runs", "comparisons"]:
            (domain_path / subdir).mkdir(parents=True, exist_ok=True)
            console.print(f"  ✓ Created {domain}/{subdir}/")

        # Create domain.yaml
        if template == "minimal":
            domain_yaml = dedent(f"""\
                name: {domain}
                description: RAG comparison domain for {domain.replace('-', ' ').replace('_', ' ')}
                evaluator:
                  model: gpt-4
                  temperature: 0.0
                  prompt_template: |
                    Compare these RAG results for the query: {{{{query}}}}

                    Provider A ({{{{provider_a}}}}):
                    {{{{response_a}}}}

                    Provider B ({{{{provider_b}}}}):
                    {{{{response_b}}}}

                    Which provider gave a better response and why?
                """)
        else:  # default or complete
            domain_yaml = dedent(f"""\
                name: {domain}
                description: RAG comparison domain for {domain.replace('-', ' ').replace('_', ' ')}
                evaluator:
                  model: gpt-4  # or anthropic/claude-3-opus, gemini/gemini-pro, etc.
                  temperature: 0.0  # Use 0 for consistent evaluation
                  max_tokens: 1000  # Optional: limit response length
                  prompt_template: |
                    You are evaluating two RAG system responses for quality and relevance.

                    Query: {{{{query}}}}

                    Response from {{{{provider_a}}}}:
                    {{{{response_a}}}}

                    Response from {{{{provider_b}}}}:
                    {{{{response_b}}}}

                    Evaluation Criteria:
                    1. Relevance to the query (40 points)
                    2. Accuracy and correctness (30 points)
                    3. Completeness (20 points)
                    4. Clarity and coherence (10 points)

                    Score each response 0-100 and determine the winner.
                    If scores differ by less than 5 points, call it a tie.

                    Respond with ONLY a JSON object in this exact format:
                    {{
                      "score_{{{{provider_a}}}}": <0-100>,
                      "score_{{{{provider_b}}}}": <0-100>,
                      "winner": "<{{{{provider_a}}}}, {{{{provider_b}}}}, or tie>",
                      "reasoning": "Brief explanation of your evaluation and decision"
                    }}
                """)

        with open(domain_path / "domain.yaml", "w") as f:
            f.write(domain_yaml)
        console.print("  ✓ Created domain.yaml")

        # Create example system configurations
        if template != "minimal":
            # Vectara example
            vectara_yaml = dedent("""\
                name: vectara-default
                description: Vectara semantic search with default settings
                tool: vectara
                config:
                  api_key: ${VECTARA_API_KEY}
                  customer_id: ${VECTARA_CUSTOMER_ID}
                  corpus_id: ${VECTARA_CORPUS_ID}
                  rerank: false
                  timeout: 30
                """)
            with open(domain_path / "systems" / "vectara-example.yaml", "w") as f:
                f.write(vectara_yaml)

            # MongoDB example
            mongodb_yaml = dedent("""\
                name: mongodb-atlas
                description: MongoDB Atlas vector search
                tool: mongodb
                config:
                  connection_string: ${MONGODB_URI}
                  database: rag_database
                  collection: documents
                  vector_index: vector_index
                  embedding_field: embedding
                  text_field: content
                  embedding_model: text-embedding-ada-002
                  embedding_dimensions: 1536
                """)
            with open(domain_path / "systems" / "mongodb-example.yaml", "w") as f:
                f.write(mongodb_yaml)

            # OpenAPI adapter example
            openapi_yaml = dedent("""\
                name: custom-api
                description: Custom RAG API via OpenAPI adapter
                tool: openapi
                config:
                  base_url: ${CUSTOM_API_URL}
                  api_key: ${CUSTOM_API_KEY}
                  search_endpoint: /search
                  search_method: POST
                  query_param: q
                  response_mapping:
                    results_path: "data.results"
                    text_path: "text"
                    score_path: "score"
                    metadata_path: "metadata"
                """)
            with open(domain_path / "systems" / "openapi-example.yaml", "w") as f:
                f.write(openapi_yaml)

            console.print("  ✓ Created example system configurations")

        # Create sample query sets
        basic_queries = dedent("""\
            What is the capital of France?
            Explain quantum computing in simple terms
            How does photosynthesis work?
            What are the main causes of climate change?
            Describe the process of machine learning
            """).strip()

        with open(domain_path / "query-sets" / "basic-queries.txt", "w") as f:
            f.write(basic_queries)
        console.print("  ✓ Created basic-queries.txt")

        if template == "complete":
            # Add JSONL query set example
            jsonl_queries = dedent("""\
                {"query": "What is DNA?", "category": "biology", "difficulty": "basic"}
                {"query": "Explain CRISPR gene editing", "category": "biology", "difficulty": "advanced"}
                {"query": "How do vaccines work?", "category": "medicine", "difficulty": "intermediate"}
                """).strip()

            with open(
                domain_path / "query-sets" / "categorized-queries.jsonl", "w"
            ) as f:
                f.write(jsonl_queries)
            console.print("  ✓ Created categorized-queries.jsonl")

        # Create .env.example if it doesn't exist
        env_example = Path(".env.example")
        if not env_example.exists():
            env_content = dedent("""\
                # RAGDiff Environment Variables

                # Vectara Configuration
                VECTARA_API_KEY=your_vectara_api_key
                VECTARA_CUSTOMER_ID=your_customer_id
                VECTARA_CORPUS_ID=your_corpus_id

                # MongoDB Atlas
                MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/

                # OpenAI (for embeddings and evaluation)
                OPENAI_API_KEY=sk-...

                # Anthropic (for evaluation)
                ANTHROPIC_API_KEY=sk-ant-...

                # Google (for Gemini evaluation)
                GOOGLE_API_KEY=...

                # Custom API
                CUSTOM_API_URL=https://api.example.com
                CUSTOM_API_KEY=your_api_key
                """)

            with open(env_example, "w") as f:
                f.write(env_content)
            console.print("\n✓ Created .env.example (copy to .env and add your keys)")

        # Success message
        console.print(f"\n[green]✓ Successfully initialized domain:[/green] {domain}")
        console.print("\n[bold]Next steps:[/bold]")
        console.print(f"1. Configure your RAG systems in {domain_path}/systems/")
        console.print(f"2. Add queries to {domain_path}/query-sets/")
        console.print(
            f"3. Run: [cyan]ragdiff run -d {domain_path} <system> <query-set>[/cyan]"
        )
        console.print(
            f"4. Compare: [cyan]ragdiff compare -d {domain_path} <run-id-1> <run-id-2>[/cyan]"
        )

        if not Path(".env").exists():
            console.print(
                "\n[yellow]Note:[/yellow] Don't forget to copy .env.example to .env and add your API keys!"
            )

    except Exception as e:
        console.print(f"[red]Error creating domain:[/red] {e}")
        # Clean up partial creation
        if domain_path.exists() and not force:
            shutil.rmtree(domain_path)
        raise typer.Exit(code=1) from e


@app.command()
def generate_provider(
    openapi_url: str = typer.Option(
        ..., "--openapi-url", help="URL to OpenAPI specification"
    ),
    api_key: str = typer.Option(..., "--api-key", help="API key for authentication"),
    test_query: str = typer.Option(..., "--test-query", help="Test query to execute"),
    provider_name: str = typer.Option(
        ..., "--provider-name", help="Name for the provider"
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
    """Generate OpenAPI provider configuration from specification.

    This command automatically generates a RAGDiff provider configuration by:
    1. Fetching and parsing the OpenAPI specification
    2. Using AI to identify the search endpoint (or using --endpoint override)
    3. Making a test query to analyze the response structure
    4. Generating JMESPath mappings with AI
    5. Creating a complete YAML configuration file

    Example:
        ragdiff generate-provider \\
            --openapi-url https://api.example.com/openapi.json \\
            --api-key $MY_API_KEY \\
            --test-query "test search" \\
            --provider-name my-api \\
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
                "[cyan]OpenAPI Provider Generator[/cyan]\n\n"
                f"Spec URL: {openapi_url}\n"
                f"Provider Name: {provider_name}\n"
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
            f"\n[cyan]Generating configuration for '{provider_name}'...[/cyan]"
        )
        console.print("[dim]This may take 30-60 seconds...[/dim]\n")

        config = generator.generate(
            openapi_url=openapi_url,
            api_key=api_key,
            test_query=test_query,
            adapter_name=provider_name,
            endpoint=endpoint,
            method=method,
        )

        # Format as YAML with comments
        yaml_content = f"""# Generated by: ragdiff generate-provider
# OpenAPI Spec: {openapi_url}
# Generated: {__import__('datetime').datetime.now().isoformat()}
#
# Usage:
#   export {config[provider_name]['api_key_env']}=your_api_key_here
#   ragdiff query "your query" --tool {provider_name} --config path/to/this/file.yaml

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
                f"   export {config[provider_name]['api_key_env']}=your_api_key_here\n\n"
                f"2. Test the provider:\n"
                f"   ragdiff query \"test\" --tool {provider_name} --config {output or 'config.yaml'}\n\n"
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
    from .display.formatting_v2 import format_comparison_markdown

    # Generate markdown using the shared utility (show all evaluations in CLI)
    markdown = format_comparison_markdown(comparison, max_evaluations=None)

    if output_path:
        with open(output_path, "w") as f:
            f.write(markdown)
        console.print(f"[green]✓[/green] Comparison exported to {output_path}")
    else:
        console.print(markdown)


def _output_eval_table(evaluation_result, output_path):
    """Output evaluation results as a table."""
    if output_path:
        console.print(
            "[yellow]Warning:[/yellow] Table format only supports console output"
        )
        console.print("[dim]Use --format json for file output[/dim]")

    console.print()
    console.print(f"[bold]Evaluation: {evaluation_result['run_label']}[/bold]")
    console.print(f"Provider: {evaluation_result['provider']}")
    console.print(f"Query Set: {evaluation_result['query_set']}")
    console.print()

    # Summary
    summary = evaluation_result["summary"]
    table = Table(title="Evaluation Summary", show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Score", style="white")

    table.add_row("Total Queries", str(summary["total_queries"]))
    table.add_row(
        "Successful",
        f"[green]{summary['successful_evaluations']}[/green]",
    )
    table.add_row("Failed", f"[red]{summary['failed_evaluations']}[/red]")
    table.add_row("Avg Correctness", f"{summary['avg_correctness']:.1f}/100")
    table.add_row("Avg Relevance", f"{summary['avg_relevance']:.1f}/100")
    table.add_row("Avg Completeness", f"{summary['avg_completeness']:.1f}/100")
    table.add_row(
        "Avg Overall Quality", f"[bold]{summary['avg_overall_quality']:.1f}/100[/bold]"
    )

    console.print(table)
    console.print()

    # Show sample evaluations
    console.print("[bold]Sample Evaluations:[/bold]")
    for i, eval_result in enumerate(evaluation_result["evaluations"][:5], 1):
        if eval_result["status"] == "failed":
            continue

        console.print(f"\n[cyan]{i}. Query:[/cyan] {eval_result['query'][:80]}...")
        console.print(f"   [dim]Reference:[/dim] {eval_result['reference'][:80]}...")

        evaluation = eval_result["evaluation"]
        console.print(
            f"   [green]Correctness:[/green] {evaluation.get('correctness', 0):.0f}/100"
        )
        console.print(
            f"   [green]Relevance:[/green] {evaluation.get('relevance', 0):.0f}/100"
        )
        console.print(
            f"   [green]Completeness:[/green] {evaluation.get('completeness', 0):.0f}/100"
        )
        console.print(
            f"   [bold green]Overall:[/bold green] {evaluation.get('overall_quality', 0):.0f}/100"
        )

        if "reasoning" in evaluation:
            reasoning = evaluation.get("reasoning", "")[:150]
            console.print(f"   [dim]Reasoning:[/dim] {reasoning}...")

    if len(evaluation_result["evaluations"]) > 5:
        console.print(
            f"\n[dim]... and {len(evaluation_result['evaluations']) - 5} more[/dim]"
        )


def _output_batched_comparison(comparison_result, output_path, format_type):
    """Output batched comparison results."""
    import json

    if format_type == "json":
        json_str = json.dumps(comparison_result, indent=2, ensure_ascii=False)
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(json_str)
            console.print(f"[green]✓[/green] Comparison exported to {output_path}")
        else:
            console.print(json_str)
        return

    # Table/markdown output
    console.print()
    console.print("[bold]Batched Comparison Results[/bold]")
    console.print()

    # Summary
    summary = comparison_result["summary"]
    table = Table(title="Comparison Summary", show_header=True)
    table.add_column("Provider", style="cyan")
    table.add_column("Wins", style="green", justify="right")
    table.add_column("Avg Score", style="yellow", justify="right")

    for run_info in summary["runs_compared"]:
        provider = run_info["provider"]
        wins = summary["provider_wins"].get(provider, 0)
        avg_score = summary["provider_avg_scores"].get(provider, 0.0)
        table.add_row(provider, str(wins), f"{avg_score:.1f}")

    console.print(table)
    console.print()
    console.print(f"Total Queries: {summary['total_queries']}")
    console.print(
        f"Successful Comparisons: [green]{summary['successful_comparisons']}[/green]"
    )
    console.print(f"Failed Comparisons: [red]{summary['failed_comparisons']}[/red]")

    if output_path and format_type == "markdown":
        # Save markdown version
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# Batched Comparison Results\n\n")
            f.write("## Summary\n\n")
            f.write("| Provider | Wins | Avg Score |\n")
            f.write("|----------|------|-----------|\n")
            for run_info in summary["runs_compared"]:
                provider = run_info["provider"]
                wins = summary["provider_wins"].get(provider, 0)
                avg_score = summary["provider_avg_scores"].get(provider, 0.0)
                f.write(f"| {provider} | {wins} | {avg_score:.1f} |\n")
        console.print(f"[green]✓[/green] Comparison exported to {output_path}")


def _output_eval_json(evaluation_result, output_path):
    """Output evaluation results as JSON."""
    import json

    json_str = json.dumps(evaluation_result, indent=2, ensure_ascii=False)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_str)
        console.print(f"[green]✓[/green] Evaluation exported to {output_path}")
    else:
        console.print(json_str)


def _output_reference_comparison_table(evaluations, output_path, format):
    """Output comparison table for multiple reference-based evaluations."""
    import json

    # Create comparison table
    console.print()
    console.print("[bold]Reference-Based Comparison[/bold]")
    console.print()

    # Summary table
    table = Table(title="Provider Comparison")
    table.add_column("Provider", style="cyan")
    table.add_column("Correctness", style="white")
    table.add_column("Relevance", style="white")
    table.add_column("Completeness", style="white")
    table.add_column("Overall Quality", style="bold white")

    for eval_result in evaluations:
        summary = eval_result["summary"]
        table.add_row(
            eval_result["provider"],
            f"{summary['avg_correctness']:.1f}/100",
            f"{summary['avg_relevance']:.1f}/100",
            f"{summary['avg_completeness']:.1f}/100",
            f"[bold]{summary['avg_overall_quality']:.1f}/100[/bold]",
        )

    console.print(table)
    console.print()

    # Find winner based on overall quality
    winner = max(evaluations, key=lambda e: e["summary"]["avg_overall_quality"])
    console.print(
        f"[green]Winner:[/green] {winner['provider']} "
        f"({winner['summary']['avg_overall_quality']:.1f}/100 overall quality)"
    )
    console.print()

    # If output path specified, export to JSON
    if output_path and format == "json":
        comparison_data = {
            "evaluations": evaluations,
            "winner": {
                "provider": winner["provider"],
                "avg_overall_quality": winner["summary"]["avg_overall_quality"],
            },
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(comparison_data, f, indent=2, ensure_ascii=False)
        console.print(f"[green]✓[/green] Comparison exported to {output_path}")


if __name__ == "__main__":
    app()
