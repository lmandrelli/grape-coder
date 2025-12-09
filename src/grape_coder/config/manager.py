import json
import os
from pathlib import Path
from typing import Any, Optional

import platformdirs
from pydantic import ValidationError

from .litellm_integration import create_litellm_model
from .models import GrapeCoderConfig

# Global config manager instance
_config_manager = None


class ConfigManager:
    """Manages loading, saving, and caching of Grape Coder configurations."""

    def __init__(self):
        self._config_dir = Path(platformdirs.user_config_dir("grape-coder"))
        self._config_file = self._config_dir / "providers.json"
        self.config: Optional[GrapeCoderConfig] = None
        self._model_cache: dict[str, Any] = {}

        # Ensure config directory exists with proper permissions
        self._ensure_config_directory()
        # Load configuration once during singleton initialization
        self.config = self._load_config_from_file()

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

    def _load_config_from_file(self) -> GrapeCoderConfig:
        """Load configuration from file."""
        try:
            if not self._config_file.exists():
                return GrapeCoderConfig()

            with open(self._config_file, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            return GrapeCoderConfig(**config_data)

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
        except ValidationError as e:
            raise ValueError(f"Configuration validation failed: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration: {e}")

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

        except ValidationError as e:
            raise ValueError(f"Configuration validation failed: {e}")
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
            self.config = self._load_config_from_file()

        config = self.config

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

    def clear_cache(self) -> None:
        """Clear the configuration cache."""
        self.config = None
        self._model_cache.clear()


def get_config_manager() -> ConfigManager:
    """Get the global config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
