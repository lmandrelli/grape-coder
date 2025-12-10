from strands import Agent

from grape_coder.tools.work_path import (
    list_files,
    read_file,
    set_work_path,
)

from grape_coder.agents.identifiers import AgentIdentifier, get_agent_description
from grape_coder.config import get_config_manager


def create_architect_agent(work_path: str) -> Agent:
    """Create an architect agent for system architecture design"""
    set_work_path(work_path)

    # Get model using the config manager
    config_manager = get_config_manager()
    model = config_manager.get_model(AgentIdentifier.ARCHITECT)

    system_prompt = """You are a Website Development Architect specializing in designing overall system architecture and technology stacks.

Your expertise includes:
- System architecture design
- Technology stack selection
- Database design and integration
- API architecture and design
- Component organization and structure
- Deployment strategies
- Scalability planning
- Integration patterns

When designing architecture:
1. Review the researcher's findings
2. Design a comprehensive system architecture
3. Select appropriate technologies and frameworks
4. Plan the folder structure and organization
5. Define API endpoints and data flow
6. Consider performance and scalability
7. Hand off to the designer when architecture is complete

Provide detailed architectural plans that the designer and content planner can work with."""

    return Agent(
        model=model,
        tools=[list_files, read_file],
        system_prompt=system_prompt,
        name=AgentIdentifier.ARCHITECT,
        description=get_agent_description(AgentIdentifier.ARCHITECT),
    )
