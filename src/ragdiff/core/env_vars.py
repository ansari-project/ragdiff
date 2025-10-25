"""Environment variable substitution for RAGDiff v2.0.

This module handles ${VAR_NAME} placeholders in configuration files,
resolving them from environment variables or .env files.
"""

import os
import re
from pathlib import Path
from typing import Any

from .errors import ConfigError
from .logging import get_logger

logger = get_logger(__name__)

# Pattern for ${VAR_NAME} placeholders
ENV_VAR_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def load_env_file(env_file: Path | None = None) -> None:
    """Load environment variables from .env file.

    Args:
        env_file: Path to .env file. If None, looks for .env in current directory.

    Raises:
        ConfigError: If .env file exists but cannot be read

    Note:
        Uses python-dotenv to load variables into os.environ.
        Variables already set in environment take precedence.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        logger.warning(
            "python-dotenv not installed. Install with: pip install python-dotenv"
        )
        return

    if env_file is None:
        env_file = Path.cwd() / ".env"

    if env_file.exists():
        logger.debug(f"Loading environment variables from {env_file}")
        load_dotenv(env_file, override=False)  # Don't override existing env vars
    else:
        logger.debug(f"No .env file found at {env_file}")


def substitute_env_vars(value: Any, *, resolve_secrets: bool = True) -> Any:
    """Recursively substitute ${VAR_NAME} placeholders in a value.

    Args:
        value: Value to process (str, dict, list, or primitive)
        resolve_secrets: If True, resolve ${VAR_NAME} from environment.
                        If False, leave placeholders as-is (for snapshots).

    Returns:
        Value with placeholders substituted (or left as-is if resolve_secrets=False)

    Raises:
        ConfigError: If resolve_secrets=True and a referenced variable is not set

    Examples:
        # Resolve secrets (normal operation)
        >>> os.environ['API_KEY'] = 'secret123'
        >>> substitute_env_vars('key: ${API_KEY}')
        'key: secret123'

        # Preserve secrets (for snapshots)
        >>> substitute_env_vars('key: ${API_KEY}', resolve_secrets=False)
        'key: ${API_KEY}'

        # Nested structures
        >>> substitute_env_vars({'api_key': '${API_KEY}'}, resolve_secrets=True)
        {'api_key': 'secret123'}
    """
    if isinstance(value, str):
        return _substitute_string(value, resolve_secrets=resolve_secrets)
    elif isinstance(value, dict):
        return {
            k: substitute_env_vars(v, resolve_secrets=resolve_secrets)
            for k, v in value.items()
        }
    elif isinstance(value, list):
        return [substitute_env_vars(item, resolve_secrets=resolve_secrets) for item in value]
    else:
        # Primitives (int, float, bool, None) pass through
        return value


def _substitute_string(text: str, *, resolve_secrets: bool) -> str:
    """Substitute ${VAR_NAME} placeholders in a string.

    Args:
        text: String to process
        resolve_secrets: If True, resolve from environment. If False, leave as-is.

    Returns:
        String with substitutions applied (or original if resolve_secrets=False)

    Raises:
        ConfigError: If resolve_secrets=True and variable not found
    """
    if not resolve_secrets:
        # For snapshots, preserve placeholders
        return text

    def replace_match(match: re.Match) -> str:
        var_name = match.group(1)
        value = os.environ.get(var_name)

        if value is None:
            raise ConfigError(
                f"Environment variable '{var_name}' not set. "
                f"Set it in your environment or .env file."
            )

        return value

    return ENV_VAR_PATTERN.sub(replace_match, text)


def validate_env_vars(value: Any, *, required_vars: set[str] | None = None) -> set[str]:
    """Extract all ${VAR_NAME} placeholders from a value.

    Args:
        value: Value to scan (str, dict, list, or primitive)
        required_vars: Optional set to accumulate variable names

    Returns:
        Set of all environment variable names referenced

    Example:
        >>> config = {
        ...     'api_key': '${API_KEY}',
        ...     'endpoints': ['${BASE_URL}/v1', '${BASE_URL}/v2']
        ... }
        >>> validate_env_vars(config)
        {'API_KEY', 'BASE_URL'}
    """
    if required_vars is None:
        required_vars = set()

    if isinstance(value, str):
        for match in ENV_VAR_PATTERN.finditer(value):
            required_vars.add(match.group(1))
    elif isinstance(value, dict):
        for v in value.values():
            validate_env_vars(v, required_vars=required_vars)
    elif isinstance(value, list):
        for item in value:
            validate_env_vars(item, required_vars=required_vars)

    return required_vars


def check_required_vars(value: Any) -> None:
    """Check that all ${VAR_NAME} placeholders can be resolved.

    Args:
        value: Value to validate

    Raises:
        ConfigError: If any referenced variable is not set

    Example:
        >>> config = {'api_key': '${API_KEY}'}
        >>> check_required_vars(config)  # Raises if API_KEY not set
    """
    required = validate_env_vars(value)
    missing = {var for var in required if var not in os.environ}

    if missing:
        raise ConfigError(
            f"Missing required environment variables: {', '.join(sorted(missing))}. "
            f"Set them in your environment or .env file."
        )
