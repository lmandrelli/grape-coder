from strands import Agent

from grape_coder.tools.work_path import (
    list_files,
    read_file,
    set_work_path,
)

from grape_coder.agents.identifiers import AgentIdentifier
from grape_coder.config import get_config_manager


def create_designer_agent(work_path: str) -> Agent:
    """Create a designer agent for UI/UX design"""
    set_work_path(work_path)

    # Get model using the config manager
    config_manager = get_config_manager()
    model = config_manager.get_model(AgentIdentifier.DESIGNER)

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
