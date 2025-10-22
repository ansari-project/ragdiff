"""Tests for multi-tenant credential support."""

import os
from pathlib import Path

import pytest

from ragdiff import load_config
from ragdiff.core.config import Config


class TestConfigCredentials:
    """Test Config class with credentials dict."""

    def test_config_with_credentials_dict(self):
        """Test Config accepts credentials dict."""
        config_dict = {
            "tools": {
                "vectara": {
                    "api_key_env": "VECTARA_API_KEY",
                    "corpus_id": "test_corpus",
                }
            }
        }

        config = Config(
            config_dict=config_dict, credentials={"VECTARA_API_KEY": "test_key_123"}
        )

        # Credential should be available via _get_env_value
        assert config._get_env_value("VECTARA_API_KEY") == "test_key_123"

    def test_credentials_precedence_over_environment(self):
        """Test credentials dict takes precedence over environment."""
        # Set environment variable
        os.environ["TEST_API_KEY"] = "env_value"

        try:
            config_dict = {
                "tools": {
                    "test_tool": {"api_key_env": "TEST_API_KEY", "corpus_id": "test"}
                }
            }

            # Pass different value in credentials
            config = Config(
                config_dict=config_dict, credentials={"TEST_API_KEY": "cred_value"}
            )

            # Credentials should win
            assert config._get_env_value("TEST_API_KEY") == "cred_value"
        finally:
            # Cleanup
            del os.environ["TEST_API_KEY"]

    def test_env_var_substitution_with_credentials(self):
        """Test ${ENV_VAR} substitution uses credentials."""
        config_dict = {
            "tools": {
                "vectara": {
                    "api_key_env": "VECTARA_API_KEY",
                    "corpus_id": "${CORPUS_ID}",  # Will be substituted
                }
            }
        }

        config = Config(
            config_dict=config_dict,
            credentials={"VECTARA_API_KEY": "key123", "CORPUS_ID": "my_corpus"},
        )

        # corpus_id should be substituted from credentials
        assert config.tools["vectara"].corpus_id == "my_corpus"

    def test_validation_with_missing_credentials(self):
        """Test validation fails when credentials missing."""
        config_dict = {
            "tools": {"vectara": {"api_key_env": "MISSING_KEY", "corpus_id": "test"}}
        }

        config = Config(config_dict=config_dict)

        with pytest.raises(
            ValueError, match="Missing required environment variable: MISSING_KEY"
        ):
            config.validate()

    def test_config_path_and_dict_mutual_exclusion(self):
        """Test can't provide both path and dict."""
        with pytest.raises(
            ValueError, match="Provide either config_path or config_dict"
        ):
            Config(config_path=Path("config.yaml"), config_dict={"tools": {}})

    def test_config_from_dict_no_path(self):
        """Test config from dict doesn't require path."""
        config_dict = {
            "tools": {
                "vectara": {"api_key_env": "VECTARA_API_KEY", "corpus_id": "test"}
            }
        }

        config = Config(config_dict=config_dict, credentials={"VECTARA_API_KEY": "key"})

        assert config.config_path is None
        assert "vectara" in config.tools


class TestLoadConfig:
    """Test load_config() function."""

    def test_load_config_with_dict_and_credentials(self):
        """Test load_config accepts dict and credentials."""
        config_dict = {
            "tools": {
                "vectara": {"api_key_env": "VECTARA_API_KEY", "corpus_id": "test"}
            }
        }

        config = load_config(config_dict, credentials={"VECTARA_API_KEY": "key"})

        assert isinstance(config, Config)
        assert config._credentials["VECTARA_API_KEY"] == "key"
        assert "vectara" in config.tools

    def test_load_config_with_file_and_credentials(self, tmp_path):
        """Test load_config accepts file path and credentials."""
        # Create temp config file
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
tools:
  vectara:
    api_key_env: VECTARA_API_KEY
    corpus_id: test_corpus
