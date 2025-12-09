from unittest.mock import MagicMock, patch

from grape_coder.config import (
    LiteLLMModel,
    ProviderConfig,
    ProviderFactory,
    ProviderType,
)


class TestProviderFactory:
    """Test ProviderFactory functionality."""

    def test_get_suggested_models(self):
        """Test getting suggested models for each provider type."""
        # Test OpenAI suggestions
        openai_models = ProviderFactory.get_suggested_models(ProviderType.OPENAI)
        assert "gpt-5.1" in openai_models

        # Test Anthropic suggestions
        anthropic_models = ProviderFactory.get_suggested_models(ProviderType.ANTHROPIC)
        assert any("claude" in model for model in anthropic_models)

        # Test Mistral suggestions
        mistral_models = ProviderFactory.get_suggested_models(ProviderType.MISTRAL)
        assert "mistral-large-latest" in mistral_models

    def test_validate_model_format(self):
        """Test model name format validation."""
        # Valid formats
        assert ProviderFactory.validate_model_format(ProviderType.OPENAI, "gpt-4o")
        assert ProviderFactory.validate_model_format(ProviderType.CUSTOM, "any-model")

        # Invalid formats
        assert not ProviderFactory.validate_model_format(ProviderType.OPENAI, "")
        assert not ProviderFactory.validate_model_format(
            ProviderType.OPENAI, "model with spaces"
        )
        assert not ProviderFactory.validate_model_format(
            ProviderType.OPENAI, "a" * 101
        )  # Too long

    @patch("grape_coder.config.litellm_integration.StrandsLiteLLMModel")
    def test_create_model(self, mock_strands_model):
        """Test creating a model instance."""
        mock_model_instance = MagicMock()
        mock_strands_model.return_value = mock_model_instance

        provider_config = ProviderConfig(
            provider=ProviderType.OPENAI, api_key="test-key", api_base_url=None
        )

        model = ProviderFactory.create_model(provider_config, "gpt-4o")

        assert isinstance(model, LiteLLMModel)
        assert model.provider_config == provider_config
        assert model.model_name == "gpt-4o"


class TestLiteLLMModel:
    """Test LiteLLMModel functionality."""

    @patch("grape_coder.config.litellm_integration.StrandsLiteLLMModel")
    def test_model_creation(self, mock_strands_model):
        """Test model creation with provider config."""
        mock_model_instance = MagicMock()
        mock_strands_model.return_value = mock_model_instance

        provider_config = ProviderConfig(
            provider=ProviderType.OPENAI, api_key="test-key", api_base_url=None
        )

        _ = LiteLLMModel(provider_config, "gpt-4o")

        # Verify the underlying model was created correctly
        mock_strands_model.assert_called_once_with(
            model_id="openai/gpt-4o", client_args={"api_key": "test-key"}
        )

    @patch("grape_coder.config.litellm_integration.StrandsLiteLLMModel")
    def test_custom_provider_model_id(self, mock_strands_model):
        """Test LiteLLM model ID generation for custom providers."""
        mock_model_instance = MagicMock()
        mock_strands_model.return_value = mock_model_instance

        provider_config = ProviderConfig(
            provider=ProviderType.CUSTOM,
            api_key="test-key",
            api_base_url="https://api.example.com",
        )

        _ = LiteLLMModel(provider_config, "custom-model")

        # Verify the model ID is prefixed with openai/ for custom providers
        mock_strands_model.assert_called_once_with(
            model_id="openai/custom-model",
            client_args={"api_key": "test-key", "api_base": "https://api.example.com"},
        )

    @patch("grape_coder.config.litellm_integration.StrandsLiteLLMModel")
    def test_model_delegation(self, mock_strands_model):
        """Test that model calls are delegated to underlying strands model."""
        mock_model_instance = MagicMock()
        mock_strands_model.return_value = mock_model_instance

        provider_config = ProviderConfig(
            provider=ProviderType.OPENAI, api_key="test-key", api_base_url=None
        )

        model = LiteLLMModel(provider_config, "gpt-4o")

        # Test attribute delegation
        mock_model_instance.some_method.return_value = "test result"
        assert model.some_method() == "test result"
        mock_model_instance.some_method.assert_called_once()

    @patch("grape_coder.config.litellm_integration.StrandsLiteLLMModel")
    def test_model_id_property(self, mock_strands_model):
        """Test model_id property."""
        mock_model_instance = MagicMock()
        mock_strands_model.return_value = mock_model_instance

        provider_config = ProviderConfig(
            provider=ProviderType.OPENAI, api_key="test-key", api_base_url=None
        )

        model = LiteLLMModel(provider_config, "gpt-4o")
        assert model.model_id == "openai/gpt-4o"

        # Test custom provider
        custom_config = ProviderConfig(
            provider=ProviderType.CUSTOM,
            api_key="test-key",
            api_base_url="https://api.example.com",
        )
        custom_model = LiteLLMModel(custom_config, "custom-model")
        assert custom_model.model_id == "openai/custom-model"

        # Test that model names already prefixed with openai/ are double-prefixed (litellm wants it that way)
        already_prefixed_model = LiteLLMModel(custom_config, "openai/gpt-4o")
        assert already_prefixed_model.model_id == "openai/openai/gpt-4o"
