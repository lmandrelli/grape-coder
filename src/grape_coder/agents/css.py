"""Agent pour créer du contenu CSS et des styles visuels"""

import os
from typing import List, Dict, Optional

from dotenv import load_dotenv
from strands import Agent
from strands.models.mistral import MistralModel
from strands.tools import tool

load_dotenv()

# Storage for CSS styles
_css_registry: Dict[str, Dict] = {}


def create_css_agent() -> Agent:
    """Create an agent for generating CSS styles and visual design"""

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

    # Create agent with CSS styling tools
    system_prompt = """You are a CSS styling specialist.
Your role is to create beautiful, modern, and responsive CSS styles.

Available tools:
- edit_file: Create or update CSS files
- read_file: Read existing CSS files to check or modify them
- list_created_files: List all CSS files created by this agent
- append_to_file: Append CSS rules to an existing file

Best practices:
- Use CSS custom properties (variables) for reusability
- Create mobile-first responsive designs
- Follow accessibility guidelines (contrast ratios, focus states)
- Use modern CSS features (flexbox, grid, clamp)
- Keep specificity low and avoid !important
- Organize CSS with comments and sections

Always output clean, well-organized CSS with comments."""

    agent = Agent(
        model=model,
        tools=[
            edit_file,
            read_file,
            list_created_files,
            append_to_file,
        ],
        system_prompt=system_prompt,
        name="CSS Agent",
        description="AI assistant for creating CSS styles and visual design",
    )

    return agent


@tool
def edit_file(path: str, content: str) -> str:
    """
    Create or update a CSS file.
    
    Args:
        path: The file path where to write (relative to project root or absolute)
        content: The CSS content to write
    
    Returns:
        Success message with file path
        
    Examples:
        - edit_file("styles/main.css", ":root { --primary: #007bff; }")
        - edit_file("styles/components/button.css", ".btn { ... }")
    """
    try:
        # Ensure the directory exists
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            
        # Write the content to the file
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Store in registry for tracking
        _css_registry[path] = {
            'path': path,
            'size': len(content),
            'lines': content.count('\n') + 1,
        }
        
        return f"✅ CSS file successfully created/updated: {path} ({len(content)} bytes, {_css_registry[path]['lines']} lines)"
        
    except Exception as e:
        return f"❌ Error writing CSS file {path}: {str(e)}"


@tool
def read_file(path: str) -> str:
    """
    Read the content of an existing CSS file.
    
    Args:
        path: The file path to read
    
    Returns:
        The file content or error message
    """
    try:
        if not os.path.exists(path):
            return f"❌ File not found: {path}"
            
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.count('\n') + 1
        return f"📄 Content of {path} ({lines} lines):\n\n{content}"
        
    except Exception as e:
        return f"❌ Error reading file {path}: {str(e)}"


@tool
def append_to_file(path: str, content: str) -> str:
    """
    Append CSS rules to an existing file.
    
    Args:
        path: The file path to append to
        content: The CSS content to append
    
    Returns:
        Success message with file path
    """
    try:
        if not os.path.exists(path):
            return f"❌ File not found: {path}. Use edit_file to create it first."
            
        # Append the content to the file
        with open(path, 'a', encoding='utf-8') as f:
            f.write('\n\n')
            f.write(content)
        
        # Update registry
        with open(path, 'r', encoding='utf-8') as f:
            new_content = f.read()
            
        _css_registry[path] = {
            'path': path,
            'size': len(new_content),
            'lines': new_content.count('\n') + 1,
        }
        
        return f"✅ Content appended to {path} (now {_css_registry[path]['size']} bytes, {_css_registry[path]['lines']} lines)"
        
    except Exception as e:
        return f"❌ Error appending to file {path}: {str(e)}"


@tool
def list_created_files() -> str:
    """
    List all CSS files created by this agent.
    
    Returns:
        List of created files with their details
    """
    if not _css_registry:
        return "No CSS files created yet."
    
    result = "📁 Created CSS files:\n\n"
    for path, info in _css_registry.items():
        result += f"- {path}\n"
        result += f"  Size: {info['size']} bytes\n"
        result += f"  Lines: {info['lines']}\n\n"
    
    return result