"""
        )

        config = load_config(str(config_file), credentials={"VECTARA_API_KEY": "key"})

        assert isinstance(config, Config)
        assert config._credentials["VECTARA_API_KEY"] == "key"
        assert config.config_path == config_file


class TestMultiTenantIsolation:
    """Test multi-tenant credential isolation."""

    def test_different_configs_have_isolated_credentials(self):
        """Test different configs have isolated credentials."""
        config_dict = {
            "tools": {
                "vectara": {"api_key_env": "VECTARA_API_KEY", "corpus_id": "test"}
            }
        }

        config_a = load_config(
            config_dict, credentials={"VECTARA_API_KEY": "tenant_a_key"}
        )

        config_b = load_config(
            config_dict, credentials={"VECTARA_API_KEY": "tenant_b_key"}
        )

        # Configs should have different credentials
        assert config_a._credentials != config_b._credentials
        assert config_a._get_env_value("VECTARA_API_KEY") == "tenant_a_key"
        assert config_b._get_env_value("VECTARA_API_KEY") == "tenant_b_key"

    def test_credentials_dont_pollute_environment(self):
        """Test passed credentials don't modify os.environ."""
        config_dict = {
            "tools": {
                "vectara": {"api_key_env": "UNIQUE_TEST_KEY", "corpus_id": "test"}
            }
        }

        # Ensure key doesn't exist in environment
        assert "UNIQUE_TEST_KEY" not in os.environ

        config = load_config(config_dict, credentials={"UNIQUE_TEST_KEY": "test_value"})

        # Key should still not be in environment
        assert "UNIQUE_TEST_KEY" not in os.environ
        # But should be available via config
        assert config._get_env_value("UNIQUE_TEST_KEY") == "test_value"


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_config_without_credentials_works(self, tmp_path):
        """Test Config works without credentials (backward compat)."""
        # Set environment variable
        os.environ["TEST_VECTARA_KEY"] = "env_key"

        try:
            config_file = tmp_path / "config.yaml"
            config_file.write_text(
                """
tools:
  vectara:
    api_key_env: TEST_VECTARA_KEY
    corpus_id: test
"""
            )

            # Old usage - no credentials parameter
            config = Config(config_path=config_file)
            config.validate()  # Should succeed using environment

            assert config._get_env_value("TEST_VECTARA_KEY") == "env_key"
        finally:
            del os.environ["TEST_VECTARA_KEY"]

    def test_load_config_without_credentials(self, tmp_path):
        """Test load_config works without credentials (backward compat)."""
        os.environ["TEST_KEY"] = "env_value"

        try:
            config_file = tmp_path / "config.yaml"
            config_file.write_text(
                """
tools:
  vectara:
    api_key_env: TEST_KEY
    corpus_id: test
"""
            )

            # Old usage
            config = load_config(str(config_file))

            assert config._get_env_value("TEST_KEY") == "env_value"
        finally:
            del os.environ["TEST_KEY"]


class TestCredentialResolution:
    """Test credential resolution order."""

    def test_resolution_order(self):
        """Test credentials > environment > None."""
        # Set environment
        os.environ["RESOLUTION_TEST_KEY"] = "env_value"

        try:
            config_dict = {
                "tools": {
                    "test": {"api_key_env": "RESOLUTION_TEST_KEY", "corpus_id": "test"}
                }
            }

            # With credentials - should use credentials
            config_with_creds = Config(
                config_dict=config_dict,
                credentials={"RESOLUTION_TEST_KEY": "cred_value"},
            )
            assert (
                config_with_creds._get_env_value("RESOLUTION_TEST_KEY") == "cred_value"
            )

            # Without credentials - should use environment
            config_without_creds = Config(config_dict=config_dict)
            assert (
                config_without_creds._get_env_value("RESOLUTION_TEST_KEY")
                == "env_value"
            )

            # Missing from both - should return None
            assert config_without_creds._get_env_value("NONEXISTENT_KEY") is None
        finally:
            del os.environ["RESOLUTION_TEST_KEY"]

    def test_partial_credentials(self):
        """Test some credentials from dict, some from environment."""
        os.environ["ENV_KEY"] = "from_env"

        try:
            config_dict = {
                "tools": {
                    "vectara": {
                        "api_key_env": "VECTARA_KEY",
                        "corpus_id": "${CORPUS_ID}",
                    }
                }
            }

            # Provide VECTARA_KEY in credentials, CORPUS_ID from env
            config = Config(
                config_dict=config_dict,
                credentials={"VECTARA_KEY": "from_creds", "CORPUS_ID": "creds_corpus"},
            )

            assert config._get_env_value("VECTARA_KEY") == "from_creds"
            assert config.tools["vectara"].corpus_id == "creds_corpus"
        finally:
            if "ENV_KEY" in os.environ:
                del os.environ["ENV_KEY"]
