from strands import Agent

from grape_coder.tools.work_path import (
    list_files,
    read_file,
    set_work_path,
)

from ...config import get_config_manager
from ...config.litellm_integration import create_litellm_model


def create_architect_agent(work_path: str) -> Agent:
    """Create an architect agent for system architecture design"""
    set_work_path(work_path)

    # Load configuration
    config_manager = get_config_manager()
    config = config_manager.load_config()

    # Validate configuration
    if not config.agents:
        raise ValueError(
            "No agents configured. Run 'grape-coder config' to set up providers and agents."
        )

    agent_name = "architect"
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
        name="architect",
        description="Designs overall system architecture and technology stacks for websites",
    )
