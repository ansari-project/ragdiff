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
    tools: list[str] = typer.Option(
        None,
        "--tool",
        "-t",
        help="RAG tools to query (defaults to all tools in config)",
    ),
    config_file: str = typer.Option(
        "configs/tafsir.yaml", "--config", "-c", help="Path to configuration file"
    ),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results to retrieve"),
    output_format: str = typer.Option(
        "display",
        "--format",
        "-f",
        help="Output format: display, json, markdown",
    ),
    output_file: Optional[str] = typer.Option(
        None, "--output", "-o", help="Save output to file"
    ),
    parallel: bool = typer.Option(
        True,
        "--parallel/--sequential",
        help="Run searches in parallel or sequential (for multiple tools)",
    ),
    evaluate: bool = typer.Option(
        False,
        "--evaluate/--no-evaluate",
        help="Enable LLM evaluation (for multiple tools)",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
):
    """Query one or more RAG systems.

    If no tools specified, queries all tools in config.
    If one tool is specified, runs a simple query.
    If multiple tools are specified, compares results side-by-side.

    Examples:
        # Query all tools in config
        ragdiff query "What is RAG?"

        # Single tool query
        ragdiff query "What is RAG?" --tool vectara

        # Compare specific tools
        ragdiff query "What is RAG?" --tool vectara --tool agentset --evaluate
    """
    setup_logging(verbose)

    try:
        # Load configuration
        if not Path(config_file).exists():
            console.print(f"[red]Configuration file not found: {config_file}[/red]")
            raise typer.Exit(1)

        config = Config(Path(config_file))
        config.validate()

        # Determine which tools to use (default to all if none specified)
        if not tools:
            tools = list(config.tools.keys())
            console.print(
                f"[dim]No tools specified, using all tools: {', '.join(tools)}[/dim]"
            )

        # Check all tools exist
        for tool in tools:
            if tool not in config.tools:
                console.print(f"[red]Tool '{tool}' not found in configuration[/red]")
                console.print(f"Available tools: {', '.join(config.tools.keys())}")
                raise typer.Exit(1)

        # Single tool query
        if len(tools) == 1:
            tool = tools[0]
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

                if output_file:
                    Path(output_file).write_text(output)
                    console.print(f"[green]Results saved to {output_file}[/green]")
                else:
                    console.print(output)
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

        # Multiple tool comparison
        else:
            console.print(f"[cyan]Comparing {len(tools)} tools...[/cyan]")

            # Create adapters
            adapters = {}
            for tool_name in tools:
                try:
                    adapters[tool_name] = create_adapter(
                        tool_name, config.tools[tool_name]
                    )
                    console.print(f"  ✓ {tool_name}")
                except Exception as e:
                    console.print(f"  ✗ {tool_name}: {str(e)}")

            if not adapters:
                console.print("[red]No tools available[/red]")
                raise typer.Exit(1)

            # Create comparison engine
            engine = ComparisonEngine(adapters)

            # Run comparison
            with console.status("[bold cyan]Running comparison...[/bold cyan]"):
                result = engine.run_comparison(
                    query_text, top_k=top_k, parallel=parallel
                )

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

            # Format and display
            formatter = ComparisonFormatter(result)

            if output_format == "display":
                formatter.display()
            else:
                output = formatter.format(output_format)

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
def batch(
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
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", "-o", help="Directory to save per-adapter output files"
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
    """Process batch queries from a file and save separate results per adapter.

    The queries file should contain one query per line.
    Results are saved as separate files for each adapter in the output directory.

    Examples:
        ragdiff batch queries.txt --config config.yaml --output-dir results/
        ragdiff batch queries.txt -t vectara -t goodmem --output-dir results/

    This creates:
        results/vectara.jsonl
        results/agentset.jsonl
        results/goodmem.jsonl
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

        # Create output directory if specified
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            console.print(f"[cyan]Output directory: {output_dir}[/cyan]")

        # Run batch queries - collect results per adapter
        adapter_results = {tool_name: [] for tool_name in adapters.keys()}

        for idx, query in enumerate(queries, 1):
            console.print(f"\n[cyan]Query {idx}/{len(queries)}: {query}[/cyan]")

            with console.status("[bold cyan]Running comparison...[/bold cyan]"):
                result = engine.run_comparison(query, top_k=top_k, parallel=parallel)

            # Store results by adapter
            for tool_name, tool_results in result.tool_results.items():
                adapter_results[tool_name].append(
                    {
                        "query": query,
                        "results": [
                            {
                                "id": r.id,
                                "text": r.text,
                                "score": r.score,
                                "source": r.source,
                                "metadata": r.metadata,
                            }
                            for r in tool_results
                        ],
                        "error": result.errors.get(tool_name),
                    }
                )

            console.print(f"[green]✓ Query {idx} complete[/green]")

        # Save separate files per adapter
        if output_dir:
            for tool_name, results in adapter_results.items():
                if output_format == "json":
                    output = json.dumps(results, indent=2, ensure_ascii=False)
                    file_ext = "json"
                else:  # jsonl
                    output = "\n".join(
                        json.dumps(r, ensure_ascii=False) for r in results
                    )
                    file_ext = "jsonl"

                output_file = output_path / f"{tool_name}.{file_ext}"
                output_file.write_text(output)
                console.print(
                    f"[green]  ✓ Saved {tool_name} results to {output_file}[/green]"
                )
        else:
            console.print(
                "[yellow]Warning: No output directory specified. Results not saved.[/yellow]"
            )
            console.print("[yellow]Use --output-dir to save results.[/yellow]")

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
    results_dir: str = typer.Argument(
        ..., help="Directory containing per-adapter result files"
    ),
    config_file: str = typer.Option(
        "configs/tafsir.yaml", "--config", "-c", help="Path to configuration file"
    ),
    output_file: Optional[str] = typer.Option(
        None, "--output", "-o", help="Save evaluation results to file"
    ),
    output_format: str = typer.Option(
        "jsonl",
        "--format",
        "-f",
        help="Output format: jsonl, json, markdown",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
):
    """Compare previously saved RAG results using LLM evaluation.

    Loads per-adapter result files from a directory and compares them
    using Claude LLM evaluation. This separates the expensive RAG queries
    from the evaluation step, allowing you to iterate on evaluation without
    re-running queries.

    Examples:
        ragdiff compare results/ --output evaluated.jsonl
        ragdiff compare results/ --format markdown --output report.md
    """
    setup_logging(verbose)

    try:
        # Load configuration
        if not Path(config_file).exists():
            console.print(f"[red]Configuration file not found: {config_file}[/red]")
            raise typer.Exit(1)

        config = Config(Path(config_file))
        llm_config = config.get_llm_config()
        if not llm_config:
            console.print("[red]LLM configuration not found in config file[/red]")
            raise typer.Exit(1)

        # Load all adapter result files
        results_path = Path(results_dir)
        if not results_path.exists():
            console.print(f"[red]Results directory not found: {results_dir}[/red]")
            raise typer.Exit(1)

        # Find all .jsonl and .json files
        result_files = list(results_path.glob("*.jsonl")) + list(
            results_path.glob("*.json")
        )
        if not result_files:
            console.print(f"[red]No result files found in {results_dir}[/red]")
            raise typer.Exit(1)

        console.print(f"[cyan]Found {len(result_files)} adapter result files[/cyan]")

        # Load results from each file
        adapter_data = {}
        for file_path in result_files:
            tool_name = file_path.stem  # filename without extension
            console.print(f"  Loading {tool_name}...")

            try:
                content = file_path.read_text()
                if file_path.suffix == ".jsonl":
                    # JSONL: one JSON object per line
                    adapter_data[tool_name] = [
                        json.loads(line)
                        for line in content.splitlines()
                        if line.strip()
                    ]
                else:
                    # JSON: array of objects
                    adapter_data[tool_name] = json.loads(content)

                console.print(
                    f"  ✓ {tool_name}: {len(adapter_data[tool_name])} queries"
                )
            except Exception as e:
                console.print(f"  ✗ {tool_name}: Failed to load - {e}")
                continue

        if not adapter_data:
            console.print("[red]No valid adapter data loaded[/red]")
            raise typer.Exit(1)

        # Verify all adapters have the same number of queries
        query_counts = {tool: len(data) for tool, data in adapter_data.items()}
        if len(set(query_counts.values())) > 1:
            console.print(
                "[yellow]Warning: Adapters have different numbers of queries:[/yellow]"
            )
            for tool, count in query_counts.items():
                console.print(f"  {tool}: {count} queries")

        # Initialize evaluator
        evaluator = LLMEvaluator(
            model=llm_config.get("model", "claude-sonnet-4-20250514"),
            api_key=os.getenv(llm_config.get("api_key_env", "ANTHROPIC_API_KEY")),
        )

        # Evaluate each query across all adapters
        evaluations = []
        num_queries = min(query_counts.values())

        for query_idx in range(num_queries):
            # Get the query text (should be same across all adapters)
            query_text = list(adapter_data.values())[0][query_idx]["query"]
            console.print(
                f"\n[cyan]Evaluating query {query_idx + 1}/{num_queries}: {query_text}[/cyan]"
            )

            # Build ComparisonResult from saved data
            tool_results = {}
            errors = {}

            for tool_name, tool_data in adapter_data.items():
                query_data = tool_data[query_idx]

                if query_data.get("error"):
                    errors[tool_name] = query_data["error"]
                    tool_results[tool_name] = []
                else:
                    # Convert back to RagResult objects
                    from .core.models import RagResult

                    tool_results[tool_name] = [
                        RagResult(
                            id=r["id"],
                            text=r["text"],
                            score=r["score"],
                            source=r["source"],
                            metadata=r.get("metadata", {}),
                        )
                        for r in query_data["results"]
                    ]

            # Create ComparisonResult
            comparison = ComparisonResult(
                query=query_text,
                tool_results=tool_results,
                errors=errors,
            )

            # Evaluate
            with console.status("[bold cyan]Running LLM evaluation...[/bold cyan]"):
                try:
                    evaluation = evaluator.evaluate(comparison)
                    console.print(f"[green]✓ Winner: {evaluation.winner}[/green]")

                    evaluations.append(
                        {
                            "query": query_text,
                            "winner": evaluation.winner,
                            "quality_scores": evaluation.quality_scores,
                            "analysis": evaluation.analysis,
                            "model": evaluation.llm_model,
                        }
                    )
                except Exception as e:
                    console.print(f"[yellow]Warning: Evaluation failed: {e}[/yellow]")

        # Save evaluations
        if output_file:
            # Auto-detect format from file extension if not explicitly set
            detected_format = output_format
            if output_format == "jsonl":  # default value
                ext = Path(output_file).suffix.lower()
                if ext == ".md":
                    detected_format = "markdown"
                elif ext == ".json":
                    detected_format = "json"

            if detected_format == "json":
                output = json.dumps(evaluations, indent=2, ensure_ascii=False)
            elif detected_format == "markdown":
                # Generate markdown report
                lines = ["# RAG Evaluation Report\n"]
                for eval_data in evaluations:
                    lines.append(f"## Query: {eval_data['query']}\n")
                    lines.append(f"**Winner:** {eval_data['winner']}\n")
                    lines.append("**Scores:**")
                    for tool, score in eval_data["quality_scores"].items():
                        lines.append(f"- {tool}: {score}/100")
                    lines.append(f"\n**Analysis:**\n{eval_data['analysis']}\n")
                    lines.append("---\n")
                output = "\n".join(lines)
            else:  # jsonl
                output = "\n".join(
                    json.dumps(e, ensure_ascii=False) for e in evaluations
                )

            Path(output_file).write_text(output)
            console.print(f"\n[green]Evaluations saved to {output_file}[/green]")
        else:
            # Print to console
            for eval_data in evaluations:
                console.print(f"\n[bold]Query:[/bold] {eval_data['query']}")
                console.print(f"[bold]Winner:[/bold] {eval_data['winner']}")
                console.print("[bold]Scores:[/bold]")
                for tool, score in eval_data["quality_scores"].items():
                    console.print(f"  {tool}: {score}/100")

        console.print(f"\n[green]✓ Evaluated {len(evaluations)} queries[/green]")

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


@app.command()
def generate_adapter(
    openapi_url: str = typer.Option(..., "--openapi-url", help="URL to OpenAPI specification"),
    api_key: str = typer.Option(..., "--api-key", help="API key for authentication"),
    test_query: str = typer.Option(..., "--test-query", help="Test query to execute"),
    adapter_name: str = typer.Option(..., "--adapter-name", help="Name for the adapter"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path (default: stdout)"),
    endpoint: Optional[str] = typer.Option(None, "--endpoint", help="Override endpoint path"),
    method: Optional[str] = typer.Option(None, "--method", help="Override HTTP method"),
    model: str = typer.Option("claude-3-5-sonnet-20241022", "--model", "-m", help="LLM model for generation"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
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
        from .openapi import ConfigGenerator
        import yaml

        console.print(Panel(
            "[cyan]OpenAPI Adapter Generator[/cyan]\n\n"
            f"Spec URL: {openapi_url}\n"
            f"Adapter Name: {adapter_name}\n"
            f"AI Model: {model}",
            title="Starting Generation",
            border_style="cyan"
        ))

        # Initialize generator
        console.print("\n[cyan]Initializing AI-powered generator...[/cyan]")
        generator = ConfigGenerator(model=model)

        # Generate configuration
        console.print(f"\n[cyan]Generating configuration for '{adapter_name}'...[/cyan]")
        console.print(f"[dim]This may take 30-60 seconds...[/dim]\n")

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
        console.print(Panel(
            f"[green]✓ Configuration generated successfully![/green]\n\n"
            f"[cyan]Next steps:[/cyan]\n"
            f"1. Set environment variable:\n"
            f"   export {config[adapter_name]['api_key_env']}=your_api_key_here\n\n"
            f"2. Test the adapter:\n"
            f"   ragdiff query \"test\" --tool {adapter_name} --config {output or 'config.yaml'}\n\n"
            f"3. Customize the config if needed (edit response_mapping, auth, etc.)",
            title="Success",
            border_style="green"
        ))

    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
