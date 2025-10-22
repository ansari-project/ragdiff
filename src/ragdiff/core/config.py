"""Configuration management for the RAG comparison harness."""

import logging
import os
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv

from .models import ToolConfig

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class Config:
    """Manages configuration for the comparison harness.

    Supports multi-tenant usage by accepting credentials dict that takes
    precedence over environment variables.
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        config_dict: Optional[dict] = None,
        credentials: Optional[dict[str, str]] = None,
    ):
        """Initialize configuration.

        Args:
            config_path: Path to configuration file
            config_dict: Configuration dictionary (alternative to file)
            credentials: Optional credential overrides (env var name -> value)
                Takes precedence over environment variables.

        Raises:
            ValueError: If both config_path and config_dict provided, or neither

        Example:
            # From file with environment variables
            config = Config(config_path=Path("config.yaml"))

            # From file with explicit credentials
            config = Config(
                config_path=Path("config.yaml"),
                credentials={"VECTARA_API_KEY": "sk_abc123"}
            )

            # From dict
            config = Config(
                config_dict={"tools": {...}},
                credentials={"VECTARA_API_KEY": "sk_abc123"}
            )
        """
        # Validation: exactly one source
        if config_path and config_dict:
            raise ValueError("Provide either config_path or config_dict, not both")
        if not config_path and not config_dict:
            # Default to standard location if neither provided
            config_path = Path(__file__).parent.parent.parent / "configs" / "tools.yaml"

        self.config_path = config_path
        self._credentials = credentials or {}

        # Load from file or use provided dict
        if config_path:
            self._raw_config = self._load_config()
        else:
            self._raw_config = config_dict

        self._process_env_vars()
        self._parse_config()

    def _load_config(self) -> dict[str, Any]:
        """Load configuration from YAML file.

        Returns:
            Configuration dictionary
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path) as f:
            config = yaml.safe_load(f)
            return config if isinstance(config, dict) else {}

    def _get_env_value(self, env_var_name: str) -> Optional[str]:
        """Get environment value from credentials or environment.

        Credentials dict takes precedence over environment variables.

        Args:
            env_var_name: Name of environment variable

        Returns:
            Value from credentials dict, environment, or None

        Resolution order:
            1. Passed credentials dict (highest priority)
            2. Process environment variables
            3. .env file (via load_dotenv)
            4. None (will cause error during validation)
        """
        # Check passed credentials first
        if env_var_name in self._credentials:
            return self._credentials[env_var_name]

        # Fall back to environment
        return os.getenv(env_var_name)

    def _process_env_vars(self) -> None:
        """Process environment variable references in config.

        Uses credential resolution to support multi-tenant usage.
        """

        def replace_env_vars(obj):
            """Recursively replace ${ENV_VAR} with actual values."""
            if isinstance(obj, str):
                if obj.startswith("${") and obj.endswith("}"):
                    env_var = obj[2:-1]
                    # Use _get_env_value instead of os.getenv
                    value = self._get_env_value(env_var)
                    if value is None:
                        # Keep the placeholder if env var not set
                        return obj
                    return value
                return obj
            elif isinstance(obj, dict):
                return {k: replace_env_vars(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_env_vars(item) for item in obj]
            return obj

        self._raw_config = replace_env_vars(self._raw_config)

    def _parse_config(self) -> None:
        """Parse configuration into structured objects."""
        # Parse tool configs
        self.tools = {}
        tools_config = self._raw_config.get("tools", {})
        for tool_name, tool_dict in tools_config.items():
            self.tools[tool_name] = ToolConfig(
                name=tool_name,
                api_key_env=tool_dict.get("api_key_env"),
                adapter=tool_dict.get(
                    "adapter"
                ),  # Optional: which adapter class to use
                options=tool_dict.get("options"),  # Optional: custom adapter options
                base_url=tool_dict.get("base_url"),
                corpus_id=tool_dict.get("corpus_id"),
                customer_id=tool_dict.get("customer_id"),
                namespace_id_env=tool_dict.get("namespace_id_env"),
                timeout=tool_dict.get("timeout", 30),
                max_retries=tool_dict.get("max_retries", 3),
                default_top_k=tool_dict.get("default_top_k", 5),
                space_ids=tool_dict.get("space_ids"),
            )

        # Parse LLM config
        llm_config = self._raw_config.get("llm", {})
        if llm_config:
            self.llm = type(
                "LLMConfig",
                (),
                {
                    "model": llm_config.get("model"),
                    "api_key_env": llm_config.get("api_key_env"),
                },
            )()
        else:
            self.llm = None

    def get_tool_config(self, tool_name: str) -> ToolConfig:
        """Get configuration for a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            ToolConfig object
        """
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        return self.tools[tool_name]

    def get_llm_config(self) -> dict[str, Any]:
        """Get LLM configuration.

        Returns:
            LLM configuration dictionary
        """
        result = self._raw_config.get("llm", {})
        return result if isinstance(result, dict) else {}

    def get_output_config(self) -> dict[str, Any]:
        """Get output configuration.

        Returns:
            Output configuration dictionary
        """
        result = self._raw_config.get("output", {})
        return result if isinstance(result, dict) else {}

    def get_display_config(self) -> dict[str, Any]:
        """Get display configuration.

        Returns:
            Display configuration dictionary
        """
        result = self._raw_config.get("display", {})
        return result if isinstance(result, dict) else {}

    def validate(self) -> None:
        """Validate the configuration.

        Validates that all required credentials are available from either
        the credentials dict or environment variables.

        Raises:
            ValueError: If configuration is invalid
        """
        # Check that at least one tool is configured
        if not self.tools:
            raise ValueError("No tools configured")

        # Validate each configured tool
        for _tool_name, config in self.tools.items():
            # Check API key is set in environment OR credentials
            if not self._get_env_value(config.api_key_env):
                raise ValueError(
                    f"Missing required environment variable: {config.api_key_env}. "
                    f"Set it in environment or pass via credentials parameter."
                )

        # Check LLM config if present (optional)
        llm_config = self.get_llm_config()
        if llm_config and llm_config.get("api_key_env"):
            if not self._get_env_value(llm_config["api_key_env"]):
                logger.warning(
                    f"LLM evaluation configured but API key not set: {llm_config['api_key_env']}"
                )
