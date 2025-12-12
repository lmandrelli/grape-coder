"""Hook provider for tracking agent tool usage and enforcing limits.

This module provides a Strands hook provider that monitors tool usage
by agents and enforces tool call limits to prevent excessive usage.
"""

from typing import Any

from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import BeforeToolCallEvent

from grape_coder.agents.identifiers import AgentIdentifier

from .tool_limit_tracker import has_hit_limit, increment_tool_count, get_tool_count


class ToolLimitHookProvider(HookProvider):
    """Hook provider that tracks tool usage and enforces limits.

    When an agent calls a tool, this hook checks if the agent has hit its
    tool usage limit and cancels the tool call if the limit is exceeded.

    Debug output:
    [DEBUG] Agent 'code_agent' attempting to use tool 'read_file' (current count: 0)
    [DEBUG] Agent 'code_agent' used tool 'read_file' (new count: 1)
    """

    def __init__(self, agent_name: AgentIdentifier):
        """Initialize the tool limit hook provider.

        Args:
            agent_name: The AgentIdentifier for this hook provider.
        """
        self.agent_name = agent_name.value

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        """Register the before tool call hook.

        Args:
            registry: The hook registry to register callbacks with.
            **kwargs: Additional keyword arguments (unused).
        """
        registry.add_callback(BeforeToolCallEvent, self._on_before_tool)

    def _on_before_tool(self, event: BeforeToolCallEvent) -> None:
        """Handle the before tool call event.

        Checks if the agent has hit its tool usage limit and cancels
        the tool call if the limit is exceeded.

        Args:
            event: The BeforeToolCallEvent containing agent and tool info.
        """
        tool_name = (
            event.tool_use.get("name", "Unknown") if event.tool_use else "Unknown"
        )

        # Get current count before incrementing
        current_count = get_tool_count(self.agent_name)

        print(
            f"[DEBUG] Agent '{self.agent_name}' attempting to use tool '{tool_name}' (current count: {current_count})"
        )

        # Check if agent has hit limit
        if has_hit_limit(self.agent_name):
            print(
                f"[DEBUG] Agent '{self.agent_name}' has hit limit! Cancelling tool '{tool_name}'"
            )
            # Cancel the tool call with a clear message
            event.cancel_tool = f"Tool limit exceeded for agent '{self.agent_name}'. Please stop your session and write the finish command."
            return

        # Increment the tool count for this agent
        increment_tool_count(self.agent_name)
        new_count = get_tool_count(self.agent_name)
        print(
            f"[DEBUG] Agent '{self.agent_name}' used tool '{tool_name}' (new count: {new_count})"
        )


def get_tool_limit_hook(agent_name: AgentIdentifier) -> ToolLimitHookProvider:
    """Create a tool limit hook provider instance for a specific agent.

    Args:
        agent_name: The AgentIdentifier for the agent using this hook provider.

    Returns:
        A new ToolLimitHookProvider instance for the specified agent.
    """
    return ToolLimitHookProvider(agent_name=agent_name)
