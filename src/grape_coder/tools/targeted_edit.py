import os
from pathlib import Path
from typing import Optional, Union

from strands import tool

from grape_coder.tools.work_path import _work_path


def _resolve_path(path: str) -> Path:
    """Resolve path relative to work_path"""
    if not os.path.isabs(path):
        path = os.path.join(_work_path, path)
    return Path(path).resolve()


def _check_file_type(path: str, allowed_extensions: tuple) -> Optional[str]:
    """Check if file has allowed extension, return error message if not"""
    if not path.endswith(allowed_extensions):
        allowed = ", ".join(allowed_extensions)
        return f"ERROR: Only files with extensions {allowed} are allowed. The path '{path}' does not have an allowed extension."
    return None


@tool
def str_replace(path: str, old_str: str, new_str: str) -> str:
    """Replace exact string in a file with new content.

    Args:
        path: Path to the file to edit
        old_str: The exact text to find and replace
        new_str: The replacement text
    """
    try:
        resolved_path = _resolve_path(path)

        if not resolved_path.exists():
            return f"Error: File '{path}' does not exist. Use edit_file to create new files."

        if not resolved_path.is_file():
            return f"Error: '{path}' is not a file"

        content = resolved_path.read_text(encoding="utf-8")

        if old_str not in content:
            return f"Error: Could not find the exact text to replace in '{path}'. Make sure old_str matches the file content exactly."

        new_content = content.replace(old_str, new_str)
        resolved_path.write_text(new_content, encoding="utf-8")

        return f"Successfully replaced text in '{path}'"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def pattern_replace(path: str, pattern: str, new_str: str) -> str:
    """Replace text in a file using regex pattern.

    Args:
        path: Path to the file to edit
        pattern: Regex pattern to match
        new_str: The replacement text
    """
    try:
        import re

        resolved_path = _resolve_path(path)

        if not resolved_path.exists():
            return f"Error: File '{path}' does not exist. Use edit_file to create new files."

        if not resolved_path.is_file():
            return f"Error: '{path}' is not a file"

        content = resolved_path.read_text(encoding="utf-8")

        try:
            new_content = re.sub(pattern, new_str, content, flags=re.IGNORECASE)
        except re.error as e:
            return f"Error: Invalid regex pattern: {str(e)}"

        resolved_path.write_text(new_content, encoding="utf-8")

        return f"Successfully replaced pattern in '{path}'"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def insert_text(path: str, insert_line: Union[str, int], new_str: str) -> str:
    """Insert text after a specified line in a file.

    Args:
        path: Path to the file to edit
        insert_line: Line number (0-based) or search text to find the line after which to insert
        new_str: The text to insert
    """
    try:
        resolved_path = _resolve_path(path)

        if not resolved_path.exists():
            return f"Error: File '{path}' does not exist. Use edit_file to create new files."

        if not resolved_path.is_file():
            return f"Error: '{path}' is not a file"

        content = resolved_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        if isinstance(insert_line, str):
            insert_idx = -1
            for i, line in enumerate(lines):
                if insert_line in line:
                    insert_idx = i
                    break
            if insert_idx == -1:
                return (
                    f"Error: Could not find line containing '{insert_line}' in '{path}'"
                )
        else:
            if insert_line < 0 or insert_line >= len(lines):
                return f"Error: Line number {insert_line} is out of range (file has {len(lines)} lines, 0-based)"
            insert_idx = insert_line

        lines.insert(insert_idx + 1, new_str)
        new_content = "\n".join(lines)
        resolved_path.write_text(new_content, encoding="utf-8")

        return f"Successfully inserted text after line {insert_idx} in '{path}'"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def str_replace_html(path: str, old_str: str, new_str: str) -> str:
    """Replace exact string in an HTML file. Only .html files allowed."""
    error = _check_file_type(path, (".html",))
    if error:
        return error
    return str_replace(path, old_str, new_str)


@tool
def pattern_replace_html(path: str, pattern: str, new_str: str) -> str:
    """Replace text in an HTML file using regex. Only .html files allowed."""
    error = _check_file_type(path, (".html",))
    if error:
        return error
    return pattern_replace(path, pattern, new_str)


@tool
def insert_text_html(path: str, insert_line: Union[str, int], new_str: str) -> str:
    """Insert text in an HTML file. Only .html files allowed."""
    error = _check_file_type(path, (".html",))
    if error:
        return error
    return insert_text(path, insert_line, new_str)


@tool
def str_replace_js(path: str, old_str: str, new_str: str) -> str:
    """Replace exact string in a JavaScript file. Only .js files allowed."""
    error = _check_file_type(path, (".js",))
    if error:
        return error
    return str_replace(path, old_str, new_str)


