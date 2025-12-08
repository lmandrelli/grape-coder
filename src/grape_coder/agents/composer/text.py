import os

from dotenv import load_dotenv
from strands import Agent
from strands.models.mistral import MistralModel

from grape_coder.tools.work_path import (
    edit_file,
    glob_files,
    grep_files,
    list_files,
    read_file,
    set_work_path,
)

load_dotenv()


def create_text_agent(work_path: str) -> Agent:
    """Create an agent for generating text content for web pages"""

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

    agent = Agent(
        model=model,
        tools=[
            list_files,
            read_file,
            edit_file,
            grep_files,
            glob_files,
        ],
        system_prompt=system_prompt,
        name="Text Agent",
        description="AI assistant for generating web page text content",
    )

    return agent
