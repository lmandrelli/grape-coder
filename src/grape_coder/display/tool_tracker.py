"""Tool usage tracker hook for displaying agent tool calls.

This module provides a hook provider that tracks and displays tool usage
by agents in real-time using rich formatting.
"""

import json
from typing import Any

from rich.console import Console
from rich.syntax import Syntax
from rich.tree import Tree
from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import BeforeToolCallEvent

from grape_coder.agents.identifiers import AgentIdentifier

# Global console instance for consistent output
_console = Console()


class ToolUsageTracker(HookProvider):
    """Hook provider that tracks and displays tool usage by agents.

    When an agent calls a tool, this hook displays:
    [Agent Name] tool_emoji Tool Name with parameters

    Example output:
    [code_agent] 🛠️ read_file
    └── Parameters: {"path": "/path/to/file.txt"}

    [text_generator] 🛠️ edit_file_contents
    └── Parameters: {"file_path": "/path/to/file.txt", "content": "Hello World"}
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

        Displays the agent name, tool being called, and parameters.

        Args:
            event: The BeforeToolCallEvent containing agent and tool info.
        """
        tool_name = event.tool_use.get("name", "unknown")
        tool_input = event.tool_use.get("input", {})

        # Use \[ to escape brackets so Rich doesn't interpret them as style tags
        self.console.print(
            f"[bold cyan]\\[{self.agent_name}][/bold cyan] [yellow]🛠️[/yellow]  {tool_name}"
        )

        # Display parameters if they exist
        if tool_input:
            self._display_parameters(tool_input)

    def _display_parameters(self, parameters: dict[str, Any]) -> None:
        """Display tool parameters with rich formatting.

        Args:
            parameters: The parameters dictionary to display.
        """
        # Create a tree structure for the parameters
        tree = Tree("📋 Parameters")

        for key, value in parameters.items():
            # Format the value based on its type
            if isinstance(value, str):
                if len(value) > 100:  # Truncate long strings
                    value_str = f"{value[:97]}..."
                else:
                    value_str = value
                tree.add(f'[dim]{key}[/dim]: [green]"{value_str}"[/green]')
            elif isinstance(value, (dict, list)):
                # For complex types, format as JSON
                try:
                    json_str = json.dumps(value, indent=2, ensure_ascii=False)
                    if len(json_str) > 200:  # Truncate long JSON
                        json_str = json_str[:197] + "..."
                    tree.add(f"[dim]{key}[/dim]:")
                    tree.add(Syntax(json_str, "json", theme="monokai", word_wrap=True))
                except (TypeError, ValueError):
                    tree.add(
                        f"[dim]{key}[/dim]: [yellow]{str(value)[:100]}{'...' if len(str(value)) > 100 else ''}[/yellow]"
                    )
            else:
                tree.add(f"[dim]{key}[/dim]: [blue]{value}[/blue]")

        # Display the tree with indentation
        self.console.print(tree)


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
