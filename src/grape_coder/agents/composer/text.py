from strands import Agent

from grape_coder.config.manager import get_config_manager
from grape_coder.tools.work_path import (
    edit_file,
    glob_files,
    grep_files,
    list_files,
    read_file,
    set_work_path,
    get_agent_tasks,
)


def create_text_agent(work_path: str) -> Agent:
    """Create an agent for generating text content for web pages"""

    # Set work_path for tools
    set_work_path(work_path)

    # Load configuration
    config_manager = get_config_manager()
    config = config_manager.load_config()

    # Validate configuration
    if not config.agents:
        raise ValueError(
            "No agents configured. Run 'grape-coder config' to set up providers and agents."
        )

    agent_name = "text_generator"
    if agent_name not in config.agents:
        available_agents = list(config.agents.keys())
        raise ValueError(
            f"Agent '{agent_name}' not found. Available agents: {available_agents}. "
            "Run 'grape-coder config' to manage agents."
        )

    agent_config = config.agents[agent_name]
    provider_config = config.providers[agent_config.provider_ref]

    # Create model using ProviderFactory
    from ...config import ProviderFactory

    model = ProviderFactory.create_model(
        provider_config, agent_config.model_name
    ).model

    # Create agent with text generation tools
    system_prompt = """You are a professional copywriter and content specialist.
Your role is to generate compelling, clear, and engaging text content for web pages.

Available tools:
- list_files: List files and directories in a path
- read_file: Read contents of one or more files
- edit_file: Edit or create a file with new content
- grep_files: Search for patterns in files
- glob_files: Find files using glob patterns

Best practices:
- Write clear, concise, and engaging copy
- Use active voice and action verbs
- Tailor tone to the target audience
- Include relevant keywords naturally
- Keep accessibility in mind (clear language)
- Create scannable content with varied sentence lengths
- Organize content in files (e.g., content/headings.txt, content/paragraphs.txt)

Always match the brand voice and target audience specified."""

    return Agent(
        model=model,
        tools=[
            list_files,
            read_file,
            edit_file,
            grep_files,
            glob_files,
            get_agent_tasks,
        ],
        system_prompt=system_prompt,
        name="text_generator",
        description="AI assistant for generating web page text content",
    )
