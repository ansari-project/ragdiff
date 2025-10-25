"""Command-line interface for RAGDiff v2.0.

RAGDiff v2.0 uses a domain-based architecture for comparing RAG systems.

Commands:
- run: Execute a query set against a system
- compare: Compare multiple runs using LLM evaluation
"""

import typer
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Typer app
app = typer.Typer(
    name="ragdiff",
    help="RAGDiff v2.0 - Domain-based RAG system comparison",
    add_completion=False,
    no_args_is_help=True,
)


# ============================================================================
# v2.0 Commands (Domain-based architecture)
# ============================================================================

from .cli_v2 import run as v2_run, compare as v2_compare

# Add v2.0 commands as primary commands
app.command(name="run", help="Execute a query set against a system")(v2_run)
app.command(name="compare", help="Compare multiple runs using LLM evaluation")(v2_compare)


if __name__ == "__main__":
    app()
