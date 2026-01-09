from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field, model_validator


class ProviderType(str, Enum):
    """Supported provider types for LiteLLM integration."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    MISTRAL = "mistral"
    OLLAMA = "ollama"
    CUSTOM = "custom"


class ProviderConfig(BaseModel):
    """Configuration for a single provider."""

    provider: ProviderType = Field(..., description="Provider type")
    api_key: str = Field(..., description="API key for the provider")
    api_base_url: Optional[str] = Field(
        None, description="Base URL for custom providers"
    )

    @model_validator(mode="after")
    def validate_custom_provider(self):
        if self.provider == ProviderType.CUSTOM and not self.api_base_url:
            raise ValueError("api_base_url is required for custom providers")
        return self


class AgentConfig(BaseModel):
    """Configuration for a single agent."""

    provider_ref: str = Field(..., description="Reference to a provider name")
    model_name: str = Field(..., description="Model identifier for LiteLLM")


class LinterConfig(BaseModel):
    """Configuration for all linter commands."""

    oxlint: str = Field(
        default="npx oxlint",
        description="Command to run oxlint",
    )
    markuplint: str = Field(
        default="npx markuplint **/*.html",
        description="Command to run markuplint",
    )
    purgecss: str = Field(
        default="npx purgecss --css style/*.css --content **/*.html **/*.js -o style",
        description="Command to run purgecss",
    )
    linkinator: str = Field(
        default="npx linkinator . --recurse",
        description="Command to run linkinator",
    )


class GrapeCoderConfig(BaseModel):
    """Main configuration model with cross-reference validation."""

    providers: Dict[str, ProviderConfig] = Field(
        default_factory=dict, description="Provider configurations"
    )
    agents: Dict[str, AgentConfig] = Field(
        default_factory=dict, description="Agent configurations"
    )
    linter_commands: LinterConfig = Field(
        default_factory=LinterConfig,
        description="Commands to run linters (oxlint, markuplint, purgecss, linkinator)",
    )

    @model_validator(mode="after")
    def validate_agent_providers(self):
        if not isinstance(self.agents, dict):
            return self

        missing_providers = []

        for agent_name, agent_config in self.agents.items():
            if agent_config.provider_ref not in self.providers:
                missing_providers.append(f"{agent_name} -> {agent_config.provider_ref}")

        if missing_providers:
            raise ValueError(
                f"Agents reference non-existent providers: {', '.join(missing_providers)}. "
                f"Available providers: {list(self.providers.keys())}"
            )

        return self
