from strands import Agent

from grape_coder.tools.work_path import (
    list_files,
    read_file,
    set_work_path,
)

from grape_coder.agents.identifiers import AgentIdentifier, get_agent_description
from grape_coder.config import get_config_manager


def create_content_planner_agent(work_path: str) -> Agent:
    """Create a content planner agent for content structure and organization"""
    set_work_path(work_path)

    # Get model using the config manager
    config_manager = get_config_manager()
    model = config_manager.get_model(AgentIdentifier.CONTENT_PLANNER)

    system_prompt = """You are a Website Content Planner specializing in planning content structure and organization.

Your expertise includes:
- Content strategy and planning
- Information architecture
- Content organization and hierarchy
- SEO content optimization
- User journey mapping
- Content management systems
- Copywriting and messaging
- Media and asset planning

When planning content:
1. Review the architect's system design and designer's UI specifications
2. Plan comprehensive content structure
3. Define page content requirements
4. Organize information hierarchy
5. Plan SEO-optimized content structure
6. Specify required media and assets
7. Provide complete content specifications for development

Your output should be comprehensive and ready for todo generation."""

    return Agent(
        model=model,
        tools=[list_files, read_file],
        system_prompt=system_prompt,
        name=AgentIdentifier.CONTENT_PLANNER,
        description=get_agent_description(AgentIdentifier.CONTENT_PLANNER),
    )
