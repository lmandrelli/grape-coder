"""
Grape Coder Agents Module

This module provides agent implementations with configuration validation.
All agent creation functions validate configuration on import to provide
clear error messages when setup is required.
"""

# Validate configuration on module import
try:
    from ..config import get_config_manager

    config_manager = get_config_manager()
    config = config_manager.load_config()

    if not config.agents:
        import warnings

        warnings.warn(
            "No agents configured. Run 'grape-coder config' to set up providers and agents.",
            UserWarning,
        )

except Exception as e:
    import warnings

    warnings.warn(
        f"Configuration validation failed: {e}. Run 'grape-coder config' to set up.",
        UserWarning,
    )
