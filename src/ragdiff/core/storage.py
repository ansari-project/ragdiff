"""Storage utilities for RAGDiff v2.0 runs and comparisons.

This module handles JSON serialization and persistence of Run and Comparison objects.
"""

import json
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from .errors import ComparisonError, RunError
from .logging import get_logger
from .models_v2 import Comparison, Run
from .paths import (
    ensure_comparisons_dir,
    ensure_runs_dir,
    find_run_by_prefix,
    get_comparison_path,
    get_run_path,
)

logger = get_logger(__name__)


def save_run(run: Run, domains_dir: Path = Path("domains")) -> Path:
    """Save a run to disk as JSON.

    Args:
        run: Run object to save
        domains_dir: Root directory containing all domains

    Returns:
        Path to saved JSON file

    Raises:
        RunError: If file cannot be written

    Example:
        >>> run = Run(...)
        >>> path = save_run(run)
        >>> print(path)
        domains/tafsir/runs/2025-10-25/550e8400-....json
    """
    try:
        # Ensure directory exists
        ensure_runs_dir(run.domain, run.started_at, domains_dir)

        # Get file path
        run_path = get_run_path(run.domain, run.id, run.started_at, domains_dir)

        # Serialize to JSON
        run_json = run.model_dump_json(indent=2, exclude_none=False)

        # Write to file
        with open(run_path, "w", encoding="utf-8") as f:
            f.write(run_json)

        logger.info(f"Saved run {run.id} to {run_path}")
        return run_path

    except Exception as e:
        raise RunError(f"Failed to save run {run.id}: {e}") from e


def load_run(
    domain_name: str, run_id: UUID | str, domains_dir: Path = Path("domains")
) -> Run:
    """Load a run from disk.

    Args:
        domain_name: Name of the domain
        run_id: UUID of the run, UUID prefix, or label (e.g., 'vectara-20251026-001')
        domains_dir: Root directory containing all domains

    Returns:
        Loaded Run object

    Raises:
        RunError: If run not found or invalid

    Example:
        >>> run = load_run("tafsir", "550e8400-e29b-41d4-a716-446655440000")
        >>> print(run.provider)
        'vectara-default'

        # Also supports prefixes
        >>> run = load_run("tafsir", "550e")

        # Also supports labels
        >>> run = load_run("tafsir", "vectara-20251026-001")
    """
    try:
        # Try to find by label first (if it doesn't look like a UUID)
        if isinstance(run_id, str) and "-" in run_id and not _is_uuid_like(run_id):
            run_path = _find_run_by_label(domain_name, run_id, domains_dir)
        # Handle UUID prefix matching
        elif isinstance(run_id, str) and len(run_id) < 36:
            # Short prefix - search for match
            run_path = find_run_by_prefix(domain_name, run_id, domains_dir)
        else:
            # Full UUID - look in all date directories
            if isinstance(run_id, str):
                run_id = UUID(run_id)

            run_path = _find_run_by_full_uuid(domain_name, run_id, domains_dir)

        # Read JSON file
        with open(run_path, encoding="utf-8") as f:
            data = json.load(f)

        # Deserialize with Pydantic
        return Run(**data)

    except ValidationError as e:
        raise RunError(f"Invalid run data in {run_path}: {e}") from e
    except RunError:
        raise
    except Exception as e:
        raise RunError(f"Failed to load run {run_id}: {e}") from e


