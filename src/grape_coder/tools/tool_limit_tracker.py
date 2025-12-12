"""Tool limit tracker for agents.

This module tracks the number of tool calls made by each agent
and enforces limits to prevent excessive tool usage.
"""

from typing import Dict
from ..agents.identifiers import AgentIdentifier, get_agent_tool_limit


class ToolLimitTracker:
    """Tracks tool usage for agents and enforces limits."""

    def __init__(self):
        """Initialize the tracker with empty counters."""
        self._tool_counts: Dict[str, int] = {}

    def increment_tool_count(self, agent_name: str) -> None:
        """Increment the tool count for a specific agent.

        Args:
            agent_name: Name of the agent that used a tool
        """
        if agent_name not in self._tool_counts:
            self._tool_counts[agent_name] = 0
        self._tool_counts[agent_name] += 1

    def has_hit_limit(self, agent_name: str) -> bool:
        """Check if an agent has hit its tool limit.

        Args:
            agent_name: Name of the agent to check

        Returns:
            True if the agent has hit or exceeded its limit, False otherwise
        """
        current_count = self._tool_counts.get(agent_name, 0)

        # Try to match agent name to identifier
        try:
            agent_id = AgentIdentifier(agent_name)
            limit = get_agent_tool_limit(agent_id)
        except ValueError:
            # If agent name doesn't match identifier, use default limit
            limit = 50

        return current_count >= limit

    def get_tool_count(self, agent_name: str) -> int:
        """Get the current tool count for an agent.

        Args:
            agent_name: Name of the agent

        Returns:
            Current tool count for the agent
        """
        return self._tool_counts.get(agent_name, 0)

    def reset_agent_count(self, agent_name: str) -> None:
        """Reset the tool count for a specific agent.

        Args:
            agent_name: Name of the agent to reset
        """
        if agent_name in self._tool_counts:
            del self._tool_counts[agent_name]

    def reset_all_counts(self) -> None:
        """Reset all tool counts."""
        self._tool_counts.clear()


# Global instance for tracking tool usage
_tool_tracker = ToolLimitTracker()


def increment_tool_count(agent_name: str) -> None:
    """Increment the tool count for an agent.

    Args:
        agent_name: Name of the agent that used a tool
    """
    _tool_tracker.increment_tool_count(agent_name)


def has_hit_limit(agent_name: str) -> bool:
    """Check if an agent has hit its tool limit.

    Args:
        agent_name: Name of the agent to check

    Returns:
        True if the agent has hit or exceeded its limit, False otherwise
    """
    return _tool_tracker.has_hit_limit(agent_name)


def get_tool_count(agent_name: str) -> int:
    """Get the current tool count for an agent.

    Args:
        agent_name: Name of the agent

    Returns:
        Current tool count for the agent
    """
    return _tool_tracker.get_tool_count(agent_name)


def reset_agent_count(agent_name: str) -> None:
    """Reset the tool count for a specific agent.

    Args:
        agent_name: Name of the agent to reset
    """
    _tool_tracker.reset_agent_count(agent_name)


def reset_all_counts() -> None:
    """Reset all tool counts."""
    _tool_tracker.reset_all_counts()
