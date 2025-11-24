import asyncio
import importlib.metadata
from typing import Optional

import typer
from rich.console import Console

from .agent_loop import create_default_agent, AgentLoop

app = typer.Typer(no_args_is_help=True)
console = Console()


def version_callback(value: bool):
    if value:
        typer.echo("""               #
       #####  ###
       #####  ###        ______                         ______          __
     ###   ### ##       / ____/________ _____  ___     / ____/___  ____/ /__  _____
   ######*#####-####   / / __/ ___/ __ `/ __ \\/ _ \\   / /   / __ \\/ __  / _ \\/ ___/
    ####  ####   #### / /_/ / /  / /_/ / /_/ /  __/  / /___/ /_/ / /_/ /  __/ /
 ####  ####  ####     \\____/_/   \\__,_/ .___/\\___/   \\____/\\____/\\__,_/\\___/_/
############=#####                   /_/
 ####  +###  =###
""")
        version = importlib.metadata.version("grape-coder")
        typer.echo(f"Running v{version}")
        raise typer.Exit()


@app.command()
def chat(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    """Start an interactive chat session with the AI agent."""
    console.print("[bold green]Starting Grape Coder Agent...[/bold green]")

    try:
        agent = create_default_agent()
        loop = AgentLoop(agent)
        asyncio.run(loop.start())
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")
    except Exception as e:
        console.print(f"[red]Error starting agent: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def hello(
    name: str = typer.Argument(..., help="Name to greet"),
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    """Hello {name} ! This is grape-coder."""
    typer.echo(f"Hello {name} ! This is grape-coder.")


@app.command()
def demo(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    """Run a demo of the agent capabilities."""
    console.print("[bold green]Grape Coder Agent Demo[/bold green]")
    console.print("This demo shows the agent's capabilities with XML function calling.")
    console.print("\n[yellow]Try these commands:[/yellow]")
    console.print("• 'What is 2+2?' - Tests calculator tool")
    console.print("• 'What time is it?' - Tests time tool")
    console.print("• 'Echo hello world' - Tests echo tool")
    console.print("• 'help' - Shows available commands")
    console.print("• 'quit' - Exit the demo")
    console.print("\n[bold blue]Starting chat session...[/bold blue]")

    try:
        agent = create_default_agent()
        loop = AgentLoop(agent)
        asyncio.run(loop.start())
    except KeyboardInterrupt:
        console.print("\n[yellow]Demo ended.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error running demo: {str(e)}[/red]")
        raise typer.Exit(1)


@app.callback()
def main_callback():
    """Grape Coder - AI Agent with XML Function Calling"""
    pass


if __name__ == "__main__":
    app()
