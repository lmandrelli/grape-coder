import os

from dotenv import load_dotenv
from strands import Agent
from strands.models.mistral import MistralModel

from grape_coder.tools.web import fetch_url
from grape_coder.tools.work_path import (
    edit_file,
    glob_files,
    grep_files,
    list_files,
    read_file,
    set_work_path,
)

load_dotenv()


def create_code_agent(work_path: str) -> Agent:
    """Create a code agent with file system tools"""

    # Set work_path for tools
    set_work_path(work_path)

    # Get configuration from environment variables
    api_key = os.getenv("MISTRAL_API_KEY")
    model_name = os.getenv("MISTRAL_MODEL_NAME", "mistral-large-latest")

    if not api_key:
        raise ValueError("MISTRAL_API_KEY environment variable is required.")

    # Create Mistral model
    model = MistralModel(
        api_key=api_key,
        model_id=model_name,
    )

    # Create agent with file system tools
    system_prompt = """You are a code assistant with access to file system tools.
You can list files, read files, edit/create files, search for content, use glob patterns, and fetch web content.

Available tools:
- list_files: List files and directories in a path
- read_file: Read contents of one or more files
- edit_file: Edit or create a file with new content
- grep_files: Search for patterns in files
- glob_files: Find files using glob patterns
- fetch_url: Fetch content from a URL

Always be helpful and provide clear explanations of what you're doing."""

    agent = Agent(
        model=model,
        tools=[
            list_files,
            read_file,
            edit_file,
            grep_files,
            glob_files,
            fetch_url,
        ],
        system_prompt=system_prompt,
        name="Code Agent",
        description="AI assistant for code and file operations",
    )

    return agent
