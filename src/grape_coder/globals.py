"""Global state management for grape-coder."""

from typing import Optional

_original_user_prompt: Optional[str] = None


def set_original_user_prompt(prompt: str) -> None:
    """Set the original user prompt globally."""
    global _original_user_prompt
    _original_user_prompt = prompt


def get_original_user_prompt() -> Optional[str]:
    """Get the original user prompt."""
    return _original_user_prompt


def clear_original_user_prompt() -> None:
    """Clear the original user prompt."""
    global _original_user_prompt
    _original_user_prompt = None
