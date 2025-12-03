import os
from typing import List, Optional

import litellm
from pydantic import ConfigDict

from .models import Message, MessageType, Provider, Tool


class LiteLLMProvider(Provider):
    """LiteLLM provider supporting multiple LLM providers with unified interface"""

    def __init__(self, **data):
        super().__init__(**data)
        # Set API key based on provider type
        if not self.api_key:
            # Try different environment variables based on model prefix
            if self.model.name.startswith("openai/"):
                self.api_key = os.getenv("OPENAI_API_KEY")
            elif self.model.name.startswith("anthropic/"):
                self.api_key = os.getenv("ANTHROPIC_API_KEY")
            elif self.model.name.startswith("openrouter/"):
                self.api_key = os.getenv("OPENROUTER_API_KEY")
            else:
                self.api_key = os.getenv("OPENAI_API_KEY")  # default
            
        if not self.api_key:
            raise ValueError(
                "API key is required. Set appropriate environment variable (OPENAI_API_KEY, ANTHROPIC_API_KEY, OPENROUTER_API_KEY, etc.) or pass api_key parameter."
            )

    async def generate(
        self, messages: List[Message], tools: Optional[List[Tool]] = None
    ) -> str:

        # Convert messages to OpenAI format
        openai_messages = []
        for msg in messages:
            if msg.type.value == "call_function":
                # Skip function call messages for now, will handle in XML implementation
                continue
            elif msg.type.value == "result_function":
                # Add function result as assistant message
                openai_messages.append({"role": "assistant", "content": msg.content})
            else:
                openai_messages.append(
                    {
                        "role": "assistant"
                        if msg.type.value
                        == MessageType.AGENT  # there is no agent role in OpenAI standard
                        else msg.type.value,
                        "content": msg.content,
                    }
                )

        # Prepare tools for OpenAI if provided
        openai_tools = []
        if tools:
            for tool in tools:
                # Build parameters schema
                properties = {}
                required = []

                for param in tool.parameters:
                    properties[param.name] = {
                        "type": param.type,
                        "description": param.description or "",
                    }
                    if param.default is not None:
                        properties[param.name]["default"] = param.default
                    if param.required:
                        required.append(param.name)

                openai_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or tool.prompt,
                            "parameters": {
                                "type": "object",
                                "properties": properties,
                                "required": required,
                            },
                        },
                    }
                )

        try:
            # Use LiteLLM completion with async support
            response = await litellm.acompletion(
                model=self.model.name,
                messages=openai_messages,
                tools=openai_tools,
                tool_choice="auto",
                api_key=self.api_key,
                base_url=self.base_url,
            )

            return response.choices[0].message.content or ""

        except Exception as e:
            raise RuntimeError(f"LiteLLM API error: {str(e)}")


class MockProvider(Provider):
    """Mock provider for testing purposes"""

    async def generate(
        self, messages: List[Message], tools: Optional[List[Tool]] = None
    ) -> str:
        # Simple mock response
        if messages and messages[-1].type.value == "user":
            user_input = messages[-1].content.lower()
            if "hello" in user_input or "hi" in user_input:
                return "Hello! How can I help you today?"
            elif "help" in user_input:
                return "I'm here to help! What do you need assistance with?"
            else:
                return f"I received your message: {messages[-1].content}"
        return "I'm ready to assist you!"
