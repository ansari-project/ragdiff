"""File path utilities for RAGDiff v2.0.

This module provides functions for generating and managing file paths
in the domain-based directory structure.
"""

from datetime import datetime
from pathlib import Path
from uuid import UUID

from .errors import ConfigError, RunError
from .logging import get_logger

logger = get_logger(__name__)


def get_domain_dir(domain_name: str, domains_dir: Path = Path("domains")) -> Path:
    """Get the directory for a domain.

    Args:
        domain_name: Name of the domain
        domains_dir: Root directory containing all domains

    Returns:
        Path to domain directory

    Example:
        >>> get_domain_dir("tafsir")
        PosixPath('domains/tafsir')
    """
    return domains_dir / domain_name


def get_systems_dir(domain_name: str, domains_dir: Path = Path("domains")) -> Path:
    """Get the systems directory for a domain.

    Args:
        domain_name: Name of the domain
        domains_dir: Root directory containing all domains

    Returns:
        Path to systems directory

    Example:
        >>> get_systems_dir("tafsir")
        PosixPath('domains/tafsir/systems')
    """
    return domains_dir / domain_name / "systems"


def get_query_sets_dir(domain_name: str, domains_dir: Path = Path("domains")) -> Path:
    """Get the query-sets directory for a domain.

    Args:
        domain_name: Name of the domain
        domains_dir: Root directory containing all domains

    Returns:
        Path to query-sets directory

    Example:
        >>> get_query_sets_dir("tafsir")
        PosixPath('domains/tafsir/query-sets')
    """
    return domains_dir / domain_name / "query-sets"


def get_runs_dir(
    domain_name: str, date: datetime | None = None, domains_dir: Path = Path("domains")
) -> Path:
    """Get the runs directory for a domain and date.

    Args:
        domain_name: Name of the domain
        date: Date for runs (defaults to today)
        domains_dir: Root directory containing all domains

    Returns:
        Path to runs directory for the specified date

    Example:
        >>> from datetime import datetime
        >>> get_runs_dir("tafsir", datetime(2025, 10, 25))
        PosixPath('domains/tafsir/runs/2025-10-25')
    """
    if date is None:
        date = datetime.utcnow()

    date_str = date.strftime("%Y-%m-%d")
    return domains_dir / domain_name / "runs" / date_str


def get_comparisons_dir(
    domain_name: str, date: datetime | None = None, domains_dir: Path = Path("domains")
) -> Path:
    """Get the comparisons directory for a domain and date.

    Args:
        domain_name: Name of the domain
        date: Date for comparisons (defaults to today)
        domains_dir: Root directory containing all domains

    Returns:
        Path to comparisons directory for the specified date

    Example:
        >>> from datetime import datetime
        >>> get_comparisons_dir("tafsir", datetime(2025, 10, 25))
        PosixPath('domains/tafsir/comparisons/2025-10-25')
    """
    if date is None:
        date = datetime.utcnow()

    date_str = date.strftime("%Y-%m-%d")
    return domains_dir / domain_name / "comparisons" / date_str


def get_run_path(
    domain_name: str,
    run_id: UUID,
    date: datetime | None = None,
    domains_dir: Path = Path("domains"),
) -> Path:
    """Get the file path for a run.

    Args:
        domain_name: Name of the domain
        run_id: UUID of the run
        date: Date of run (defaults to today)
        domains_dir: Root directory containing all domains

    Returns:
        Path to run JSON file

    Example:
        >>> from uuid import UUID
        >>> run_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        >>> get_run_path("tafsir", run_id)
        PosixPath('domains/tafsir/runs/2025-10-25/550e8400-e29b-41d4-a716-446655440000.json')
    """
    runs_dir = get_runs_dir(domain_name, date, domains_dir)
    return runs_dir / f"{run_id}.json"


def get_comparison_path(
    domain_name: str,
    comparison_id: UUID,
    date: datetime | None = None,
    domains_dir: Path = Path("domains"),
) -> Path:
    """Get the file path for a comparison.

    Args:
        domain_name: Name of the domain
        comparison_id: UUID of the comparison
        date: Date of comparison (defaults to today)
        domains_dir: Root directory containing all domains

    Returns:
        Path to comparison JSON file

    Example:
        >>> from uuid import UUID
        >>> comp_id = UUID("660e8400-e29b-41d4-a716-446655440000")
        >>> get_comparison_path("tafsir", comp_id)
        PosixPath('domains/tafsir/comparisons/2025-10-25/660e8400-e29b-41d4-a716-446655440000.json')
    """
    comparisons_dir = get_comparisons_dir(domain_name, date, domains_dir)
    return comparisons_dir / f"{comparison_id}.json"


