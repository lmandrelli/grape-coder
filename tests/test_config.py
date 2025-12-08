import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from grape_coder.config import (
    ProviderConfig,
    AgentConfig,
    GrapeCoderConfig,
    ProviderType,
    ConfigManager,
)


class TestProviderConfig:
    """Test ProviderConfig validation."""

    def test_valid_provider_config(self):
        """Test creating a valid provider configuration."""
        config = ProviderConfig(provider=ProviderType.OPENAI, api_key="test-key")
        assert config.provider == ProviderType.OPENAI
        assert config.api_key == "test-key"
        assert config.api_base_url is None

    def test_custom_provider_requires_base_url(self):
        """Test that custom providers require base URL."""
        with pytest.raises(
            ValueError, match="api_base_url is required for custom providers"
        ):
            ProviderConfig(provider=ProviderType.CUSTOM, api_key="test-key")

    def test_custom_provider_with_base_url(self):
        """Test custom provider with base URL."""
        config = ProviderConfig(
            provider=ProviderType.CUSTOM,
            api_key="test-key",
            api_base_url="https://api.example.com",
        )
        assert config.provider == ProviderType.CUSTOM
        assert config.api_base_url == "https://api.example.com"


class TestAgentConfig:
    """Test AgentConfig validation."""

    def test_valid_agent_config(self):
        """Test creating a valid agent configuration."""
        config = AgentConfig(provider_ref="test-provider", model_name="gpt-4o")
        assert config.provider_ref == "test-provider"
        assert config.model_name == "gpt-4o"


class TestGrapeCoderConfig:
    """Test GrapeCoderConfig validation."""

    def test_empty_config(self):
        """Test creating an empty configuration."""
        config = GrapeCoderConfig()
        assert config.providers == {}
        assert config.agents == {}

    def test_valid_config(self):
        """Test creating a valid configuration with providers and agents."""
        config = GrapeCoderConfig(
            providers={
                "openai": ProviderConfig(
                    provider=ProviderType.OPENAI, api_key="test-key"
                )
            },
            agents={"code": AgentConfig(provider_ref="openai", model_name="gpt-4o")},
        )
        assert len(config.providers) == 1
        assert len(config.agents) == 1
        assert "openai" in config.providers
        assert "code" in config.agents

    def test_agent_references_missing_provider(self):
        """Test validation when agent references missing provider."""
        with pytest.raises(ValueError, match="Agents reference non-existent providers"):
            GrapeCoderConfig(
                providers={},
                agents={
                    "code": AgentConfig(
                        provider_ref="missing-provider", model_name="gpt-4o"
                    )
                },
            )


class TestConfigManager:
    """Test ConfigManager functionality."""

    def test_init_creates_config_directory(self):
        """Test that initialization creates config directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("platformdirs.user_config_dir", return_value=temp_dir):
                manager = ConfigManager()
                config_dir = Path(temp_dir)
                assert config_dir.exists()
                assert config_dir.is_dir()

    def test_load_empty_config(self):
        """Test loading configuration when no file exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("platformdirs.user_config_dir", return_value=temp_dir):
                manager = ConfigManager()
                config = manager.load_config()
                assert isinstance(config, GrapeCoderConfig)
                assert config.providers == {}
                assert config.agents == {}

    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("platformdirs.user_config_dir", return_value=temp_dir):
                manager = ConfigManager()

                # Create test configuration
                config = GrapeCoderConfig(
                    providers={
                        "openai": ProviderConfig(
                            provider=ProviderType.OPENAI, api_key="test-key"
                        )
                    },
                    agents={
                        "code": AgentConfig(provider_ref="openai", model_name="gpt-4o")
                    },
                )

                # Save configuration
                manager.save_config(config)

                # Load configuration
                loaded_config = manager.load_config()

                assert loaded_config.providers == config.providers
                assert loaded_config.agents == config.agents

    def test_config_exists(self):
        """Test checking if configuration file exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("platformdirs.user_config_dir", return_value=temp_dir):
                manager = ConfigManager()

                # Should not exist initially
                assert not manager.config_exists()

                # Save configuration
                config = GrapeCoderConfig()
                manager.save_config(config)

                # Should exist now
                assert manager.config_exists()

    def test_invalid_json_handling(self):
        """Test handling of invalid JSON in configuration file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("platformdirs.user_config_dir", return_value=temp_dir):
                manager = ConfigManager()

                # Write invalid JSON
                config_file = manager._config_file
                config_file.write_text("{ invalid json }")

                # Should raise ValueError
                with pytest.raises(ValueError, match="Invalid JSON"):
                    manager.load_config()

    def test_cache_invalidation(self):
        """Test that cache is invalidated when file changes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("platformdirs.user_config_dir", return_value=temp_dir):
                manager = ConfigManager()

                # Load initial config
                config1 = manager.load_config()

                # Save new config
                config2 = GrapeCoderConfig(
                    providers={
                        "openai": ProviderConfig(
                            provider=ProviderType.OPENAI, api_key="test-key"
                        )
                    }
                )
                manager.save_config(config2)

                # Load again - should get updated config
                config3 = manager.load_config()
                assert config3.providers == config2.providers
                assert config3.providers != config1.providers
