"""Agents package for grape-coder"""

from .code import create_code_agent

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
    
__all__ = [
    "create_code_agent",
]