def ensure_domain_structure(
    domain_name: str, domains_dir: Path = Path("domains")
) -> None:
    """Ensure all necessary directories exist for a domain.

    Creates:
    - domains/<domain>/
    - domains/<domain>/systems/
    - domains/<domain>/query-sets/
    - domains/<domain>/runs/
    - domains/<domain>/comparisons/

    Args:
        domain_name: Name of the domain
        domains_dir: Root directory containing all domains

    Raises:
        ConfigError: If directories cannot be created

    Example:
        >>> ensure_domain_structure("tafsir")
        # Creates all necessary directories
    """
    try:
        domain_dir = get_domain_dir(domain_name, domains_dir)
        systems_dir = get_systems_dir(domain_name, domains_dir)
        query_sets_dir = get_query_sets_dir(domain_name, domains_dir)
        runs_dir = domain_dir / "runs"
        comparisons_dir = domain_dir / "comparisons"

        for directory in [domain_dir, systems_dir, query_sets_dir, runs_dir, comparisons_dir]:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory exists: {directory}")

    except Exception as e:
        raise ConfigError(f"Failed to create domain structure for '{domain_name}': {e}")


def ensure_runs_dir(
    domain_name: str, date: datetime | None = None, domains_dir: Path = Path("domains")
) -> Path:
    """Ensure the runs directory exists for a specific date.

    Args:
        domain_name: Name of the domain
        date: Date for runs (defaults to today)
        domains_dir: Root directory containing all domains

    Returns:
        Path to runs directory

    Raises:
        RunError: If directory cannot be created

    Example:
        >>> ensure_runs_dir("tafsir")
        PosixPath('domains/tafsir/runs/2025-10-25')
    """
    try:
        runs_dir = get_runs_dir(domain_name, date, domains_dir)
        runs_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured runs directory exists: {runs_dir}")
        return runs_dir
    except Exception as e:
        raise RunError(f"Failed to create runs directory: {e}")


def ensure_comparisons_dir(
    domain_name: str, date: datetime | None = None, domains_dir: Path = Path("domains")
) -> Path:
    """Ensure the comparisons directory exists for a specific date.

    Args:
        domain_name: Name of the domain
        date: Date for comparisons (defaults to today)
        domains_dir: Root directory containing all domains

    Returns:
        Path to comparisons directory

    Raises:
        RunError: If directory cannot be created

    Example:
        >>> ensure_comparisons_dir("tafsir")
        PosixPath('domains/tafsir/comparisons/2025-10-25')
    """
    try:
        comparisons_dir = get_comparisons_dir(domain_name, date, domains_dir)
        comparisons_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured comparisons directory exists: {comparisons_dir}")
        return comparisons_dir
    except Exception as e:
        raise RunError(f"Failed to create comparisons directory: {e}")


def find_run_by_prefix(
    domain_name: str, prefix: str, domains_dir: Path = Path("domains")
) -> Path:
    """Find a run by UUID prefix (e.g., '550e' matches '550e8400-...').

    Args:
        domain_name: Name of the domain
        prefix: UUID prefix to search for
        domains_dir: Root directory containing all domains

    Returns:
        Path to matching run file

    Raises:
        RunError: If no match found or multiple matches found

    Example:
        >>> find_run_by_prefix("tafsir", "550e")
        PosixPath('domains/tafsir/runs/2025-10-25/550e8400-e29b-41d4-a716-446655440000.json')
    """
    runs_base_dir = get_domain_dir(domain_name, domains_dir) / "runs"

    if not runs_base_dir.exists():
        raise RunError(f"No runs found for domain '{domain_name}'")

    # Search all date directories
    matches = []
    for date_dir in sorted(runs_base_dir.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue

        for run_file in date_dir.glob(f"{prefix}*.json"):
            matches.append(run_file)

    if len(matches) == 0:
        raise RunError(
            f"No run found matching prefix '{prefix}' in domain '{domain_name}'"
        )
    elif len(matches) > 1:
        raise RunError(
            f"Multiple runs found matching prefix '{prefix}': "
            f"{', '.join(m.stem for m in matches)}. Use a longer prefix."
        )

    return matches[0]


def list_systems(domain_name: str, domains_dir: Path = Path("domains")) -> list[str]:
    """List all systems in a domain.

    Args:
        domain_name: Name of the domain
        domains_dir: Root directory containing all domains

    Returns:
        List of system names (without .yaml extension)

    Example:
        >>> list_systems("tafsir")
        ['vectara-default', 'vectara-mmr', 'agentset']
    """
    systems_dir = get_systems_dir(domain_name, domains_dir)

    if not systems_dir.exists():
        return []

    return sorted(
        [f.stem for f in systems_dir.glob("*.yaml") if f.is_file()]
    )


def list_query_sets(domain_name: str, domains_dir: Path = Path("domains")) -> list[str]:
    """List all query sets in a domain.

    Args:
        domain_name: Name of the domain
        domains_dir: Root directory containing all domains

    Returns:
        List of query set names (without extensions)

    Example:
        >>> list_query_sets("tafsir")
        ['test-queries', 'eval-set-v1']
    """
    query_sets_dir = get_query_sets_dir(domain_name, domains_dir)

    if not query_sets_dir.exists():
        return []

    # Collect both .txt and .jsonl files
    names = set()
    for pattern in ["*.txt", "*.jsonl"]:
        for f in query_sets_dir.glob(pattern):
            if f.is_file():
                names.add(f.stem)

    return sorted(names)
