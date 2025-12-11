"""Agent identifiers for Grape Coder.

This module defines all available agent identifiers that can be configured.
Each agent identifier represents a specific agent role in the system.
"""

from enum import Enum
from typing import Dict, List


class AgentIdentifier(str, Enum):
    """Enumeration of all available agent identifiers."""

    # Planner agents
    ARCHITECT = "architect"
    DESIGNER = "designer"
    CONTENT_PLANNER = "content_planner"
    RESEARCHER = "researcher"

    # Todo agent
    TODO = "todo_generator"

    # Composer agents
    ORCHESTRATOR = "orchestrator"

    GENERATE_CLASS = "class_generator"
    TEXT = "text_generator"
    SVG = "svg_generator"

    # Code agent
    CODE = "code_agent"

    # Mono-agent
    MONO_AGENT = "mono_agent"

    def __str__(self) -> str:
        return self.value


# Agent descriptions for CLI display
AGENT_DESCRIPTIONS: Dict[AgentIdentifier, str] = {
    AgentIdentifier.ARCHITECT: "Architecture planning agent for system design",
    AgentIdentifier.DESIGNER: "UI/UX design planning agent",
    AgentIdentifier.CONTENT_PLANNER: "Content strategy and planning agent",
    AgentIdentifier.RESEARCHER: "Research and information gathering agent",
    AgentIdentifier.TODO: "Todo list generation agent",
    AgentIdentifier.ORCHESTRATOR: "Orchestration agent for multi-agent coordination",
    AgentIdentifier.GENERATE_CLASS: "CSS class generation agent",
    AgentIdentifier.TEXT: "Text generation agent",
    AgentIdentifier.SVG: "SVG generation agent",
    AgentIdentifier.CODE: "Interactive code agent with file system tools",
    AgentIdentifier.MONO_AGENT: "A standalone coding agent for general programming tasks",
}


def get_all_agent_identifiers() -> List[AgentIdentifier]:
    """Get all available agent identifiers."""
    return list(AgentIdentifier)


def get_agent_description(agent_id: AgentIdentifier) -> str:
    """Get description for a specific agent identifier."""
    return AGENT_DESCRIPTIONS.get(agent_id, "No description available")


def get_agent_values() -> List[str]:
    """Get list of agent choices for CLI selection."""
    return [agent.value for agent in AgentIdentifier]


def get_agent_display_list() -> List[str]:
    """Get formatted list of agents for CLI display."""
    result: List[str] = []
    for agent in AgentIdentifier:
        description = get_agent_description(agent)
        result.append(f"{agent.value}: {description}")
    return result
