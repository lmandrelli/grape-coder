import os
from pathlib import Path

from dotenv import load_dotenv

from ..models import Agent, LLMModel, ToolParameter
from ..providers import OpenAIProvider
from ..tools import Tool, WorkPathTool

load_dotenv()


def create_code_agent(work_path: str) -> Agent:
    """Create a code agent with file system tools"""

    # Get configuration from environment variables
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model_name = os.getenv("OPENAI_MODEL_NAME")

    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required. ")

    if not model_name:
        raise ValueError("OPENAI_MODEL_NAME environment variable is required. ")

    # Create LLMModel instance
    llm_model = LLMModel(name=model_name)

    # Create OpenAIProvider with environment configuration
    provider_kwargs = {"model": llm_model, "api_key": api_key}

    if base_url:
        provider_kwargs["base_url"] = base_url

    provider = OpenAIProvider(**provider_kwargs)

    # Create agent
    system_prompt = """You are a code assistant with access to file system tools.
You can list files, read files, edit/create files, search for content, and fetch web content.

When you need to use a tool, format your response with XML like this:

<function_calls>
<invoke tool="tool_name">
<parameters>
<param1>value1</param1>
<param2>value2</param2>
</parameters>
</invoke>
</function_calls>

Available tools:
- list_files: List files and directories in a path
- read_file: Read contents of one or more files
- edit_file: Edit or create a file with new content
- grep_files: Search for patterns in files
- fetch_url: Fetch content from a URL

Always be helpful and provide clear explanations of what you're doing."""

    agent = Agent(
        name="Code Agent",
        description="AI assistant for code and file operations",
        system_prompt=system_prompt,
        system_variables={"work_path": work_path},
        provider=provider,
    )

    # Add file system tools
    agent.add_tool(create_list_files_tool(work_path))
    agent.add_tool(create_read_file_tool(work_path))
    agent.add_tool(create_edit_file_tool(work_path))
    agent.add_tool(create_grep_files_tool(work_path))
    agent.add_tool(create_fetch_url_tool())

    return agent


def create_list_files_tool(work_path: str) -> Tool:
    """Create a list files tool"""

    async def list_files(path: str = ".", recursive: bool = False) -> str:
        """List files and directories in a path"""
        try:
            path_obj = Path(path).resolve()
            if not path_obj.exists():
                return f"Error: Path '{path}' does not exist"

            if recursive:
                files = []
                for item in path_obj.rglob("*"):
                    if item.is_file():
                        files.append(f"  {item.relative_to(path_obj)}")
                    else:
                        files.append(f"📁 {item.relative_to(path_obj)}/")
                return f"Files in '{path}' (recursive):\n" + "\n".join(sorted(files))
            else:
                items = []
                for item in path_obj.iterdir():
                    if item.is_file():
                        items.append(f"  {item.name}")
                    else:
                        items.append(f"📁 {item.name}/")
                return f"Contents of '{path}':\n" + "\n".join(sorted(items))
        except Exception as e:
            return f"Error: {str(e)}"

    return WorkPathTool(
        name="list_files",
        prompt="List files and directories",
        description="List files and directories in a specified path",
        function=list_files,
        parameters=[
            ToolParameter(
                name="path",
                type="string",
                description="Path to list (default: current directory)",
                required=False,
                default=".",
            ),
            ToolParameter(
                name="recursive",
                type="boolean",
                description="List files recursively (default: false)",
                required=False,
                default=False,
            ),
        ],
        work_path=work_path,
    )


def create_read_file_tool(work_path: str) -> Tool:
    """Create a read file tool"""

    async def read_file(paths: str) -> str:
        """Read contents of one or more files"""
        try:
            path_list = [p.strip() for p in paths.split(",")]
            results = []

            for path in path_list:
                path_obj = Path(path).resolve()
                if not path_obj.exists():
                    results.append(f"Error: File '{path}' does not exist")
                    continue

                if not path_obj.is_file():
                    results.append(f"Error: '{path}' is not a file")
                    continue

                try:
                    content = path_obj.read_text(encoding="utf-8")
                    results.append(f"=== {path} ===\n{content}")
                except UnicodeDecodeError:
                    results.append(f"Error: Could not read '{path}' as text")

            return "\n\n".join(results)
        except Exception as e:
            return f"Error: {str(e)}"

    return WorkPathTool(
        name="read_file",
        prompt="Read file contents",
        description="Read contents of one or more files (comma-separated paths)",
        function=read_file,
        parameters=[
            ToolParameter(
                name="paths",
                type="string",
                description="Comma-separated list of file paths to read",
                required=True,
            ),
        ],
        work_path=work_path,
    )


