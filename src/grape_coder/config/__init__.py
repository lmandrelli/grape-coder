"""Configuration module for Grape Coder."""

import sys
from rich.console import Console

from .models import ProviderConfig, AgentConfig, GrapeCoderConfig, ProviderType
from .manager import ConfigManager, get_config_manager
from .litellm_integration import LiteLLMModel, ProviderFactory
from .cli import run_config_setup

# Initialize config manager immediately when config module is imported
console = Console()
try:
    _config_manager = get_config_manager()
except Exception as e:
    console.print(f"[red]Configuration error: {str(e)}[/red]")
    console.print(
        "[yellow]Run 'grape-coder config' to set up your configuration.[/yellow]"
    )
    sys.exit(1)

__all__ = [
    "ProviderConfig",
    "AgentConfig",
    "GrapeCoderConfig",
    "ProviderType",
    "ConfigManager",
    "get_config_manager",
    "LiteLLMModel",
    "ProviderFactory",
    "run_config_setup",
]
