from strands import Agent

from grape_coder.tools.work_path import (
    list_files,
    read_file,
    set_work_path,
)

from ...config import get_config_manager
from ...config.litellm_integration import create_litellm_model


def create_designer_agent(work_path: str) -> Agent:
    """Create a designer agent for UI/UX design"""
    set_work_path(work_path)

    # Load configuration
    config_manager = get_config_manager()
    config = config_manager.load_config()

    # Validate configuration
    if not config.agents:
        raise ValueError(
            "No agents configured. Run 'grape-coder config' to set up providers and agents."
        )

    agent_name = "designer"
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

    system_prompt = """You are a Website UI/UX Designer specializing in creating user interface and user experience designs.

Your expertise includes:
- User interface design principles
- User experience research and design
- Responsive design and mobile-first approaches
- Color theory and typography
- Layout and component design
- Accessibility and inclusive design
- Design systems and component libraries
- User flow and interaction design

When designing:
1. Review the architect's system design
2. Create comprehensive UI/UX specifications
3. Design page layouts and component structures
4. Define styling approaches and design systems
5. Plan responsive design strategies
6. Consider accessibility requirements
7. Hand off to the content planner when design is complete

Provide detailed design specifications that can be implemented by developers."""

    return Agent(
        model=model,
        tools=[list_files, read_file],
        system_prompt=system_prompt,
        name="designer",
        description="Creates UI/UX design specifications and layout plans for websites",
    )