def create_edit_file_tool(work_path: str) -> Tool:
    """Create an edit file tool"""

    async def edit_file(path: str, content: str) -> str:
        """Edit or create a file with new content"""
        try:
            path_obj = Path(path).resolve()

            # Create parent directories if they don't exist
            path_obj.parent.mkdir(parents=True, exist_ok=True)

            # Write the content
            path_obj.write_text(content, encoding="utf-8")

            action = "updated" if path_obj.exists() else "created"
            return f"File '{path}' {action} successfully"
        except Exception as e:
            return f"Error: {str(e)}"

    return WorkPathTool(
        name="edit_file",
        prompt="Edit or create a file",
        description="Edit an existing file or create a new one with specified content",
        function=edit_file,
        parameters=[
            ToolParameter(
                name="path",
                type="string",
                description="Path to the file to edit or create",
                required=True,
            ),
            ToolParameter(
                name="content",
                type="string",
                description="Content to write to the file",
                required=True,
            ),
        ],
        work_path=work_path,
    )


def create_grep_files_tool(work_path: str) -> Tool:
    """Create a grep files tool"""

    async def grep_files(pattern: str, path: str = ".", file_pattern: str = "*") -> str:
        """Search for patterns in files"""
        try:
            import re

            path_obj = Path(path).resolve()
            if not path_obj.exists():
                return f"Error: Path '{path}' does not exist"

            results = []
            regex = re.compile(pattern, re.IGNORECASE)

            # Find files matching the pattern
            files = (
                list(path_obj.rglob(file_pattern))
                if any(c in file_pattern for c in "*?[]")
                else path_obj.rglob("*")
            )

            for file_path in files:
                if not file_path.is_file():
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8")
                    lines = content.splitlines()

                    for line_num, line in enumerate(lines, 1):
                        if regex.search(line):
                            results.append(
                                f"{file_path.relative_to(path_obj)}:{line_num}: {line}"
                            )

                except (UnicodeDecodeError, PermissionError):
                    continue

            if not results:
                return f"No matches found for pattern '{pattern}' in '{path}'"

            return f"Matches for '{pattern}' in '{path}':\n" + "\n".join(
                results[:50]
            )  # Limit to 50 results
        except Exception as e:
            return f"Error: {str(e)}"

    return WorkPathTool(
        name="grep_files",
        prompt="Search for patterns in files",
        description="Search for text patterns in files using regex",
        function=grep_files,
        parameters=[
            ToolParameter(
                name="pattern",
                type="string",
                description="Regex pattern to search for",
                required=True,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Path to search in (default: current directory)",
                required=False,
                default=".",
            ),
            ToolParameter(
                name="file_pattern",
                type="string",
                description="File pattern to match (default: *)",
                required=False,
                default="*",
            ),
        ],
        work_path=work_path,
    )


def create_fetch_url_tool() -> Tool:
    """Create a fetch URL tool"""

    async def fetch_url(url: str) -> str:
        """Fetch content from a URL"""
        import urllib

        try:
            request = urllib.request.Request(url)
            with urllib.request.urlopen(request, timeout=30) as response:
                content = response.read().decode("utf-8", errors="ignore")
                return f"Content from {url}:\n{content[:5000]}{'...' if len(content) > 5000 else ''}"
        except urllib.error.HTTPError as e:
            return f"Error: HTTP {e.code} - {e.reason}"
        except Exception as e:
            return f"Error fetching URL: {str(e)}"

    return Tool(
        name="fetch_url",
        prompt="Fetch content from URL",
        description="Fetch and display content from a web URL",
        function=fetch_url,
        parameters=[
            ToolParameter(
                name="url",
                type="string",
                description="URL to fetch content from",
                required=True,
            ),
        ],
    )
