from strands.models.litellm import LiteLLMModel as StrandsLiteLLMModel

from .models import ProviderConfig, ProviderType


def create_litellm_model(
    provider_config: ProviderConfig, model_name: str
) -> StrandsLiteLLMModel:
    """Create a LiteLLM model instance from provider configuration."""

    # Create client args with API key and base URL
    client_args = {"api_key": provider_config.api_key}

    # Add base URL for custom providers
    if provider_config.api_base_url:
        client_args["api_base"] = provider_config.api_base_url

    # Get the LiteLLM model identifier
    model_id = _get_litellm_model_id(provider_config, model_name)

    # Create and return the strands LiteLLM model
    try:
        model = StrandsLiteLLMModel(model_id=model_id, client_args=client_args)
        return model
    except Exception as _:
        import traceback

        print(f"Error creating LiteLLM model: {traceback.format_exc()}")
        raise


def _get_litellm_model_id(provider_config: ProviderConfig, model_name: str) -> str:
    """Get the LiteLLM model identifier."""
    provider_prefix = provider_config.provider.value

    if provider_config.provider == ProviderType.CUSTOM:
        # For custom providers (OpenAI-compatible APIs), prepend openai/
        # This ensures LiteLLM treats it as an OpenAI-compatible endpoint
        return f"openai/{model_name}"

    return f"{provider_prefix}/{model_name}"


# For backward compatibility, expose a class that wraps the function
class LiteLLMModel:
    """LiteLLM wrapper for strands compatibility."""

    def __init__(self, provider_config: ProviderConfig, model_name: str):
        self.model = create_litellm_model(provider_config, model_name)
        self.provider_config = provider_config
        self.model_name = model_name

    def __getattr__(self, name: str):
        """Delegate all attribute access to the underlying model."""
        return getattr(self.model, name)

    @property
    def model_id(self) -> str:
        """Get the model identifier."""
        return _get_litellm_model_id(self.provider_config, self.model_name)


class ProviderFactory:
    """Factory for creating models from provider configurations."""

    @staticmethod
    def create_model(provider_config: ProviderConfig, model_name: str) -> LiteLLMModel:
        """Create a model instance from provider configuration."""
        return LiteLLMModel(provider_config, model_name)

    @staticmethod
    def get_suggested_models(provider_type: ProviderType) -> list[str]:
        """Get suggested model names for a provider type."""
        suggestions = {
            ProviderType.OPENAI: [
                "gpt-5.1",
                "gpt-5.1-codex-max",
            ],
            ProviderType.ANTHROPIC: [
                "claude-sonnet-4-5",
                "claude-opus-4-5",
            ],
            ProviderType.GEMINI: [
                "gemini-3-pro-preview",
                "gemini-2.5-flash",
            ],
            ProviderType.MISTRAL: [
                "mistral-large-latest",
                "mistral-medium-latest",
                "magistral-medium-latest",
                "devstral-medium-latest",
                "mistral-small-latest",
                "magistral-small-latest",
                "devstral-small-latest",
                "ministral-14b-latest",
            ],
            ProviderType.OLLAMA: [
                "qwen3-coder:30b",
                "ministral-3:14b",
                "rmdashrf/webgen-preview-4b:Q8_0",
            ],
            ProviderType.CUSTOM: [
                "zai-org/GLM-4.6",
                "deepseek-ai/DeepSeek-V3.2",
                "moonshotai/Kimi-K2-Thinking",
            ],
        }
        return suggestions.get(provider_type, [])

    @staticmethod
    def validate_model_format(provider_type: ProviderType, model_name: str) -> bool:
        """Validate that model name is appropriate for the provider."""
        if provider_type == ProviderType.CUSTOM:
            # Custom providers can use any model name
            return True

        # For other providers, check if it looks like a valid model identifier
        if not model_name or len(model_name.strip()) == 0:
            return False

        # Basic validation - no spaces, reasonable length
        return " " not in model_name and len(model_name) <= 100
