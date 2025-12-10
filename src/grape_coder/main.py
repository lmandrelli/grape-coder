import importlib.metadata
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from grape_coder.agents.todo import create_todo_generator_agent

from .agents.composer import build_composer
from .agents.planner import build_planner
from .config import run_config_setup
from .config.manager import get_config_manager

app = typer.Typer(no_args_is_help=True)
console = Console()


def validate_config():
    """Validate configuration and provide detailed error messages."""
    config_manager = get_config_manager()
    try:
        return config_manager.validate_config(panic=True)
    except Exception as e:
        console.print(f"[red]Configuration validation failed: {str(e)}[/red]")
        console.print(
            "[yellow]Run 'grape-coder config' to fix your configuration.[/yellow]"
        )
        return False


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
def config():
    """Interactive configuration setup for providers and agents."""
    run_config_setup()


@app.command()
def code(
    path: str = typer.Argument(
        ".", help="Path to work in (default: current directory)"
    ),
):
    """Start an interactive code session with file system tools."""

    # Validate configuration first
    if not validate_config():
        raise typer.Exit(1)

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
        console.print(
            "[bold blue]Grape Coder is ready! Type 'exit' to quit.[/bold blue]"
        )

        while True:
            try:
                user_input = console.input("\n[bold cyan]You:[/bold cyan] ")

                if user_input.lower() in ["/exit", "/quit", "/q"]:
                    console.print("[yellow]Goodbye![/yellow]")
                    break

                if not user_input.strip():
                    continue

                console.print("[bold green]Agent:[/bold green]")

                console.print("\n[green]📄 Planner...[/green]")

                try:
                    planner = build_planner(str(work_path))

                    planner_prompt = f"Create a comprehensive website development plan for: {user_input}"
                    planner_result = planner(planner_prompt)

                    # Extract the complete plan from the swarm
                    complete_plan = ""
                    for node_name, node_result in planner_result.results.items():
                        if hasattr(node_result, "result"):
                            complete_plan += f"\n=== {node_name.upper()} OUTPUT ===\n{node_result.result}\n"

                    console.print("\n[green]📋 Todo[/green]")

                    todo_generator = create_todo_generator_agent(str(work_path))

                    todo_prompt = f"Create a structured todo list from this website development plan:\n{complete_plan}"
                    todo_result = todo_generator(todo_prompt)

                    graph_input = f"Execute the following todo list for website development:\n{todo_result}"

                except Exception as e:
                    console.print(f"[bold red]❌ Swarm error: {str(e)}[/bold red]")
                    console.print(
                        "[bold yellow]Falling back to direct code execution...[/bold yellow]"
                    )

                    # Fallback to direct code execution
                    graph_input = user_input

                console.print("\n[green]📚 Composer[/green]")

                graph = build_composer(str(work_path))
                _ = graph(graph_input)

            except KeyboardInterrupt:
                console.print("\n[yellow]Goodbye![/yellow]")
                break
            except Exception as e:
                console.print(f"[red]Error: {str(e)}[/red]")

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
    """Grape Coder - AI Agent with Strands Framework and Mistral"""
    pass


if __name__ == "__main__":
    app()
