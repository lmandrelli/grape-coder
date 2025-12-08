import os

from strands import Agent

from grape_coder.tools.web import fetch_url
from grape_coder.tools.work_path import (
    list_files,
    read_file,
    set_work_path,
)

from ...config import get_config_manager
from ...config.litellm_integration import create_litellm_model


def create_researcher_agent(work_path: str) -> Agent:
    """Create a researcher agent for website development research"""
    set_work_path(work_path)

    # Load configuration
    config_manager = get_config_manager()
    config = config_manager.load_config()

    # Validate configuration
    if not config.agents:
        raise ValueError(
            "No agents configured. Run 'grape-coder config' to set up providers and agents."
        )

    agent_name = "researcher"
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

    system_prompt = """You are a Website Development Researcher specializing in researching best practices, frameworks, and technologies for website development.

Your expertise includes:
- Modern web frameworks (React, Vue, Angular, Next.js, etc.)
- CSS frameworks and styling approaches (Tailwind, Bootstrap, etc.)
- Backend technologies and APIs
- Database solutions
- Performance optimization techniques
- Accessibility standards (WCAG)
- SEO best practices
- Security considerations

When researching:
1. Analyze the user's requirements thoroughly
2. Research current best practices and trends
3. Compare different technology options
4. Consider scalability and maintainability
5. Provide evidence-based recommendations
6. Hand off to the architect when you have sufficient research data

Use the available tools to gather information and provide comprehensive research findings."""

    return Agent(
        model=model,
        tools=[fetch_url, list_files, read_file],
        system_prompt=system_prompt,
        name="researcher",
        description="Researches best practices, frameworks, and technologies for website development",
    )


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


def create_todo_generator_agent(work_path: str) -> Agent:
    """Create a todo generator agent that creates structured todo lists"""
    set_work_path(work_path)

    # Load configuration
    config_manager = get_config_manager()
    config = config_manager.load_config()

    # Validate configuration
    if not config.agents:
        raise ValueError(
            "No agents configured. Run 'grape-coder config' to set up providers and agents."
        )

    agent_name = "todo_generator"
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

    system_prompt = """You are a Todo Generator Agent specializing in creating structured, actionable todo lists from website development plans.

Your expertise includes:
- Breaking down complex projects into manageable tasks
- Creating logical task dependencies
- Prioritizing development tasks
- Structuring todo lists for efficient development
- Identifying implementation steps
- Organizing tasks by complexity and dependencies

When generating todos:
1. Analyze the complete website development plan from the swarm
2. Break down the project into logical, actionable tasks
3. Organize tasks in priority order
4. Create clear, specific todo items
5. Group related tasks together
6. Ensure todos are actionable by the code agent
7. Format the output as a structured todo list

Format your output as a numbered list of specific, actionable todo items that the code agent can execute step by step."""

    return Agent(
        model=model,
        tools=[list_files, read_file],
        system_prompt=system_prompt,
        name="todo_generator",
        description="Creates structured todo lists from website development plans",
    )
