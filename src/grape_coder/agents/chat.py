import os

from dotenv import load_dotenv

from ..models import Agent, LLMModel, ToolParameter
from ..providers import OpenAIProvider
from ..tools import Tool

load_dotenv()


def create_chat_agent() -> Agent:
    """Create a chat agent with basic tools"""

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
    system_prompt = """You are a helpful AI assistant with access to various tools.
When you need to use a tool, format your response with XML like this:

<function_calls>
<invoke tool="tool_name">
<parameters>
<param1>value1</param1>
<param2>value2</param2>
</parameters>
</invoke>
</function_calls>

Always be helpful, accurate, and concise. If you don't know something, admit it and suggest alternatives."""

    agent = Agent(
        name="Grape Coder",
        description="AI assistant with tool capabilities",
        system_prompt=system_prompt,
        provider=provider,
    )

    # Add some basic tools
    agent.add_tool(create_calculator_tool())
    agent.add_tool(create_time_tool())
    agent.add_tool(create_echo_tool())

    return agent


def create_calculator_tool() -> Tool:
    """Create a calculator tool"""

    async def calculator(expression: str) -> str:
        """Evaluate a mathematical expression safely"""
        try:
            # Simple and safe evaluation
            allowed_chars = set("0123456789+-*/().() ")
            if not all(c in allowed_chars for c in expression):
                return "Error: Invalid characters in expression"

            result = eval(expression)
            return f"Result: {result}"
        except Exception as e:
            return f"Error: {str(e)}"

    return Tool(
        name="calculator",
        prompt="Calculate mathematical expressions",
        description="Evaluates mathematical expressions safely",
        function=calculator,
        parameters=[
            ToolParameter(
                name="expression",
                type="string",
                description="Mathematical expression to evaluate (e.g., '2 + 3 * 4')",
                required=True,
            )
        ],
    )


def create_time_tool() -> Tool:
    """Create a time tool"""
    import datetime

    async def get_time(format: str = "%Y-%m-%d %H:%M:%S") -> str:
        """Get current time"""
        try:
            current_time = datetime.datetime.now()
            return current_time.strftime(format)
        except Exception as e:
            return f"Error: {str(e)}"

    return Tool(
        name="get_time",
        prompt="Get current time",
        description="Returns the current date and time in a specified format",
        function=get_time,
        parameters=[
            ToolParameter(
                name="format",
                type="string",
                description="DateTime format string (default: '%Y-%m-%d %H:%M:%S')",
                required=False,
                default="%Y-%m-%d %H:%M:%S",
            )
        ],
    )


def create_echo_tool() -> Tool:
    """Create an echo tool"""

    async def echo(message: str) -> str:
        """Echo back the message"""
        return f"Echo: {message}"

    return Tool(
        name="echo",
        prompt="Echo back the provided message",
        description="Returns the exact message that was provided",
        function=echo,
        parameters=[
            ToolParameter(
                name="message",
                type="string",
                description="The message to echo back",
                required=True,
            )
        ],
    )
