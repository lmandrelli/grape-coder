import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from grape_coder.agents.identifiers import AgentIdentifier
from grape_coder.config import (
    AgentConfig,
    ConfigManager,
    GrapeCoderConfig,
    ProviderConfig,
    ProviderType,
)


class TestProviderConfig:
    """Test ProviderConfig validation."""

    def test_valid_provider_config(self):
        """Test creating a valid provider configuration."""
        config = ProviderConfig(
            provider=ProviderType.OPENAI, api_key="test-key", api_base_url=None
        )
        assert config.provider == ProviderType.OPENAI
        assert config.api_key == "test-key"
        assert config.api_base_url is None

    def test_custom_provider_requires_base_url(self):
        """Test that custom providers require base URL."""
        with pytest.raises(
            ValueError, match="api_base_url is required for custom providers"
        ):
            ProviderConfig(
                provider=ProviderType.CUSTOM, api_key="test-key", api_base_url=None
            )

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
                    provider=ProviderType.OPENAI, api_key="test-key", api_base_url=None
                )
            },
            agents={
                AgentIdentifier.CODE: AgentConfig(
                    provider_ref="openai", model_name="gpt-4o"
                )
            },
        )
        assert len(config.providers) == 1
        assert len(config.agents) == 1
        assert "openai" in config.providers
        assert AgentIdentifier.CODE in config.agents

    def test_agent_references_missing_provider(self):
        """Test validation when agent references missing provider."""
        with pytest.raises(ValueError, match="Agents reference non-existent providers"):
            GrapeCoderConfig(
                providers={},
                agents={
                    AgentIdentifier.CODE: AgentConfig(
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
                _ = ConfigManager()
                config_dir = Path(temp_dir)
                assert config_dir.exists()
                assert config_dir.is_dir()

    def test_load_empty_config(self):
        """Test loading configuration when no file exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("platformdirs.user_config_dir", return_value=temp_dir):
                manager = ConfigManager()
                config_result = manager._load_config_from_file()
                config, dropped_items = config_result
                assert isinstance(config, GrapeCoderConfig)
                assert config.providers == {}
                assert config.agents == {}
                assert dropped_items == {
                    "malformed_providers": [],
                    "malformed_agents": [],
                    "unrecognized_agents": [],
                    "orphaned_agents": [],
                }

    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("platformdirs.user_config_dir", return_value=temp_dir):
                manager = ConfigManager()

                # Create test configuration
                config = GrapeCoderConfig(
                    providers={
                        "openai": ProviderConfig(
                            provider=ProviderType.OPENAI,
                            api_key="test-key",
                            api_base_url=None,
                        )
                    },
                    agents={
                        AgentIdentifier.CODE: AgentConfig(
                            provider_ref="openai", model_name="gpt-4o"
                        )
                    },
                )

                # Save configuration
                manager.save_config(config)

                # Load configuration
                config_result = manager._load_config_from_file()
                loaded_config, dropped_items = config_result

                assert loaded_config.providers == config.providers
                assert loaded_config.agents == config.agents
                assert dropped_items == {
                    "malformed_providers": [],
                    "malformed_agents": [],
                    "unrecognized_agents": [],
                    "orphaned_agents": [],
                }

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

                # Should return empty config and dropped items (graceful handling)
                config_result = manager._load_config_from_file()
                config, dropped_items = config_result

                assert isinstance(config, GrapeCoderConfig)
                assert config.providers == {}
                assert config.agents == {}
                assert dropped_items == {
                    "malformed_providers": [],
                    "malformed_agents": [],
                    "unrecognized_agents": [],
                    "orphaned_agents": [],
                }

    def test_cache_invalidation(self):
        """Test that cache is invalidated when file changes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("platformdirs.user_config_dir", return_value=temp_dir):
                manager = ConfigManager()

                # Load initial config
                config_result1 = manager._load_config_from_file()
                config1, _ = config_result1

                # Save new config
                config2 = GrapeCoderConfig(
                    providers={
                        "openai": ProviderConfig(
                            provider=ProviderType.OPENAI,
                            api_key="test-key",
                            api_base_url=None,
                        )
                    }
                )
                manager.save_config(config2)

                # Load again - should get updated config
                config_result3 = manager._load_config_from_file()
                config3, _ = config_result3
                assert config3.providers == config2.providers
                assert config3.providers != config1.providers

    def test_get_model_success(self):
        """Test successful model retrieval."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("platformdirs.user_config_dir", return_value=temp_dir):
                manager = ConfigManager()

                # Create test configuration
                config = GrapeCoderConfig(
                    providers={
                        "openai": ProviderConfig(
                            provider=ProviderType.OPENAI,
                            api_key="test-key",
                            api_base_url=None,
                        )
                    },
                    agents={
                        AgentIdentifier.CODE: AgentConfig(
                            provider_ref="openai", model_name="gpt-4o"
                        )
                    },
                )
                manager.save_config(config)

                # Mock the create_litellm_model function
                with patch(
                    "grape_coder.config.manager.create_litellm_model"
                ) as mock_create:
                    mock_model = "mock_model"
                    mock_create.return_value = mock_model

                    # Get model
                    model = manager.get_model(AgentIdentifier.CODE)

                    # Verify model creation was called correctly
                    mock_create.assert_called_once_with(
                        config.providers["openai"],
                        config.agents[AgentIdentifier.CODE].model_name,
                    )
                    assert model == mock_model

    def test_get_model_caching(self):
        """Test that models are cached."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("platformdirs.user_config_dir", return_value=temp_dir):
                manager = ConfigManager()

                # Create test configuration
                config = GrapeCoderConfig(
                    providers={
                        "openai": ProviderConfig(
                            provider=ProviderType.OPENAI,
                            api_key="test-key",
                            api_base_url=None,
                        )
                    },
                    agents={
                        AgentIdentifier.CODE: AgentConfig(
                            provider_ref="openai", model_name="gpt-4o"
                        )
                    },
                )
                manager.save_config(config)

                # Mock the create_litellm_model function
                with patch(
                    "grape_coder.config.manager.create_litellm_model"
                ) as mock_create:
                    mock_model = "mock_model"
                    mock_create.return_value = mock_model

                    # Get model twice
                    model1 = manager.get_model(AgentIdentifier.CODE)
                    model2 = manager.get_model(AgentIdentifier.CODE)

                    # Should only create model once (cached)
                    mock_create.assert_called_once()
                    assert model1 == mock_model
                    assert model2 == mock_model

    def test_get_model_no_agents_configured(self):
        """Test get_model when no agents are configured."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("platformdirs.user_config_dir", return_value=temp_dir):
                manager = ConfigManager()

                # Save empty config
                manager.save_config(GrapeCoderConfig())

                # Should raise ValueError
                with pytest.raises(ValueError, match="No agents configured"):
                    manager.get_model(AgentIdentifier.CODE)

    def test_get_model_agent_not_found(self):
        """Test get_model when agent is not found."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("platformdirs.user_config_dir", return_value=temp_dir):
                manager = ConfigManager()

                # Create test configuration with different agent
                config = GrapeCoderConfig(
                    providers={
                        "openai": ProviderConfig(
                            provider=ProviderType.OPENAI,
                            api_key="test-key",
                            api_base_url=None,
                        )
                    },
                    agents={
                        "other_agent": AgentConfig(
                            provider_ref="openai", model_name="gpt-4o"
                        )
                    },
                )
                manager.save_config(config)

                # Should raise ValueError
                with pytest.raises(
                    ValueError, match=f"Agent '{AgentIdentifier.CODE}' not found"
                ):
                    manager.get_model(AgentIdentifier.CODE)

    def test_get_model_creation_failure(self):
        """Test get_model when model creation fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("platformdirs.user_config_dir", return_value=temp_dir):
                manager = ConfigManager()

                # Create test configuration
                config = GrapeCoderConfig(
                    providers={
                        "openai": ProviderConfig(
                            provider=ProviderType.OPENAI,
                            api_key="test-key",
                            api_base_url=None,
                        )
                    },
                    agents={
                        AgentIdentifier.CODE: AgentConfig(
                            provider_ref="openai", model_name="gpt-4o"
                        )
                    },
                )
                manager.save_config(config)

                # Mock the create_litellm_model function to raise exception
                with patch(
                    "grape_coder.config.manager.create_litellm_model"
                ) as mock_create:
                    mock_create.side_effect = Exception("Model creation failed")

                    # Should raise RuntimeError
                    with pytest.raises(RuntimeError, match="Failed to create model"):
                        manager.get_model(AgentIdentifier.CODE)

    def test_clear_cache_clears_model_cache(self):
        """Test that clear_cache also clears the model cache."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("platformdirs.user_config_dir", return_value=temp_dir):
                manager = ConfigManager()

                # Create test configuration
                config = GrapeCoderConfig(
                    providers={
                        "openai": ProviderConfig(
                            provider=ProviderType.OPENAI,
                            api_key="test-key",
                            api_base_url=None,
                        )
                    },
                    agents={
                        AgentIdentifier.CODE: AgentConfig(
                            provider_ref="openai", model_name="gpt-4o"
                        )
                    },
                )
                manager.save_config(config)

                # Mock the create_litellm_model function
                with patch(
                    "grape_coder.config.manager.create_litellm_model"
                ) as mock_create:
                    mock_model = "mock_model"
                    mock_create.return_value = mock_model

                    # Get model to populate cache
                    manager.get_model(AgentIdentifier.CODE)
                    assert len(manager._model_cache) == 1

                    # Clear cache
                    manager.clear_cache()

                    # Model cache should be empty
                    assert len(manager._model_cache) == 0
