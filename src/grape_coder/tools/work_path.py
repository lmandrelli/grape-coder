import os
from pathlib import Path

from strands.tools import tool

# Global variable to store work_path for tools
_work_path = "."


def set_work_path(path: str) -> None:
    """Set the working path for all tools"""
    global _work_path
    _work_path = path


@tool
def list_files(path: str = ".", recursive: bool = False) -> str:
    """List files and directories in a path

    Args:
        path: Path to list (default: current directory)
        recursive: List files recursively (default: false)
    """
    try:
        # Resolve path relative to work_path
        if not os.path.isabs(path):
            path = os.path.join(_work_path, path)

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


@tool
def read_file(path: str) -> str:
    """Read contents of a file

    Args:
        path: Path to the file to read
    """
    try:
        # Resolve path relative to work_path
        if not os.path.isabs(path):
            path = os.path.join(_work_path, path)

        path_obj = Path(path).resolve()
        if not path_obj.exists():
            return f"Error: File '{path}' does not exist"

        if not path_obj.is_file():
            return f"Error: '{path}' is not a file"

        try:
            content = path_obj.read_text(encoding="utf-8")
            return content
        except UnicodeDecodeError:
            return f"Error: Could not read '{path}' as text"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def edit_file(path: str, content: str) -> str:
    """Edit or create a file with new content

    Args:
        path: Path to the file to edit or create
        content: Content to write to the file
    """
    try:
        # Resolve path relative to work_path
        if not os.path.isabs(path):
            path = os.path.join(_work_path, path)

        path_obj = Path(path).resolve()

        # Create parent directories if they don't exist
        path_obj.parent.mkdir(parents=True, exist_ok=True)

        # Write the content
        path_obj.write_text(content, encoding="utf-8")

        action = "updated" if path_obj.exists() else "created"
        return f"File '{path}' {action} successfully"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def grep_files(pattern: str, path: str = ".", file_pattern: str = "*") -> str:
    """Search for patterns in files

    Args:
        pattern: Regex pattern to search for
        path: Path to search in (default: current directory)
        file_pattern: File pattern to match (default: *)
    """
    try:
        import re

        # Resolve path relative to work_path
        if not os.path.isabs(path):
            path = os.path.join(_work_path, path)

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


@tool
def glob_files(pattern: str, path: str = ".") -> str:
    """Find files using glob patterns

    Args:
        pattern: Glob pattern to match files (e.g., "*.py", "**/*.js", "src/**/*.ts")
        path: Path to search in (default: current directory)
    """
    try:
        # Resolve path relative to work_path
        if not os.path.isabs(path):
            path = os.path.join(_work_path, path)

        path_obj = Path(path).resolve()
        if not path_obj.exists():
            return f"Error: Path '{path}' does not exist"

        # Use glob to find matching files
        matches = list(path_obj.glob(pattern))

        if not matches:
            return f"No files found matching pattern '{pattern}' in '{path}'"

        # Sort results and format output
        results = []
        for match in sorted(matches):
            if match.is_file():
                results.append(f"  {match.relative_to(path_obj)}")
            else:
                results.append(f"📁 {match.relative_to(path_obj)}/")

        return f"Files matching '{pattern}' in '{path}':\n" + "\n".join(results)
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def get_agent_tasks(xml_distribution: str, agent_name: str) -> str:
    """Extract tasks for a given agent from an XML task distribution.

    Args:
        xml_distribution: XML string containing task_distribution root and agent sections
        agent_name: Tag name of the agent section (e.g. 'class_agent')

    Returns:
        A newline-separated string of tasks for the agent, or an error message.
    """
    try:
        import xml.etree.ElementTree as ET

        root = ET.fromstring(xml_distribution)

        if root.tag != "task_distribution":
            return "Error: Root element must be 'task_distribution'"

        # Find the agent element by tag
        agent_elem = root.find(agent_name)
        if agent_elem is None:
            return f"No tasks found for agent '{agent_name}'"

        tasks = [t.text.strip() for t in agent_elem.findall("task") if t.text]
        if not tasks:
            return f"No tasks found for agent '{agent_name}'"

        return "\n".join(tasks)

    except ET.ParseError as e:
        return f"Error: Invalid XML format - {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"