@tool
def pattern_replace_js(path: str, pattern: str, new_str: str) -> str:
    """Replace text in a JavaScript file using regex. Only .js files allowed."""
    error = _check_file_type(path, (".js",))
    if error:
        return error
    return pattern_replace(path, pattern, new_str)


@tool
def insert_text_js(path: str, insert_line: Union[str, int], new_str: str) -> str:
    """Insert text in a JavaScript file. Only .js files allowed."""
    error = _check_file_type(path, (".js",))
    if error:
        return error
    return insert_text(path, insert_line, new_str)


@tool
def str_replace_css(path: str, old_str: str, new_str: str) -> str:
    """Replace exact string in a CSS file. Only .css files allowed."""
    error = _check_file_type(path, (".css",))
    if error:
        return error
    return str_replace(path, old_str, new_str)


@tool
def pattern_replace_css(path: str, pattern: str, new_str: str) -> str:
    """Replace text in a CSS file using regex. Only .css files allowed."""
    error = _check_file_type(path, (".css",))
    if error:
        return error
    return pattern_replace(path, pattern, new_str)


@tool
def insert_text_css(path: str, insert_line: Union[str, int], new_str: str) -> str:
    """Insert text in a CSS file. Only .css files allowed."""
    error = _check_file_type(path, (".css",))
    if error:
        return error
    return insert_text(path, insert_line, new_str)


@tool
def str_replace_svg(path: str, old_str: str, new_str: str) -> str:
    """Replace exact string in an SVG file. Only .svg files allowed."""
    error = _check_file_type(path, (".svg",))
    if error:
        return error
    return str_replace(path, old_str, new_str)


@tool
def pattern_replace_svg(path: str, pattern: str, new_str: str) -> str:
    """Replace text in an SVG file using regex. Only .svg files allowed."""
    error = _check_file_type(path, (".svg",))
    if error:
        return error
    return pattern_replace(path, pattern, new_str)


@tool
def insert_text_svg(path: str, insert_line: Union[str, int], new_str: str) -> str:
    """Insert text in an SVG file. Only .svg files allowed."""
    error = _check_file_type(path, (".svg",))
    if error:
        return error
    return insert_text(path, insert_line, new_str)


@tool
def str_replace_md(path: str, old_str: str, new_str: str) -> str:
    """Replace exact string in a Markdown file. Only .md files allowed."""
    error = _check_file_type(path, (".md",))
    if error:
        return error
    return str_replace(path, old_str, new_str)


@tool
def pattern_replace_md(path: str, pattern: str, new_str: str) -> str:
    """Replace text in a Markdown file using regex. Only .md files allowed."""
    error = _check_file_type(path, (".md",))
    if error:
        return error
    return pattern_replace(path, pattern, new_str)


@tool
def insert_text_md(path: str, insert_line: Union[str, int], new_str: str) -> str:
    """Insert text in a Markdown file. Only .md files allowed."""
    error = _check_file_type(path, (".md",))
    if error:
        return error
    return insert_text(path, insert_line, new_str)


@tool
def str_replace_json(path: str, old_str: str, new_str: str) -> str:
    """Replace exact string in a JSON file. Only .json files allowed."""
    error = _check_file_type(path, (".json",))
    if error:
        return error
    return str_replace(path, old_str, new_str)


@tool
def pattern_replace_json(path: str, pattern: str, new_str: str) -> str:
    """Replace text in a JSON file using regex. Only .json files allowed."""
    error = _check_file_type(path, (".json",))
    if error:
        return error
    return pattern_replace(path, pattern, new_str)


@tool
def insert_text_json(path: str, insert_line: Union[str, int], new_str: str) -> str:
    """Insert text in a JSON file. Only .json files allowed."""
    error = _check_file_type(path, (".json",))
    if error:
        return error
    return insert_text(path, insert_line, new_str)


@tool
def str_replace_code(path: str, old_str: str, new_str: str) -> str:
    """Replace exact string in a web file (.html, .js, .css, .svg, .json, .md)."""
    error = _check_file_type(path, (".html", ".js", ".css", ".svg", ".json", ".md"))
    if error:
        return error
    return str_replace(path, old_str, new_str)


@tool
def pattern_replace_code(path: str, pattern: str, new_str: str) -> str:
    """Replace text in a web file using regex (.html, .js, .css, .svg, .json, .md)."""
    error = _check_file_type(path, (".html", ".js", ".css", ".svg", ".json", ".md"))
    if error:
        return error
    return pattern_replace(path, pattern, new_str)


@tool
def insert_text_code(path: str, insert_line: Union[str, int], new_str: str) -> str:
    """Insert text in a web file (.html, .js, .css, .svg, .json, .md)."""
    error = _check_file_type(path, (".html", ".js", ".css", ".svg", ".json", ".md"))
    if error:
        return error
    return insert_text(path, insert_line, new_str)
