from strands import Agent

from grape_coder.tools.web import fetch_url
from grape_coder.tools.work_path import (
    list_files,
    read_file,
    set_work_path,
)

from ...config import get_config_manager


def create_researcher_agent(work_path: str) -> Agent:
    """Create a researcher agent for website development research"""
    set_work_path(work_path)

    # Get model using the simplified config manager
    config_manager = get_config_manager()
    model = config_manager.get_model("researcher")

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
