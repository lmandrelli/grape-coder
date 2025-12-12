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

        # Check if agent has hit limit
        if has_hit_limit(self.agent_name):            # Cancel the tool call with a clear message
            event.cancel_tool = f"You hit the tool usage limit. Tool '{tool_name}' call cancelled. You should finish your task now by summarizing what you've done. YOUR WORK IS DONE, THIS MESSAGE CANCELS YOUR TASK, EVEN IF YOU WERE NOT DONE. NO FURTHER ACTIONS CAN BE DONE."
            return

        # Increment the tool count for this agent
        increment_tool_count(self.agent_name)

def get_tool_limit_hook(agent_name: AgentIdentifier) -> ToolLimitHookProvider:
    """Create a tool limit hook provider instance for a specific agent.

    Args:
        agent_name: The AgentIdentifier for the agent using this hook provider.

    Returns:
        A new ToolLimitHookProvider instance for the specified agent.
    """
    return ToolLimitHookProvider(agent_name=agent_name)
