"""Agent pour créer des classes CSS et composants HTML réutilisables"""

import os
from typing import List, Dict, Optional

from dotenv import load_dotenv
from strands import Agent
from strands.models.mistral import MistralModel
from strands.tools import tool

load_dotenv()

# Storage for created classes
_class_registry: Dict[str, Dict] = {}


def create_class_agent() -> Agent:
    """Create an agent for creating reusable CSS classes and HTML components"""

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

    # Create agent with class creation tools
    system_prompt = """You are a CSS class and HTML component specialist.
Your role is to create reusable, well-structured CSS classes and HTML component templates.

Available tools:
- edit_file: Create or update files with CSS/HTML content
- read_file: Read existing files to check or modify them
- list_created_files: List all files created by this agent

Best practices:
- Use BEM naming convention (block__element--modifier)
- Create mobile-first responsive classes
- Keep classes single-purpose and composable
- Document each class with its purpose and usage
- Organize files logically (e.g., components/, utilities/, layouts/)

Always output clean, well-documented code."""

    agent = Agent(
        model=model,
        tools=[
            edit_file,
            read_file,
            list_created_files,
        ],
        system_prompt=system_prompt,
        name="Class Agent",
        description="AI assistant for creating reusable CSS classes and components",
    )

    return agent


@tool
def edit_file(path: str, content: str) -> str:
    """
    Create or update a file with CSS classes or HTML components.
    
    Args:
        path: The file path where to write (relative to project root or absolute)
        content: The content to write (CSS, HTML, or mixed)
    
    Returns:
        Success message with file path
        
    Examples:
        - edit_file("styles/components.css", ".button { ... }")
        - edit_file("components/card.html", "<div class='card'>...</div>")
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
        file_extension = os.path.splitext(path)[1]
        _class_registry[path] = {
            'path': path,
            'type': file_extension,
            'size': len(content),
        }
        
        return f"✅ File successfully created/updated: {path} ({len(content)} bytes)"
        
    except Exception as e:
        return f"❌ Error writing file {path}: {str(e)}"


@tool
def read_file(path: str) -> str:
    """
    Read the content of an existing file.
    
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
        
        return f"📄 Content of {path}:\n\n{content}"
        
    except Exception as e:
        return f"❌ Error reading file {path}: {str(e)}"


@tool
def list_created_files() -> str:
    """
    List all files created by this agent.
    
    Returns:
        List of created files with their details
    """
    if not _class_registry:
        return "No files created yet."
    
    result = "📁 Created files:\n\n"
    for path, info in _class_registry.items():
        result += f"- {path}\n"
        result += f"  Type: {info['type']}\n"
        result += f"  Size: {info['size']} bytes\n\n"
    
    return result
    