"""Tests for space_ids configuration in Goodmem adapter."""

from pathlib import Path
from unittest.mock import Mock, patch

from ragdiff.adapters.goodmem import GoodmemAdapter
from ragdiff.core.config import Config
from ragdiff.core.models import ToolConfig


class TestSpaceIdsConfiguration:
    """Test that space_ids are properly configured and used."""

    def test_config_loads_space_ids_from_yaml(self):
        """Test that Config loads space_ids from YAML file."""
        # Load tafsir config
        config = Config(Path("configs/tafsir.yaml"))
        goodmem_config = config.tools["goodmem"]

        # Should have 2 spaces for tafsir
        assert goodmem_config.space_ids is not None
        assert len(goodmem_config.space_ids) == 2
        assert (
            "efd91f05-87cf-4c4c-a04d-0a970f8d30a7" in goodmem_config.space_ids
        )  # Ibn Katheer
        assert (
            "d04d8032-3a9b-4b83-b906-e48458715a7a" in goodmem_config.space_ids
        )  # Qurtubi

    def test_mawsuah_config_loads_single_space(self):
        """Test that mawsuah config loads single space."""
        config = Config(Path("configs/mawsuah.yaml"))
        goodmem_config = config.tools["goodmem"]

        # Should have 1 space for mawsuah
        assert goodmem_config.space_ids is not None
        assert len(goodmem_config.space_ids) == 1
        assert (
            "2d1f3227-8331-46ee-9dc2-d9265bfc79f5" in goodmem_config.space_ids
        )  # Mawsuah

    @patch("src.adapters.goodmem.GOODMEM_AVAILABLE", False)
    def test_goodmem_adapter_uses_config_space_ids(self):
        """Test that GoodmemAdapter uses space_ids from config."""
        # Create config with custom space_ids
        config = ToolConfig(
            name="goodmem",
            api_key_env="GOODMEM_API_KEY",
            space_ids=["space-1", "space-2"],
        )

        # Create adapter
        adapter = GoodmemAdapter(config)

        # Should use config space_ids
        assert adapter.space_ids == ["space-1", "space-2"]

    @patch("src.adapters.goodmem.GOODMEM_AVAILABLE", False)
    def test_goodmem_adapter_falls_back_to_defaults(self):
        """Test that adapter falls back to default space_ids if not configured."""
        # Create config without space_ids
        config = ToolConfig(
            name="goodmem", api_key_env="GOODMEM_API_KEY", space_ids=None
        )

        # Create adapter
        adapter = GoodmemAdapter(config)

        # Should use default space_ids
        assert adapter.space_ids is not None
        assert len(adapter.space_ids) == 3  # Default has all 3 spaces

    @patch("src.adapters.goodmem.GOODMEM_AVAILABLE", False)
    def test_goodmem_adapter_respects_config_space_ids(self):
        """Test that adapter uses space_ids from config even in mock mode."""
        # Create config with specific spaces
        config = ToolConfig(
            name="goodmem",
            api_key_env="GOODMEM_API_KEY",
            base_url="http://test.com",
            space_ids=["test-space-1", "test-space-2"],
        )

        # Create adapter (will be in mock mode)
        adapter = GoodmemAdapter(config)

        # Verify space_ids were set correctly from config
        assert adapter.space_ids == ["test-space-1", "test-space-2"]

    def test_tool_config_space_ids_field_exists(self):
        """Test that ToolConfig has space_ids field."""
        config = ToolConfig(
            name="test", api_key_env="TEST_KEY", space_ids=["space-1", "space-2"]
        )

        assert hasattr(config, "space_ids")
        assert config.space_ids == ["space-1", "space-2"]

    def test_tool_config_space_ids_optional(self):
        """Test that space_ids is optional in ToolConfig."""
        config = ToolConfig(name="test", api_key_env="TEST_KEY")

        assert hasattr(config, "space_ids")
        assert config.space_ids is None


class TestGoodmemSpaceQuerying:
    """Test that Goodmem adapter queries the correct spaces."""

    @patch("src.adapters.goodmem.GOODMEM_AVAILABLE", False)
    @patch("src.adapters.goodmem.subprocess.run")
    def test_cli_queries_all_configured_spaces(self, mock_run):
        """Test that CLI fallback queries all configured spaces."""
        # Mock subprocess response
        mock_run.return_value = Mock(returncode=0, stdout='{"retrieved": []}')

        # Create adapter with 2 spaces
        config = ToolConfig(
            name="goodmem",
            api_key_env="GOODMEM_API_KEY",
            space_ids=["space-1", "space-2"],
        )

        with patch.dict("os.environ", {"GOODMEM_API_KEY": "test-key"}):
            adapter = GoodmemAdapter(config)
            adapter.search("test query", top_k=5)

            # Should have called subprocess twice (once per space)
            assert mock_run.call_count == 2

            # Verify both spaces were queried
            calls = mock_run.call_args_list
            assert "space-1" in str(calls[0])
            assert "space-2" in str(calls[1])

    @patch("src.adapters.goodmem.GOODMEM_AVAILABLE", False)
    def test_adapter_uses_all_configured_spaces_for_search(self):
        """Test that adapter is configured to search all spaces."""
        # Create adapter with 2 spaces
        config = ToolConfig(
            name="goodmem",
            api_key_env="GOODMEM_API_KEY",
            base_url="http://test.com",
            space_ids=["space-1", "space-2"],
        )

        with patch.dict("os.environ", {"GOODMEM_API_KEY": "test-key"}):
            adapter = GoodmemAdapter(config)

            # Verify adapter has the right spaces configured
            assert adapter.space_ids == ["space-1", "space-2"]
            # In production, _search_via_streaming would loop through these spaces
            # but we can't easily test that without mocking the entire HTTP stack
