"""Logging configuration for RAGDiff v2.0.

This module provides centralized logging configuration for the entire application.
Logs are written to both console and file, with configurable levels.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

# Default log level
DEFAULT_LEVEL = logging.INFO

# Log format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(
    level: int = DEFAULT_LEVEL,
    log_file: Optional[Path] = None,
    console: bool = True,
) -> None:
    """Configure logging for RAGDiff.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file. If None, only console logging is enabled.
        console: Whether to log to console (default: True)

    Example:
        # Simple console logging
        configure_logging(level=logging.INFO)

        # Console + file logging
        configure_logging(
            level=logging.DEBUG,
            log_file=Path("ragdiff.log")
        )

        # File-only logging
        configure_logging(
            level=logging.INFO,
            log_file=Path("ragdiff.log"),
            console=False
        )
    """
    # Get root logger
    logger = logging.getLogger("ragdiff")
    logger.setLevel(level)

    # Remove existing handlers
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # Add console handler if requested
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Add file handler if log file specified
    if log_file:
        # Create parent directory if it doesn't exist
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Prevent propagation to root logger (avoid duplicate logs)
    logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific module.

    Args:
        name: Name of the module (e.g., "ragdiff.loader")

    Returns:
        Logger instance

    Example:
        logger = get_logger(__name__)
        logger.info("Loading domain...")
        logger.debug("Query set has %d queries", len(queries))
    """
    return logging.getLogger(name)


# Configure default logging on module import
configure_logging()
