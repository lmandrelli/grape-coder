from strands import Agent

from grape_coder.tools.work_path import (
    list_files,
    read_file,
    set_work_path,
)

from ...config import get_config_manager
from ...config.litellm_integration import create_litellm_model


def create_content_planner_agent(work_path: str) -> Agent:
    """Create a content planner agent for content structure and organization"""
    set_work_path(work_path)

    # Load configuration
    config_manager = get_config_manager()
    config = config_manager.load_config()

    # Validate configuration
    if not config.agents:
        raise ValueError(
            "No agents configured. Run 'grape-coder config' to set up providers and agents."
        )

    agent_name = "content_planner"
    if agent_name not in config.agents:
        available_agents = list(config.agents.keys())
        raise ValueError(
            f"Agent '{agent_name}' not found. Available agents: {available_agents}. "
            "Run 'grape-coder config' to manage agents."
        )

    agent_config = config.agents[agent_name]
    provider_config = config.providers[agent_config.provider_ref]

    # Create model using LiteLLM integration
    model = create_litellm_model(provider_config, agent_config.model_name)

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
        name="content_planner",
        description="Plans content structure and organization for websites",
    )
