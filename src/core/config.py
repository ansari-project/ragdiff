"""Configuration management for the RAG comparison harness."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from .models import ToolConfig

# Load environment variables
load_dotenv()


class Config:
    """Manages configuration for the comparison harness."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration.

        Args:
            config_path: Path to configuration file
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "configs" / "tools.yaml"

        self.config_path = config_path
        self._raw_config = self._load_config()
        self._process_env_vars()
        self._parse_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file.

        Returns:
            Configuration dictionary
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, "r") as f:
            return yaml.safe_load(f)

    def _process_env_vars(self) -> None:
        """Process environment variable references in config."""
        def replace_env_vars(obj):
            """Recursively replace ${ENV_VAR} with actual values."""
            if isinstance(obj, str):
                if obj.startswith("${") and obj.endswith("}"):
                    env_var = obj[2:-1]
                    value = os.getenv(env_var)
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
                base_url=tool_dict.get("base_url"),
                corpus_id=tool_dict.get("corpus_id"),
                customer_id=tool_dict.get("customer_id"),
                timeout=tool_dict.get("timeout", 30),
                max_retries=tool_dict.get("max_retries", 3),
                default_top_k=tool_dict.get("default_top_k", 5)
            )

        # Parse LLM config
        llm_config = self._raw_config.get("llm", {})
        if llm_config:
            self.llm = type('LLMConfig', (), {
                'model': llm_config.get("model"),
                'api_key_env': llm_config.get("api_key_env")
            })()
        else:
            self.llm = None

    def get_tool_config(self, tool_name: str) -> ToolConfig:
        """Get configuration for a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            ToolConfig object
        """
        if tool_name not in self._raw_config:
            raise ValueError(f"Unknown tool: {tool_name}")

        tool_dict = self._raw_config[tool_name]
        return ToolConfig(
            name=tool_dict.get("name", tool_name),
            api_key_env=tool_dict.get("api_key_env"),
            base_url=tool_dict.get("base_url"),
            corpus_id=tool_dict.get("corpus_id"),
            customer_id=tool_dict.get("customer_id"),
            timeout=tool_dict.get("timeout", 30),
            max_retries=tool_dict.get("max_retries", 3),
            default_top_k=tool_dict.get("default_top_k", 5)
        )

    def get_llm_config(self) -> Dict[str, Any]:
        """Get LLM configuration.

        Returns:
            LLM configuration dictionary
        """
        return self._raw_config.get("llm", {})

    def get_output_config(self) -> Dict[str, Any]:
        """Get output configuration.

        Returns:
            Output configuration dictionary
        """
        return self._raw_config.get("output", {})

    def get_display_config(self) -> Dict[str, Any]:
        """Get display configuration.

        Returns:
            Display configuration dictionary
        """
        return self._raw_config.get("display", {})

    def validate(self) -> None:
        """Validate the configuration.

        Raises:
            ValueError: If configuration is invalid
        """
        # Check required tools
        for tool in ["goodmem", "mawsuah"]:
            if tool not in self._raw_config:
                raise ValueError(f"Missing required tool configuration: {tool}")

            config = self.get_tool_config(tool)
            config.validate()

        # Check LLM config
        llm_config = self.get_llm_config()
        if not llm_config.get("api_key_env"):
            raise ValueError("Missing LLM API key configuration")

        if not os.getenv(llm_config["api_key_env"]):
            raise ValueError(
                f"Missing LLM API key environment variable: {llm_config['api_key_env']}"
            )