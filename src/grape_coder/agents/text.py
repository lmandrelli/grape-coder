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
- generate_heading: Create headings and titles
- generate_paragraph: Create body text and descriptions
- generate_cta: Create call-to-action text
- generate_list_content: Create list items (features, benefits, etc.)
- generate_meta_content: Create SEO meta content (title, description)
- get_all_text: Get all generated text content

Best practices:
- Write clear, concise, and engaging copy
- Use active voice and action verbs
- Tailor tone to the target audience
- Include relevant keywords naturally
- Keep accessibility in mind (clear language)
- Create scannable content with varied sentence lengths

Always match the brand voice and target audience specified."""

    agent = Agent(
        model=model,
        tools=[
        ],
        system_prompt=system_prompt,
        name="Text Agent",
        description="AI assistant for generating web page text content",
    )

    return agent
