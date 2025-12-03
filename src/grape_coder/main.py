import asyncio
import importlib.metadata
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from .agent_loop import AgentLoop
from .agents.chat import create_chat_agent
from .agents.code import create_code_agent

app = typer.Typer(no_args_is_help=True)
console = Console()


def header():
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


def version_callback(value: bool):
    if value:
        header()
        version = importlib.metadata.version("grape-coder")
        typer.echo(f"Running v{version}")
        raise typer.Exit()


@app.command()
def chat():
    """Start an interactive chat session with the AI agent."""
    console.print("[bold green]Starting Grape Coder Chat Agent...[/bold green]")

    try:
        agent = create_chat_agent()
        loop = AgentLoop(agent)
        asyncio.run(loop.start())
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")
    except Exception as e:
        console.print(f"[red]Error starting agent: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def code(
    path: str = typer.Argument(
        ".", help="Path to work in (default: current directory)"
    ),
):
    """Start an interactive code session with file system tools."""

    # Resolve and validate the path
    work_path = Path(path).resolve()
    if not work_path.exists():
        console.print(f"[red]Error: Path '{path}' does not exist[/red]")
        raise typer.Exit(1)

    # Change to the target directory
    original_cwd = os.getcwd()
    os.chdir(work_path)

    console.print(
        f"[bold green]Starting Grape Coder Code Agent in: {work_path}[/bold green]"
    )

    try:
        agent = create_code_agent(str(work_path))
        loop = AgentLoop(agent)
        asyncio.run(loop.start())
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")
    except Exception as e:
        console.print(f"[red]Error starting agent: {str(e)}[/red]")
        raise typer.Exit(1)
    finally:
        # Restore original working directory
        os.chdir(original_cwd)


@app.callback()
def main_callback(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version",
    ),
):
    """Grape Coder - AI Agent with XML Function Calling"""
    pass


if __name__ == "__main__":
    app()