def _find_run_by_full_uuid(domain_name: str, run_id: UUID, domains_dir: Path) -> Path:
    """Find a run file by searching all date directories."""
    from .paths import get_domain_dir

    runs_base_dir = get_domain_dir(domain_name, domains_dir) / "runs"

    if not runs_base_dir.exists():
        raise RunError(f"No runs found for domain '{domain_name}'")

    # Search all date directories
    for date_dir in sorted(runs_base_dir.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue

        run_path = date_dir / f"{run_id}.json"
        if run_path.exists():
            return run_path

    raise RunError(f"Run {run_id} not found in domain '{domain_name}'")


def save_comparison(
    comparison: Comparison, domains_dir: Path = Path("domains")
) -> Path:
    """Save a comparison to disk as JSON.

    Args:
        comparison: Comparison object to save
        domains_dir: Root directory containing all domains

    Returns:
        Path to saved JSON file

    Raises:
        ComparisonError: If file cannot be written

    Example:
        >>> comparison = Comparison(...)
        >>> path = save_comparison(comparison)
        >>> print(path)
        domains/tafsir/comparisons/2025-10-25/660e8400-....json
    """
    try:
        # Ensure directory exists
        ensure_comparisons_dir(comparison.domain, comparison.created_at, domains_dir)

        # Get file path
        comparison_path = get_comparison_path(
            comparison.domain, comparison.id, comparison.created_at, domains_dir
        )

        # Serialize to JSON
        comparison_json = comparison.model_dump_json(indent=2, exclude_none=False)

        # Write to file
        with open(comparison_path, "w", encoding="utf-8") as f:
            f.write(comparison_json)

        logger.info(f"Saved comparison {comparison.id} to {comparison_path}")
        return comparison_path

    except Exception as e:
        raise ComparisonError(f"Failed to save comparison {comparison.id}: {e}") from e


def load_comparison(
    domain_name: str, comparison_id: UUID | str, domains_dir: Path = Path("domains")
) -> Comparison:
    """Load a comparison from disk.

    Args:
        domain_name: Name of the domain
        comparison_id: UUID of the comparison (full or prefix)
        domains_dir: Root directory containing all domains

    Returns:
        Loaded Comparison object

    Raises:
        ComparisonError: If comparison not found or invalid

    Example:
        >>> comp = load_comparison("tafsir", "660e8400-e29b-41d4-a716-446655440000")
        >>> print(len(comp.evaluations))
        10
    """
    try:
        # Handle UUID prefix matching
        if isinstance(comparison_id, str) and len(comparison_id) < 36:
            # Short prefix - search for match
            comparison_path = _find_comparison_by_prefix(
                domain_name, comparison_id, domains_dir
            )
        else:
            # Full UUID - look in all date directories
            if isinstance(comparison_id, str):
                comparison_id = UUID(comparison_id)

            comparison_path = _find_comparison_by_full_uuid(
                domain_name, comparison_id, domains_dir
            )

        # Read JSON file
        with open(comparison_path, encoding="utf-8") as f:
            data = json.load(f)

        # Deserialize with Pydantic
        return Comparison(**data)

    except ValidationError as e:
        raise ComparisonError(
            f"Invalid comparison data in {comparison_path}: {e}"
        ) from e
    except ComparisonError:
        raise
    except Exception as e:
        raise ComparisonError(f"Failed to load comparison {comparison_id}: {e}") from e


def _find_comparison_by_prefix(
    domain_name: str, prefix: str, domains_dir: Path
) -> Path:
    """Find a comparison by UUID prefix."""
    from .paths import get_domain_dir

    comparisons_base_dir = get_domain_dir(domain_name, domains_dir) / "comparisons"

    if not comparisons_base_dir.exists():
        raise ComparisonError(f"No comparisons found for domain '{domain_name}'")

    # Search all date directories
    matches = []
    for date_dir in sorted(comparisons_base_dir.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue

        for comparison_file in date_dir.glob(f"{prefix}*.json"):
            matches.append(comparison_file)

    if len(matches) == 0:
        raise ComparisonError(
            f"No comparison found matching prefix '{prefix}' in domain '{domain_name}'"
        )
    elif len(matches) > 1:
        raise ComparisonError(
            f"Multiple comparisons found matching prefix '{prefix}': "
            f"{', '.join(m.stem for m in matches)}. Use a longer prefix."
        )

    return matches[0]


def _find_comparison_by_full_uuid(
    domain_name: str, comparison_id: UUID, domains_dir: Path
) -> Path:
    """Find a comparison file by searching all date directories."""
    from .paths import get_domain_dir

    comparisons_base_dir = get_domain_dir(domain_name, domains_dir) / "comparisons"

    if not comparisons_base_dir.exists():
        raise ComparisonError(f"No comparisons found for domain '{domain_name}'")

    # Search all date directories
    for date_dir in sorted(comparisons_base_dir.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue

        comparison_path = date_dir / f"{comparison_id}.json"
        if comparison_path.exists():
            return comparison_path

    raise ComparisonError(
        f"Comparison {comparison_id} not found in domain '{domain_name}'"
    )


def _is_uuid_like(s: str) -> bool:
    """Check if a string looks like a UUID (8-4-4-4-12 format)."""
    try:
        UUID(s)
        return True
    except (ValueError, AttributeError):
        # Check if it's a valid UUID prefix (starts with hex chars)
        if len(s) <= 8 and all(c in "0123456789abcdefABCDEF-" for c in s):
            return True
        return False


def _find_run_by_label(domain_name: str, label: str, domains_dir: Path) -> Path:
    """Find a run by its label.

    Args:
        domain_name: Name of the domain
        label: Run label (e.g., 'vectara-20251026-001')
        domains_dir: Root directory containing all domains

    Returns:
        Path to the run file

    Raises:
        RunError: If run not found or multiple matches found
    """
    from .paths import get_domain_dir

    runs_base_dir = get_domain_dir(domain_name, domains_dir) / "runs"

    if not runs_base_dir.exists():
        raise RunError(f"No runs found for domain '{domain_name}'")

    # Search all date directories
    matches = []
    for date_dir in sorted(runs_base_dir.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue

        for run_file in date_dir.glob("*.json"):
            try:
                with open(run_file, encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("label") == label:
                    matches.append(run_file)
            except Exception:
                continue

    if len(matches) == 0:
        raise RunError(f"No run found with label '{label}' in domain '{domain_name}'")
    elif len(matches) > 1:
        raise RunError(
            f"Multiple runs found with label '{label}' (this should not happen)"
        )

    return matches[0]


def generate_run_label(
    domain_name: str, provider: str, date_str: str, domains_dir: Path = Path("domains")
) -> str:
    """Generate the next available label for a run.

    Args:
        domain_name: Name of the domain
        provider: Provider name (e.g., 'vectara-default')
        date_str: Date string in YYYY-MM-DD format
        domains_dir: Root directory containing all domains

    Returns:
        Next available label (e.g., 'vectara-default-20251026-001')

    Example:
        >>> label = generate_run_label("tafsir", "vectara-default", "2025-10-26")
        >>> print(label)
        'vectara-default-20251026-001'
    """
    from .paths import get_domain_dir

    # Format: {provider}-{YYYYMMDD}-{counter}
    date_part = date_str.replace("-", "")
    label_prefix = f"{provider}-{date_part}-"

    runs_base_dir = get_domain_dir(domain_name, domains_dir) / "runs"

    # Find existing runs with this prefix
    existing_counters = []
    if runs_base_dir.exists():
        for date_dir in runs_base_dir.iterdir():
            if not date_dir.is_dir():
                continue

            for run_file in date_dir.glob("*.json"):
                try:
                    with open(run_file, encoding="utf-8") as f:
                        data = json.load(f)
                    label = data.get("label", "")
                    if label.startswith(label_prefix):
                        # Extract counter from label
                        counter_str = label[len(label_prefix) :]
                        if counter_str.isdigit():
                            existing_counters.append(int(counter_str))
                except Exception:
                    continue

    # Get next counter
    next_counter = max(existing_counters, default=0) + 1

    return f"{label_prefix}{next_counter:03d}"


def generate_comparison_label(
    domain_name: str, date_str: str, domains_dir: Path = Path("domains")
) -> str:
    """Generate the next available label for a comparison.

    Args:
        domain_name: Name of the domain
        date_str: Date string in YYYY-MM-DD format
        domains_dir: Root directory containing all domains

    Returns:
        Next available label (e.g., 'comparison-20251026-001')

    Example:
        >>> label = generate_comparison_label("tafsir", "2025-10-26")
        >>> print(label)
        'comparison-20251026-001'
    """
    from .paths import get_domain_dir

    # Format: comparison-{YYYYMMDD}-{counter}
    date_part = date_str.replace("-", "")
    label_prefix = f"comparison-{date_part}-"

    comparisons_base_dir = get_domain_dir(domain_name, domains_dir) / "comparisons"

    # Find existing comparisons with this prefix
    existing_counters = []
    if comparisons_base_dir.exists():
        for date_dir in comparisons_base_dir.iterdir():
            if not date_dir.is_dir():
                continue

            for comp_file in date_dir.glob("*.json"):
                try:
                    with open(comp_file, encoding="utf-8") as f:
                        data = json.load(f)
                    label = data.get("label", "")
                    if label.startswith(label_prefix):
                        # Extract counter from label
                        counter_str = label[len(label_prefix) :]
                        if counter_str.isdigit():
                            existing_counters.append(int(counter_str))
                except Exception:
                    continue

    # Get next counter
    next_counter = max(existing_counters, default=0) + 1

    return f"{label_prefix}{next_counter:03d}"


def list_runs(
    domain_name: str,
    limit: int | None = None,
    provider: str | None = None,
    query_set: str | None = None,
    domains_dir: Path = Path("domains"),
) -> list[Run]:
    """List runs for a domain, optionally filtered.

    Args:
        domain_name: Name of the domain
        limit: Maximum number of runs to return (most recent first)
        provider: Filter by provider name
        query_set: Filter by query set name
        domains_dir: Root directory containing all domains

    Returns:
        List of Run objects, sorted by started_at (most recent first)

    Example:
        >>> runs = list_runs("tafsir", limit=10)
        >>> runs = list_runs("tafsir", provider="vectara-default")
        >>> runs = list_runs("tafsir", query_set="test-queries")
    """
    from .paths import get_domain_dir

    runs_base_dir = get_domain_dir(domain_name, domains_dir) / "runs"

    if not runs_base_dir.exists():
        return []

    # Collect all run files
    run_files = []
    for date_dir in sorted(runs_base_dir.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue

        for run_file in sorted(date_dir.glob("*.json"), reverse=True):
            run_files.append(run_file)

    # Load and filter runs
    runs = []
    for run_file in run_files:
        try:
            with open(run_file, encoding="utf-8") as f:
                data = json.load(f)

            # Apply filters without loading full Run object
            if provider and data.get("provider") != provider:
                continue
            if query_set and data.get("query_set") != query_set:
                continue

            # Load full Run object
            run = Run(**data)
            runs.append(run)

            # Stop if we've reached the limit
            if limit and len(runs) >= limit:
                break

        except Exception as e:
            logger.warning(f"Failed to load run from {run_file}: {e}")
            continue

    return runs


def list_comparisons(
    domain_name: str,
    limit: int | None = None,
    domains_dir: Path = Path("domains"),
) -> list[Comparison]:
    """List comparisons for a domain.

    Args:
        domain_name: Name of the domain
        limit: Maximum number of comparisons to return (most recent first)
        domains_dir: Root directory containing all domains

    Returns:
        List of Comparison objects, sorted by created_at (most recent first)

    Example:
        >>> comparisons = list_comparisons("tafsir", limit=5)
    """
    from .paths import get_domain_dir

    comparisons_base_dir = get_domain_dir(domain_name, domains_dir) / "comparisons"

    if not comparisons_base_dir.exists():
        return []

    # Collect all comparison files
    comparison_files = []
    for date_dir in sorted(comparisons_base_dir.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue

        for comparison_file in sorted(date_dir.glob("*.json"), reverse=True):
            comparison_files.append(comparison_file)

    # Load comparisons
    comparisons = []
    for comparison_file in comparison_files:
        try:
            with open(comparison_file, encoding="utf-8") as f:
                data = json.load(f)

            comparison = Comparison(**data)
            comparisons.append(comparison)

            # Stop if we've reached the limit
            if limit and len(comparisons) >= limit:
                break

        except Exception as e:
            logger.warning(f"Failed to load comparison from {comparison_file}: {e}")
            continue

    return comparisons
