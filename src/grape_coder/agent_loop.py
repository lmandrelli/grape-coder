from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.panel import Panel

from .models import Agent, MessageType

load_dotenv()


class AgentLoop:
    """Main agent interaction loop"""

    def __init__(self, agent: Agent):
        self.agent = agent
        self.console = Console()
        self.running = False
        self.session = PromptSession()

    async def start(self) -> None:
        """Start the agent interaction loop"""
        self.running = True
        self.console.print(
            Panel(
                f"[bold green]Agent {self.agent.name or 'System'}[/bold green]\n"
                f"{self.agent.description or 'Ready to help!'}\n\n"
                f"Type '/help' for commands, '/quit' or Ctrl+C to exit.",
                title="🤖 Grape Coder Agent",
                border_style="green",
            )
        )

        while self.running:
            try:
                # Get user input using prompt_toolkit with styled prompt
                user_input = await self.session.prompt_async(
                    HTML("<b><ansiblue>You</ansiblue></b>: "),
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
                self.console.print("[bold green]Agent[/bold green]: " + response)

            except KeyboardInterrupt:
                # Clean exit on Ctrl+C
                self.running = False
                self.console.print("[yellow]Goodbye![/yellow]")
            except EOFError:
                # Clean exit on Ctrl+D
                self.running = False
                self.console.print("[yellow]Goodbye![/yellow]")
            except Exception as e:
                self.console.print(f"[red]Error: {str(e)}[/red]")

    async def handle_command(self, user_input: str) -> bool:
        """Handle special commands"""
        command = user_input.lower().strip()

        if command in ["/quit", "/exit", "/q"]:
            self.running = False
            self.console.print("[yellow]Goodbye![/yellow]")
            return True

        elif command == "/help":
            self.show_help()
            return True

        elif command == "/clear":
            self.agent.clear_history()
            self.console.print("[yellow]History cleared.[/yellow]")
            return True

        elif command == "/tools":
            tools_info = self.agent.get_tools_info()
            self.console.print(
                Panel(
                    tools_info,
                    title="[bold cyan]Available Tools[/bold cyan]",
                    border_style="cyan",
                )
            )
            return True

        elif command == "/history":
            self.show_history()
            return True

        return False

    def show_help(self) -> None:
        """Show help information"""
        help_text = """
[bold]Available Slash Commands:[/bold]
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
