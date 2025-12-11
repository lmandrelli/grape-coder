"""Grape Coder CLI package."""

# Global debug flag - accessible throughout the application
DEBUG_MODE: bool = False

def set_debug_mode(debug: bool) -> None:
    """Set the global debug mode."""
    global DEBUG_MODE
    DEBUG_MODE = debug

def get_debug_mode() -> bool:
    """Get the current debug mode."""
    return DEBUG_MODE
