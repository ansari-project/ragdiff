"""Thread-safe serialization utilities for RAGDiff.

This module provides centralized, thread-safe JSON serialization for all
data models in the library. It ensures consistent output formatting and
prevents race conditions during serialization.

Thread-Safety:
    All functions in this module are thread-safe. JSON serialization is
    performed using thread-safe operations, and no global state is mutated.
"""

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any


def to_json(obj: Any, pretty: bool = True, sort_keys: bool = False) -> str:
    """Convert an object to JSON string.

    Thread-safe JSON serialization with support for common Python types
    including dataclasses, datetime objects, and nested structures.

    Args:
        obj: Object to serialize (dataclass, dict, list, etc.)
        pretty: Whether to pretty-print with indentation (default: True)
        sort_keys: Whether to sort dictionary keys (default: False)

    Returns:
        JSON string representation

    Raises:
        TypeError: If object contains non-serializable types

    Thread-Safety:
        This function is thread-safe and can be called concurrently.
        Each call operates on its own data without shared state.

    Example:
        >>> from ragdiff.core.models import RagResult
        >>> result = RagResult(id="1", text="test", score=0.95)
        >>> json_str = to_json(result)
        >>> print(json_str)
        {
          "id": "1",
          "text": "test",
          "score": 0.95,
          ...
        }
    """
    data = to_serializable(obj)

    if pretty:
        return json.dumps(data, indent=2, sort_keys=sort_keys, ensure_ascii=False)
    else:
        return json.dumps(data, sort_keys=sort_keys, ensure_ascii=False)


def to_serializable(obj: Any) -> Any:
    """Convert an object to a JSON-serializable format.

    Recursively converts objects to JSON-compatible types:
    - Dataclasses -> dict
    - datetime -> ISO format string
    - Custom objects with to_dict() method -> dict
    - Lists, tuples -> list
    - Dicts -> dict (with serialized values)
    - Primitives (str, int, float, bool, None) -> as-is

    Args:
        obj: Object to convert

    Returns:
        JSON-serializable representation

    Thread-Safety:
        This function is thread-safe and can be called concurrently.
        It creates new data structures without modifying the input.

    Example:
        >>> from datetime import datetime
        >>> data = {"timestamp": datetime.now(), "count": 5}
        >>> serializable = to_serializable(data)
        >>> isinstance(serializable["timestamp"], str)
        True
    """
    # Handle None
    if obj is None:
        return None

    # Handle datetime
    if isinstance(obj, datetime):
        return obj.isoformat()

    # Handle dataclasses
    if is_dataclass(obj) and not isinstance(obj, type):
        # Convert to dict first, then recursively serialize
        return to_serializable(asdict(obj))

    # Handle objects with to_dict method
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return to_serializable(obj.to_dict())

    # Handle dictionaries
    if isinstance(obj, dict):
        return {key: to_serializable(value) for key, value in obj.items()}

    # Handle lists and tuples
    if isinstance(obj, (list, tuple)):
        return [to_serializable(item) for item in obj]

    # Handle sets
    if isinstance(obj, set):
        return [to_serializable(item) for item in sorted(obj)]

    # Handle primitives (str, int, float, bool)
    if isinstance(obj, (str, int, float, bool)):
        return obj

    # Fallback: convert to string
    # This ensures we always return something serializable
    return str(obj)


def from_json(json_str: str) -> Any:
    """Parse JSON string to Python object.

    Thread-safe JSON deserialization.

    Args:
        json_str: JSON string to parse

    Returns:
        Parsed Python object (dict, list, etc.)

    Raises:
        json.JSONDecodeError: If JSON is malformed

    Thread-Safety:
        This function is thread-safe and can be called concurrently.

    Example:
        >>> json_str = '{"name": "test", "count": 5}'
        >>> data = from_json(json_str)
        >>> data["name"]
        'test'
    """
    return json.loads(json_str)


def to_dict(obj: Any) -> dict[str, Any]:
    """Convert an object to a dictionary.

    Convenience function that converts an object to a dict and ensures
    all values are JSON-serializable.

    Args:
        obj: Object to convert (must be dataclass or have to_dict method)

    Returns:
        Dictionary representation with serializable values

    Raises:
        TypeError: If object cannot be converted to dict

    Thread-Safety:
        This function is thread-safe and can be called concurrently.

    Example:
        >>> from ragdiff.core.models import RagResult
        >>> result = RagResult(id="1", text="test", score=0.95)
        >>> data = to_dict(result)
        >>> isinstance(data, dict)
        True
    """
    # Handle dataclasses
    if is_dataclass(obj) and not isinstance(obj, type):
        data = asdict(obj)
        return to_serializable(data)

    # Handle objects with to_dict method
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        data = obj.to_dict()
        return to_serializable(data)

    # Handle dictionaries
    if isinstance(obj, dict):
        return to_serializable(obj)

    raise TypeError(
        f"Object of type {type(obj).__name__} cannot be converted to dict. "
        f"Must be a dataclass or have a to_dict() method."
    )


def format_json_output(
    obj: Any,
    pretty: bool = True,
    sort_keys: bool = False,
    include_nulls: bool = True,
) -> str:
    """Format an object as JSON with additional formatting options.

    This is a more flexible version of to_json() that provides additional
    control over the output format.

    Args:
        obj: Object to serialize
        pretty: Whether to pretty-print with indentation (default: True)
        sort_keys: Whether to sort dictionary keys (default: False)
        include_nulls: Whether to include null/None values (default: True)

    Returns:
        Formatted JSON string

    Thread-Safety:
        This function is thread-safe and can be called concurrently.

    Example:
        >>> data = {"name": "test", "value": None, "count": 5}
        >>> json_str = format_json_output(data, include_nulls=False)
        >>> "value" in json_str
        False
    """
    # Convert to serializable format
    data = to_serializable(obj)

    # Optionally remove null values
    if not include_nulls:
        data = _remove_nulls(data)

    # Serialize to JSON
    if pretty:
        return json.dumps(data, indent=2, sort_keys=sort_keys, ensure_ascii=False)
    else:
        return json.dumps(data, sort_keys=sort_keys, ensure_ascii=False)


def _remove_nulls(obj: Any) -> Any:
    """Recursively remove None/null values from data structures.

    Args:
        obj: Object to process

    Returns:
        Object with null values removed

    Thread-Safety:
        This function is thread-safe (pure function, no side effects).
    """
    if isinstance(obj, dict):
        return {k: _remove_nulls(v) for k, v in obj.items() if v is not None}
    elif isinstance(obj, (list, tuple)):
        return [_remove_nulls(item) for item in obj if item is not None]
    else:
        return obj
