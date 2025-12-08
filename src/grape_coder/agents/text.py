"""Agent pour générer du contenu textuel en lien avec le sujet"""

import os
from typing import List, Dict, Optional

from dotenv import load_dotenv
from strands import Agent
from strands.models.mistral import MistralModel
from strands.tools import tool

load_dotenv()

# Storage for generated text content
_text_registry: Dict[str, Dict] = {}


def create_text_agent() -> Agent:
    """Create an agent for generating text content for web pages"""

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
- edit_file: Create or update text content files
- read_file: Read existing text files to check or modify them
- list_created_files: List all text files created by this agent
- append_to_file: Append text content to an existing file

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
            edit_file,
            read_file,
            list_created_files,
            append_to_file,
        ],
        system_prompt=system_prompt,
        name="Text Agent",
        description="AI assistant for generating web page text content",
    )

    return agent


@tool
def edit_file(path: str, content: str) -> str:
    """
    Create or update a text content file.
    
    Args:
        path: The file path where to write (relative to project root or absolute)
        content: The text content to write
    
    Returns:
        Success message with file path
        
    Examples:
        - edit_file("content/headings.txt", "Welcome to Our Website")
        - edit_file("content/hero.txt", "Discover amazing products...")
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
        _text_registry[path] = {
            'path': path,
            'size': len(content),
            'lines': content.count('\n') + 1,
            'words': len(content.split()),
        }
        
        return f"✅ Text file successfully created/updated: {path} ({_text_registry[path]['words']} words, {_text_registry[path]['lines']} lines)"
        
    except Exception as e:
        return f"❌ Error writing text file {path}: {str(e)}"


@tool
def read_file(path: str) -> str:
    """
    Read the content of an existing text file.
    
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
        
        words = len(content.split())
        lines = content.count('\n') + 1
        return f"📄 Content of {path} ({words} words, {lines} lines):\n\n{content}"
        
    except Exception as e:
        return f"❌ Error reading file {path}: {str(e)}"


@tool
def append_to_file(path: str, content: str) -> str:
    """
    Append text content to an existing file.
    
    Args:
        path: The file path to append to
        content: The text content to append
    
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
            
        _text_registry[path] = {
            'path': path,
            'size': len(new_content),
            'lines': new_content.count('\n') + 1,
            'words': len(new_content.split()),
        }
        
        return f"✅ Content appended to {path} (now {_text_registry[path]['words']} words, {_text_registry[path]['lines']} lines)"
        
    except Exception as e:
        return f"❌ Error appending to file {path}: {str(e)}"


@tool
def list_created_files() -> str:
    """
    List all text files created by this agent.
    
    Returns:
        List of created files with their details
    """
    if not _text_registry:
        return "No text files created yet."
    
    result = "📁 Created text files:\n\n"
    for path, info in _text_registry.items():
        result += f"- {path}\n"
        result += f"  Words: {info['words']}\n"
        result += f"  Lines: {info['lines']}\n"
        result += f"  Size: {info['size']} bytes\n\n"
    
    return result
