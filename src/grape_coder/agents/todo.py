from strands import Agent

from grape_coder.config import get_config_manager
from grape_coder.tools.work_path import (
    list_files,
    read_file,
    set_work_path,
)


def create_todo_generator_agent(work_path: str) -> Agent:
    """Create a todo generator agent that creates structured todo lists"""
    set_work_path(work_path)

    # Get model using the config manager
    config_manager = get_config_manager()
    model = config_manager.get_model(agent_identifier="todo_generator")

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
