"""Tool usage tracker hook for displaying agent tool calls.

This module provides a hook provider that tracks and displays tool usage
by agents in real-time using rich formatting.
"""

from typing import Any

from rich.console import Console
from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import BeforeToolCallEvent

from grape_coder.agents.identifiers import AgentIdentifier

# Global console instance for consistent output
_console = Console()


class ToolUsageTracker(HookProvider):
    """Hook provider that tracks and displays tool usage by agents.

    When an agent calls a tool, this hook displays:
    [Agent Name] tool_emoji Tool Name

    Example output:
    [code_agent] 🛠️ read_file
    [text_generator] 🛠️ edit_file_contents
    """

    def __init__(
        self,
        agent_name: AgentIdentifier,
        console: Console | None = None,
    ):
        """Initialize the tool usage tracker.

        Args:
            agent_name: The AgentIdentifier for this tracker.
            console: Optional rich Console instance. If not provided,
                    uses the module's global console.
        """
        self.agent_name = agent_name.value
        self.console = console or _console

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        """Register the before tool call hook.

        Args:
            registry: The hook registry to register callbacks with.
            **kwargs: Additional keyword arguments (unused).
        """
        registry.add_callback(BeforeToolCallEvent, self._on_before_tool)

    def _on_before_tool(self, event: BeforeToolCallEvent) -> None:
        """Handle the before tool call event.

        Displays the agent name and tool being called.

        Args:
            event: The BeforeToolCallEvent containing agent and tool info.
        """
        tool_name = event.tool_use.get("name", "unknown")

        # Use \[ to escape brackets so Rich doesn't interpret them as style tags
        self.console.print(
            f"[bold cyan]\\[{self.agent_name}][/bold cyan] [yellow]🛠️[/yellow]  {tool_name}"
        )


def get_tool_tracker(
    agent_name: AgentIdentifier,
    console: Console | None = None,
) -> ToolUsageTracker:
    """Create a tool tracker instance for a specific agent.

    Args:
        agent_name: The AgentIdentifier for the agent using this tracker.
        console: Optional rich Console instance for the tracker.

    Returns:
        A new ToolUsageTracker instance for the specified agent.
    """
    return ToolUsageTracker(agent_name=agent_name, console=console)
