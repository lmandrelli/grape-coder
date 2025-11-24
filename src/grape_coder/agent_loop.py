import asyncio
import os

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from .models import Agent, MessageType
from .providers import MockProvider, OpenAIProvider
from .tools import BaseTool


class AgentLoop:
    """Main agent interaction loop"""

    def __init__(self, agent: Agent):
        self.agent = agent
        self.console = Console()
        self.running = False

    async def start(self) -> None:
        """Start the agent interaction loop"""
        self.running = True
        self.console.print(
            Panel(
                f"[bold green]Agent {self.agent.name or 'System'}[/bold green]\n"
                f"{self.agent.description or 'Ready to help!'}\n\n"
                f"Type 'help' for commands, 'quit' to exit.",
                title="🤖 Grape Coder Agent",
                border_style="green",
            )
        )

        while self.running:
            try:
                # Get user input
                user_input = Prompt.ask(
                    "[bold blue]You[/bold blue]", console=self.console
                )

                if not user_input.strip():
                    continue

                # Handle special commands
                if await self.handle_command(user_input):
                    continue

                # Process user input through agent
                self.console.print("[yellow]Thinking...[/yellow]")
                response = await self.agent.process_user_input(user_input)

                # Display agent response
                self.console.print(
                    Panel(
                        response,
                        title="[bold green]Agent[/bold green]",
                        border_style="green",
                    )
                )

            except KeyboardInterrupt:
                self.console.print(
                    "\n[yellow]Interrupted. Type 'quit' to exit.[/yellow]"
                )
            except Exception as e:
                self.console.print(f"[red]Error: {str(e)}[/red]")

    async def handle_command(self, user_input: str) -> bool:
        """Handle special commands"""
        command = user_input.lower().strip()

        if command in ["quit", "exit", "q"]:
            self.running = False
            self.console.print("[yellow]Goodbye![/yellow]")
            return True

        elif command == "help":
            self.show_help()
            return True

        elif command == "clear":
            self.agent.clear_history()
            self.console.print("[yellow]History cleared.[/yellow]")
            return True

        elif command == "tools":
            tools_info = self.agent.get_tools_info()
            self.console.print(
                Panel(
                    tools_info,
                    title="[bold cyan]Available Tools[/bold cyan]",
                    border_style="cyan",
                )
            )
            return True

        elif command == "history":
            self.show_history()
            return True

        return False

    def show_help(self) -> None:
        """Show help information"""
        help_text = """
[bold]Available Commands:[/bold]
• [cyan]help[/cyan] - Show this help message
• [cyan]clear[/cyan] - Clear conversation history
• [cyan]tools[/cyan] - Show available tools
• [cyan]history[/cyan] - Show conversation history
• [cyan]quit[/cyan] or [cyan]exit[/cyan] - Exit the agent

[bold]Usage:[/bold]
Simply type your message and press Enter. The agent will respond and can use tools automatically.
        """
        self.console.print(Panel(help_text, title="Help", border_style="blue"))

    def show_history(self) -> None:
        """Show conversation history"""
        if not self.agent.history.messages:
            self.console.print("[yellow]No conversation history.[/yellow]")
            return

        history_text = ""
        for i, msg in enumerate(self.agent.history.messages):
            if msg.type == MessageType.SYSTEM:
                continue  # Skip system messages

            sender = "You" if msg.type == MessageType.USER else "Agent"
            color = "blue" if msg.type == MessageType.USER else "green"

            history_text += f"[{color}]{sender}[/{color}]: {msg.content}\n\n"

        self.console.print(
            Panel(
                history_text.strip(),
                title="Conversation History",
                border_style="yellow",
            )
        )


def create_default_agent() -> Agent:
    """Create a default agent with basic tools"""

    # Create provider (use mock for testing, OpenAI for production)
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        provider = OpenAIProvider(model_name="gpt-3.5-turbo", api_key=api_key)
    else:
        provider = MockProvider(model_name="mock")

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


def create_calculator_tool() -> BaseTool:
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

    return BaseTool(
        name="calculator",
        prompt="Calculate mathematical expressions",
        function=calculator,
        description="Evaluates mathematical expressions like '2+2' or '10*5'",
    )


def create_time_tool() -> BaseTool:
    """Create a time tool"""
    import datetime

    async def get_time(format: str = "%Y-%m-%d %H:%M:%S") -> str:
        """Get current time"""
        try:
            current_time = datetime.datetime.now()
            return current_time.strftime(format)
        except Exception as e:
            return f"Error: {str(e)}"

    return BaseTool(
        name="get_time",
        prompt="Get current time",
        function=get_time,
        description="Returns the current date and time",
    )


def create_echo_tool() -> BaseTool:
    """Create an echo tool"""

    async def echo(message: str) -> str:
        """Echo back the message"""
        return f"Echo: {message}"

    return BaseTool(
        name="echo",
        prompt="Echo a message",
        function=echo,
        description="Repeats back the given message",
    )


async def main():
    """Main entry point for the agent system"""
    agent = create_default_agent()
    loop = AgentLoop(agent)
    await loop.start()


if __name__ == "__main__":
    asyncio.run(main())
