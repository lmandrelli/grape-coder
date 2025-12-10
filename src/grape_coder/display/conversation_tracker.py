"""Conversation tracker hook for displaying agent conversation flow.

This module provides a hook provider that tracks and displays conversation
messages by agents in real-time using rich formatting.
"""

from typing import Any

from rich.console import Console
from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import MessageAddedEvent

from grape_coder.agents.identifiers import AgentIdentifier

# Global console instance for consistent output
_console = Console()


class ConversationTracker(HookProvider):
    """Hook provider that tracks and displays conversation messages by agents.

    When an agent processes messages, this hook displays:
    - User prompts (debug mode only)
    - Assistant responses (always)
    - Tool results (debug mode only, truncated)

    Example output:
    [agent_name] 🚀 Request #1 starting
    ────────────────────────────────────────────────────────────
    [agent_name] 💬 User: What files are in current directory?  (debug only)
    ────────────────────────────────────────────────────────────
    [agent_name] 🤖 Assistant: I'll check the current directory for you...
    ────────────────────────────────────────────────────────────
    [agent_name] 🛠️ Tool: read_file  (debug only)
      Result: [truncated tool result]
    ────────────────────────────────────────────────────────────
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
        # Access global debug flag
        from grape_coder import get_debug_mode
        self.debug_mode = get_debug_mode()

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        """Register the message added hook.

        Args:
            registry: The hook registry to register callbacks with.
            **kwargs: Additional keyword arguments (unused).
        """
        registry.add_callback(MessageAddedEvent, self._on_message_added)

    def _display_separator(self) -> None:
        """Display a visual separator line."""
        console_width = self.console.width or 80
        separator = "─" * console_width
        self.console.print(f"[dim]{separator}[/dim]")

    def _on_message_added(self, event: MessageAddedEvent) -> None:
        """Handle the message added event.

        Displays the message based on its role and debug mode.

        Args:
            event: The MessageAddedEvent containing message info.
        """
        message = event.message
        role = getattr(message, 'role', 'unknown')
        content = getattr(message, 'content', '')

        # Track request lifecycle
        if role == 'user':
            self.request_count += 1
            self._display_separator()
            self.console.print(
                f"[bold cyan]\\[{self.agent_name}][/bold cyan] [green]🚀[/green] Request #{self.request_count} starting"
            )
            self._display_separator()

        # Display user messages only in debug mode
        if role == 'user' and self.debug_mode:
            self._display_user_message(content)
        # Always display assistant messages
        elif role == 'assistant':
            self._display_assistant_message(content)
        # Display tool messages only in debug mode
        elif role == 'tool' and self.debug_mode:
            self._display_tool_message(content)

        # Mark request completion after assistant response
        if role == 'assistant':
            self._display_separator()
            self.console.print(
                f"[bold cyan]\\[{self.agent_name}][/bold cyan] [green]✅[/green] Request #{self.request_count} completed"
            )

    def _display_user_message(self, content: str) -> None:
        """Display a user message.

        Args:
            content: The user message content.
        """
        self._display_separator()
        self.console.print(
            f"[bold cyan]\\[{self.agent_name}][/bold cyan] [blue]💬[/blue] User: {content}"
        )

    def _display_assistant_message(self, content: str) -> None:
        """Display an assistant message.

        Args:
            content: The assistant message content.
        """
        self._display_separator()
        self.console.print(
            f"[bold cyan]\\[{self.agent_name}][/bold cyan] [green]🤖[/green] Assistant: {content}"
        )

    def _display_tool_message(self, content: str) -> None:
        """Display a tool message with truncated content.

        Args:
            content: The tool result content.
        """
        self._display_separator()
        self.console.print(
            f"[bold cyan]\\[{self.agent_name}][/bold cyan] [yellow]🛠️[/yellow] Tool Result:"
        )
        
        # Truncate tool results for readability
        if content:
            truncated_content = content[:150] + "..." if len(content) > 150 else content
            self.console.print(f"  [dim]{truncated_content}[/dim]")


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