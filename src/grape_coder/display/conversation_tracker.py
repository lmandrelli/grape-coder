"""Conversation tracker hook for displaying agent conversation flow.

This module provides a comprehensive hook provider that tracks and displays conversation
messages by agents in real-time using rich formatting with full lifecycle awareness
and personalized context support.
"""

from typing import Any

from rich.console import Console
from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import (
    BeforeInvocationEvent,
    AfterInvocationEvent,
)

from grape_coder.agents.identifiers import AgentIdentifier

# Global console instance for consistent output
_console = Console()


class ConversationTracker(HookProvider):
    """Enhanced hook provider that tracks and displays conversation messages by agents.

    This hook provides comprehensive conversation tracking with:
    - Full request lifecycle tracking (start/end)
    Example output:
    [agent_name] 🚀 Request #1 starting (user: john_doe, session: abc123)
    ────────────────────────────────────────────
    Agent streaming response content...
    ────────────────────────────────────────────
    [agent_name] ✅ Request #1 completed
    """

    def __init__(
        self,
        agent_name: AgentIdentifier,
        console: Console | None = None,
    ):
        """Initialize the conversation tracker.

        Args:
            agent_name: The AgentIdentifier for this tracker.
            console: Optional rich Console instance. If not provided,
                    uses the module's global console.
        """
        self.agent_name = agent_name.value
        self.console = console or _console
        self.request_count = 0
        self.current_request_start = None
        # Access global debug flag
        from grape_coder import get_debug_mode

        self.debug_mode = get_debug_mode()

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        """Register comprehensive hooks for full conversation tracking.

        Args:
            registry: The hook registry to register callbacks with.
            **kwargs: Additional keyword arguments (unused).
        """
        registry.add_callback(BeforeInvocationEvent, self._on_request_start)
        registry.add_callback(AfterInvocationEvent, self._on_request_complete)

    def _get_context_info(self, invocation_state: dict[str, Any] | None) -> str:
        """Extract personalized context information from invocation state.

        Args:
            invocation_state: The invocation state containing context data.

        Returns:
            Formatted context string for display.
        """
        if not invocation_state:
            return ""

        context_parts : list[str] = []

        # User information
        if user_id := invocation_state.get("user_id"):
            context_parts.append(f"user: {user_id}")

        # Session information
        if session_id := invocation_state.get("session_id"):
            context_parts.append(f"session: {session_id}")

        # Request ID
        if request_id := invocation_state.get("request_id"):
            context_parts.append(f"req: {request_id}")

        # Custom context
        if custom_context := invocation_state.get("custom_context"):
            context_parts.append(f"context: {custom_context}")

        return f" ({', '.join(context_parts)})" if context_parts else ""

    def _display_separator(self) -> None:
        """Display a visual separator line."""
        console_width = self.console.width or 80
        separator = "─" * console_width
        self.console.print(f"\n[dim]{separator}[/dim]")

    def _on_request_start(self, event: BeforeInvocationEvent) -> None:
        """Handle request start event.

        Args:
            event: The BeforeInvocationEvent containing request info.
        """
        self.request_count += 1
        self.current_request_start = event

        # Extract context from agent's invocation state
        context_info = self._get_context_info(getattr(event, "invocation_state", None))

        self._display_separator()
        self.console.print(
            f"[bold cyan]\\[{self.agent_name}][/bold cyan] [green]🚀[/green] Request #{self.request_count} starting{context_info}"
        )
        self._display_separator()

    def _on_request_complete(self, event: AfterInvocationEvent) -> None:
        """Handle request completion event.

        Args:
            event: The AfterInvocationEvent containing completion info.
        """
        # Calculate duration if we have start time
        self._display_separator()
        self.console.print(
            f"[bold cyan]\\[{self.agent_name}][/bold cyan] [green]✅[/green] Request #{self.request_count} completed"
        )
        self.current_request_start = None


def get_conversation_tracker(
    agent_name: AgentIdentifier,
    console: Console | None = None,
) -> ConversationTracker:
    """Create a conversation tracker instance for a specific agent.

    Args:
        agent_name: The AgentIdentifier for the agent using this tracker.
        console: Optional rich Console instance for the tracker.

    Returns:
        A new ConversationTracker instance for the specified agent.
    """
    return ConversationTracker(agent_name=agent_name, console=console)
