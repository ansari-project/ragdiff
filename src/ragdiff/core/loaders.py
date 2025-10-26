"""File loaders for RAGDiff v2.0 configuration files.

This module provides functions to load domains, systems, and query sets
from the file system.
"""

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .env_vars import check_required_vars, substitute_env_vars
from .errors import ConfigError
from .logging import get_logger
from .models_v2 import Domain, ProviderConfig, Query, QuerySet

logger = get_logger(__name__)


def load_yaml(path: Path) -> dict[str, Any]:
    """Load and parse a YAML file.

    Args:
        path: Path to YAML file

    Returns:
        Parsed YAML as dictionary

    Raises:
        ConfigError: If file cannot be read or YAML is invalid
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if not isinstance(data, dict):
                raise ConfigError(
                    f"Invalid YAML in {path}: expected dictionary, got {type(data).__name__}"
                )
            return data
    except FileNotFoundError:
        raise ConfigError(f"Configuration file not found: {path}") from None
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML syntax in {path}: {e}") from e
    except Exception as e:
        raise ConfigError(f"Failed to read {path}: {e}") from e


def load_domain(domain_name: str, domains_dir: Path = Path("domains")) -> Domain:
    """Load domain configuration from domains/<domain>/domain.yaml.

    Args:
        domain_name: Name of the domain (e.g., "tafsir")
        domains_dir: Root directory containing all domains (default: "domains")

    Returns:
        Validated Domain model

    Raises:
        ConfigError: If domain file not found, invalid, or missing required fields

    Example:
        >>> domain = load_domain("tafsir")
        >>> print(domain.name)
        'tafsir'
        >>> print(domain.evaluator.model)
        'claude-3-5-sonnet-20241022'
    """
    domain_path = domains_dir / domain_name / "domain.yaml"

    if not domain_path.exists():
        raise ConfigError(
            f"Domain '{domain_name}' not found at {domain_path}. "
            f"Create the directory and domain.yaml file."
        )

    logger.debug(f"Loading domain from {domain_path}")

    try:
        raw_data = load_yaml(domain_path)

        # Add domain name if not present
        if "name" not in raw_data:
            raw_data["name"] = domain_name

        # Validate all environment variables are set before substituting
        check_required_vars(raw_data)

        # Substitute environment variables (resolve secrets for runtime use)
        resolved_data = substitute_env_vars(raw_data, resolve_secrets=True)

        # Validate with Pydantic
        return Domain(**resolved_data)

    except ValidationError as e:
        raise ConfigError(f"Invalid domain configuration in {domain_path}: {e}") from e


def load_provider(
    domain_name: str, provider_name: str, domains_dir: Path = Path("domains")
) -> ProviderConfig:
    """Load system configuration from domains/<domain>/systems/<name>.yaml.

    Args:
        domain_name: Name of the domain
        provider_name: Name of the system (e.g., "vectara-default")
        domains_dir: Root directory containing all domains

    Returns:
        Validated ProviderConfig model

    Raises:
        ConfigError: If provider file not found, invalid, or missing required fields

    Example:
        >>> system = load_provider("tafsir", "vectara-default")
        >>> print(system.tool)
        'vectara'
        >>> print(system.config['top_k'])
        5
    """
    system_path = domains_dir / domain_name / "providers" / f"{provider_name}.yaml"

    if not system_path.exists():
        raise ConfigError(
            f"System '{provider_name}' not found at {system_path}. "
            f"Create the system configuration file."
        )

    logger.debug(f"Loading system from {system_path}")

    try:
        raw_data = load_yaml(system_path)

        # Add system name if not present
        if "name" not in raw_data:
            raw_data["name"] = provider_name

        # Validate all environment variables are set
        check_required_vars(raw_data)

        # Substitute environment variables (resolve secrets for runtime use)
        resolved_data = substitute_env_vars(raw_data, resolve_secrets=True)

        # Validate with Pydantic
        return ProviderConfig(**resolved_data)

    except ValidationError as e:
        raise ConfigError(f"Invalid system configuration in {system_path}: {e}") from e


def load_provider_for_snapshot(
    domain_name: str, provider_name: str, domains_dir: Path = Path("domains")
) -> ProviderConfig:
    """Load provider configuration WITHOUT resolving secrets (for snapshots).

    This is used when creating Run snapshots. It preserves ${VAR_NAME} placeholders
    so that runs can be shared without leaking credentials.

    Args:
        domain_name: Name of the domain
        provider_name: Name of the provider
        domains_dir: Root directory containing all domains

    Returns:
        ProviderConfig with unresolved ${VAR_NAME} placeholders

    Raises:
        ConfigError: If provider file not found or invalid

    Example:
        >>> provider = load_provider_for_snapshot("tafsir", "vectara-default")
        >>> print(provider.config['api_key'])
        '${VECTARA_API_KEY}'  # Placeholder preserved!
    """
    system_path = domains_dir / domain_name / "providers" / f"{provider_name}.yaml"

    if not system_path.exists():
        raise ConfigError(f"System '{provider_name}' not found at {system_path}")

    logger.debug(f"Loading system (snapshot mode) from {system_path}")

    try:
        raw_data = load_yaml(system_path)

        # Add system name if not present
        if "name" not in raw_data:
            raw_data["name"] = provider_name

        # DO NOT resolve secrets - keep ${VAR_NAME} placeholders
        unresolved_data = substitute_env_vars(raw_data, resolve_secrets=False)

        # Validate with Pydantic
        return ProviderConfig(**unresolved_data)

    except ValidationError as e:
        raise ConfigError(f"Invalid system configuration in {system_path}: {e}") from e


def load_query_set(
    domain_name: str, query_set_name: str, domains_dir: Path = Path("domains")
) -> QuerySet:
    """Load query set from domains/<domain>/query-sets/<name>.{txt,jsonl}.

    Supports two formats:
    1. .txt: One query per line (no reference answers)
    2. .jsonl: {"query": "...", "reference": "..."} per line

    Args:
        domain_name: Name of the domain
        query_set_name: Name of the query set (without extension)
        domains_dir: Root directory containing all domains

    Returns:
        Validated QuerySet model

    Raises:
        ConfigError: If query set file not found, invalid, or exceeds 1000 query limit

    Example:
        >>> qs = load_query_set("tafsir", "test-queries")
        >>> print(len(qs.queries))
        10
        >>> print(qs.queries[0].text)
        'What is Islamic inheritance law?'
    """
    query_set_dir = domains_dir / domain_name / "query-sets"

    # Try .txt first, then .jsonl
    txt_path = query_set_dir / f"{query_set_name}.txt"
    jsonl_path = query_set_dir / f"{query_set_name}.jsonl"

    if txt_path.exists():
        return _load_txt_query_set(domain_name, query_set_name, txt_path)
    elif jsonl_path.exists():
        return _load_jsonl_query_set(domain_name, query_set_name, jsonl_path)
    else:
        raise ConfigError(
            f"Query set '{query_set_name}' not found. "
            f"Expected {txt_path} or {jsonl_path}"
        )


def _load_txt_query_set(domain_name: str, query_set_name: str, path: Path) -> QuerySet:
    """Load query set from .txt file (one query per line)."""
    logger.debug(f"Loading query set from {path}")

    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()

        # Parse queries (skip empty lines and comments)
        queries = []
        for line_num, line in enumerate(lines, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            try:
                queries.append(Query(text=line))
            except ValidationError as e:
                raise ConfigError(
                    f"Invalid query at line {line_num} in {path}: {e}"
                ) from e

        if not queries:
            raise ConfigError(f"Query set is empty: {path}")

        # Validate with Pydantic (enforces 1000 query limit)
        return QuerySet(name=query_set_name, domain=domain_name, queries=queries)

    except ConfigError:
        raise
    except Exception as e:
        raise ConfigError(f"Failed to read query set {path}: {e}") from e


def _load_jsonl_query_set(
    domain_name: str, query_set_name: str, path: Path
) -> QuerySet:
    """Load query set from .jsonl file (one JSON object per line)."""
    logger.debug(f"Loading query set from {path}")

    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()

        # Parse JSONL
        queries = []
        for line_num, line in enumerate(lines, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            try:
                data = json.loads(line)
                if not isinstance(data, dict):
                    raise ConfigError(
                        f"Expected JSON object, got {type(data).__name__}"
                    )

                # Support both 'query' and 'text' keys
                query_text = data.get("query") or data.get("text")
                if not query_text:
                    raise ConfigError("Missing 'query' or 'text' field")

                queries.append(
                    Query(
                        text=query_text,
                        reference=data.get("reference"),
                        metadata=data.get("metadata", {}),
                    )
                )

            except json.JSONDecodeError as e:
                raise ConfigError(
                    f"Invalid JSON at line {line_num} in {path}: {e}"
                ) from e
            except ValidationError as e:
                raise ConfigError(
                    f"Invalid query at line {line_num} in {path}: {e}"
                ) from e

        if not queries:
            raise ConfigError(f"Query set is empty: {path}")

        # Validate with Pydantic (enforces 1000 query limit)
        return QuerySet(name=query_set_name, domain=domain_name, queries=queries)

    except ConfigError:
        raise
    except Exception as e:
        raise ConfigError(f"Failed to read query set {path}: {e}") from e
