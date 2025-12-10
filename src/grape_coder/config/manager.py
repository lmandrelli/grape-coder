import json
import os
from pathlib import Path
from typing import Any, Optional

import platformdirs

from .litellm_integration import create_litellm_model
from .models import GrapeCoderConfig, ProviderConfig, AgentConfig
from ..agents.identifiers import get_agent_values

# Global config manager instance
_config_manager = None


class ConfigManager:
    """Manages loading, saving, and caching of Grape Coder configurations."""

    def __init__(self):
        self._config_dir = Path(platformdirs.user_config_dir("grape-coder"))
        self._config_file = self._config_dir / "providers.json"
        self.config: Optional[GrapeCoderConfig] = None
        self._model_cache: dict[str, Any] = {}
        self._dropped_items: dict[str, list[str]] = {
            "malformed_providers": [],
            "malformed_agents": [],
            "unrecognized_agents": [],
            "orphaned_agents": [],
        }

        # Ensure config directory exists with proper permissions
        self._ensure_config_directory()
        # Load configuration once during singleton initialization
        config_result = self._load_config_from_file()
        self.config = config_result[0]
        self._dropped_items = config_result[1]

    def _ensure_config_directory(self) -> None:
        """Create config directory with secure permissions."""
        try:
            self._config_dir.mkdir(parents=True, exist_ok=True)
            # Set directory permissions to 700 (user read/write/execute only)
            os.chmod(self._config_dir, 0o700)
        except OSError as e:
            raise RuntimeError(f"Failed to create config directory: {e}")

    def _set_secure_permissions(self, file_path: Path) -> None:
        """Set secure file permissions (600 - user read/write only)."""
        try:
            os.chmod(file_path, 0o600)
        except OSError as e:
            raise RuntimeError(f"Failed to set secure permissions on {file_path}: {e}")

    def _load_config_from_file(self) -> tuple[GrapeCoderConfig, dict[str, list[str]]]:
        """Load configuration from file, gracefully handling malformed entries.

        Returns:
            Tuple of (config, dropped_items) where dropped_items contains:
            - 'malformed_providers': list of provider names that were dropped
            - 'malformed_agents': list of agent names that were dropped
            - 'unrecognized_agents': list of agent names that were dropped
            - 'orphaned_agents': list of agent names with missing providers
        """
        dropped_items: dict[str, list[str]] = {
            "malformed_providers": [],
            "malformed_agents": [],
            "unrecognized_agents": [],
            "orphaned_agents": [],
        }

        try:
            if not self._config_file.exists():
                return GrapeCoderConfig(), dropped_items

            with open(self._config_file, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            # Extract valid providers
            valid_providers: dict[str, ProviderConfig] = {}
            if "providers" in config_data:
                for provider_name, provider_data in config_data["providers"].items():
                    try:
                        provider_config: ProviderConfig = ProviderConfig(
                            **provider_data
                        )
                        valid_providers[provider_name] = provider_config
                    except Exception:
                        # Skip malformed provider
                        dropped_items["malformed_providers"].append(provider_name)
                        continue

            # Extract valid agents
            valid_agents: dict[str, AgentConfig] = {}
            required_agents = set(get_agent_values())
            if "agents" in config_data:
                for agent_name, agent_data in config_data["agents"].items():
                    # Skip unrecognized agents
                    if agent_name not in required_agents:
                        dropped_items["unrecognized_agents"].append(agent_name)
                        continue

                    try:
                        agent_config: AgentConfig = AgentConfig(**agent_data)
                        # Skip agents that reference non-existent providers
                        if agent_config.provider_ref not in valid_providers:
                            dropped_items["orphaned_agents"].append(agent_name)
                            continue
                        valid_agents[agent_name] = agent_config
                    except Exception:
                        # Skip malformed agent
                        dropped_items["malformed_agents"].append(agent_name)
                        continue

            return GrapeCoderConfig(
                providers=valid_providers, agents=valid_agents
            ), dropped_items

        except Exception:
            # Return empty config if JSON is invalid or any other error
            return GrapeCoderConfig(), dropped_items

    def save_config(self, config: GrapeCoderConfig) -> None:
        """Save configuration to file with secure permissions."""
        try:
            # Validate configuration before saving
            config.model_validate(config.model_dump())

            # Write to temporary file first, then move to prevent corruption
            temp_file = self._config_file.with_suffix(".tmp")

            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(config.model_dump(), f, indent=4, ensure_ascii=False)

            # Set secure permissions on temp file
            self._set_secure_permissions(temp_file)

            # Atomic move to final location
            temp_file.replace(self._config_file)

            # Update cached config
            self.config = config
            # Reset dropped items when saving a valid config
            self._dropped_items = {
                "malformed_providers": [],
                "malformed_agents": [],
                "unrecognized_agents": [],
                "orphaned_agents": [],
            }

        except Exception as e:
            raise RuntimeError(f"Failed to save configuration: {e}")

    def config_exists(self) -> bool:
        """Check if configuration file exists."""
        return self._config_file.exists()

    def get_config_path(self) -> str:
        """Get the path to the configuration file."""
        return str(self._config_file)

    def get_model(self, agent_identifier: str) -> Any:
        """Get a model instance for the specified agent identifier.

        Args:
            agent_identifier: The name of the agent configuration

        Returns:
            A model instance ready for use

        Raises:
            ValueError: If configuration is missing or invalid
            RuntimeError: If model creation fails
        """
        # Check model cache first
        if agent_identifier in self._model_cache:
            return self._model_cache[agent_identifier]

        # Use config loaded during singleton initialization
        if self.config is None:
            # This shouldn't happen, but fallback just in case
            config_result = self._load_config_from_file()
            self.config = config_result[0]
            self._dropped_items = config_result[1]

        config = self.config
        if not config:
            raise ValueError(
                "No configuration found. Run 'grape-coder config' to set up providers and agents."
            )

        # Validate agents configuration exists
        if not config.agents:
            raise ValueError(
                "No agents configured. Run 'grape-coder config' to set up providers and agents."
            )

        # Validate specific agent exists
        if agent_identifier not in config.agents:
            available_agents = list(config.agents.keys())
            raise ValueError(
                f"Agent '{agent_identifier}' not found. Available agents: {available_agents}. "
                "Run 'grape-coder config' to manage agents."
            )

        # Get agent and provider configurations
        agent_config = config.agents[agent_identifier]
        provider_config = config.providers[agent_config.provider_ref]

        # Create model
        try:
            model = create_litellm_model(provider_config, agent_config.model_name)

            # Cache the model
            self._model_cache[agent_identifier] = model

            return model

        except Exception as e:
            raise RuntimeError(
                f"Failed to create model for agent '{agent_identifier}': {e}"
            )

    def validate_config(self, panic: bool = True) -> bool | dict[str, list[str]]:
        """Validate configuration and provide detailed error messages.

        Args:
            panic: If True, raises exceptions on validation errors. If False, returns error dict.

        Returns:
            True if configuration is valid (when panic=True)
            Error dict with categorized validation errors (when panic=False)

        Raises:
            ValueError: When configuration is invalid and panic=True
        """
        errors: dict[str, list[str]] = {
            "providers": [],
            "agents": [],
            "missing": [],
            "additional": [],
        }

        config = self.config

        if config is None:
            errors["missing"].append("No configuration found")
            if panic:
                raise ValueError("No configuration found.")
            return errors

        # Check for at least one provider
        if not config.providers:
            errors["missing"].append("At least one provider is required")
        else:
            # Check for malformed providers
            for provider_name, provider_config in config.providers.items():
                try:
                    ProviderConfig.model_validate(provider_config.model_dump())
                except Exception as e:
                    errors["providers"].append(f"Provider '{provider_name}': {str(e)}")

        # Check for required agents and additional/unrecognized agents
        required_agents = set(get_agent_values())
        configured_agents: set[str] = (
            set(config.agents.keys()) if config.agents else set()
        )

        missing_agents = required_agents - configured_agents

        if missing_agents:
            errors["missing"].extend(
                [f"Agent '{agent}'" for agent in sorted(missing_agents)]
            )

        # Add unrecognized agents from dropped items (already detected during loading)
        if self._dropped_items["unrecognized_agents"]:
            errors["additional"].extend(
                [
                    f"Agent '{agent}'"
                    for agent in sorted(self._dropped_items["unrecognized_agents"])
                ]
            )

        # Add malformed providers from dropped items
        if self._dropped_items["malformed_providers"]:
            errors["providers"].extend(
                [
                    f"Provider '{provider}' (malformed)"
                    for provider in sorted(self._dropped_items["malformed_providers"])
                ]
            )

        # Add malformed agents from dropped items
        if self._dropped_items["malformed_agents"]:
            errors["agents"].extend(
                [
                    f"Agent '{agent}' (malformed)"
                    for agent in sorted(self._dropped_items["malformed_agents"])
                ]
            )

        # Add orphaned agents from dropped items
        if self._dropped_items["orphaned_agents"]:
            errors["agents"].extend(
                [
                    f"Agent '{agent}' references non-existent provider"
                    for agent in sorted(self._dropped_items["orphaned_agents"])
                ]
            )

        # Check for malformed agents and provider references
        if config.agents:
            for agent_name, agent_config in config.agents.items():
                # Check if agent references a valid provider
                if agent_config.provider_ref not in config.providers:
                    errors["agents"].append(
                        f"Agent '{agent_name}' references non-existent provider '{agent_config.provider_ref}'"
                    )
                    continue

                # Validate agent configuration
                try:
                    AgentConfig.model_validate(agent_config.model_dump())
                except Exception as e:
                    errors["agents"].append(f"Agent '{agent_name}': {str(e)}")

        # Return based on panic mode
        has_errors = any(errors.values())

        if has_errors:
            if panic:
                raise ValueError("Configuration Invalid")
            else:
                return errors
        else:
            return True if panic else {}

    def display_validation_errors(self, errors: dict[str, list[str]]) -> None:
        """Display validation errors in the required format.

        Args:
            errors: Dictionary containing categorized validation errors
        """
        from rich.console import Console

        console = Console()

        console.print("\n[bold yellow]Configuration Issues Found:[/bold yellow]")

        if errors["providers"]:
            console.print("\n[bold red]Providers:[/bold red]")
            for error in errors["providers"]:
                console.print(f"  - {error}")

        if errors["agents"]:
            console.print("\n[bold red]Agents:[/bold red]")
            for error in errors["agents"]:
                console.print(f"  - {error}")

        if errors["missing"]:
            console.print("\n[bold red]Missing:[/bold red]")
            for error in errors["missing"]:
                console.print(f"  - {error}")

        if errors["additional"]:
            console.print("\n[bold yellow]Additional (unexpected):[/bold yellow]")
            for error in errors["additional"]:
                console.print(f"  - {error}")

    def clear_cache(self) -> None:
        """Clear the configuration cache."""
        config_result = self._load_config_from_file()
        self.config = config_result[0]
        self._dropped_items = config_result[1]
        self._model_cache.clear()


def get_config_manager() -> ConfigManager:
    """Get the global config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
