import importlib.metadata
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from strands.multiagent import Swarm

from .agents.code import create_code_agent
from .agents.planner import (
    create_architect_agent,
    create_content_planner_agent,
    create_designer_agent,
    create_researcher_agent,
    create_todo_generator_agent,
)

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

                # Planner - Create swarm for website development planning
                console.print(
                    "[bold blue]🚀 Planning website development with agent swarm...[/bold blue]"
                )

                try:
                    # Create specialized agents
                    researcher = create_researcher_agent(str(work_path))
                    architect = create_architect_agent(str(work_path))
                    designer = create_designer_agent(str(work_path))
                    content_planner = create_content_planner_agent(str(work_path))

                    # Create swarm with website development agents
                    swarm = Swarm(
                        [researcher, architect, designer, content_planner],
                        entry_point=researcher,  # Start with researcher
                        max_handoffs=10,
                        max_iterations=10,
                        execution_timeout=480.0,  # 5 minutes
                        node_timeout=90.0,  # 2 minutes per agent
                        repetitive_handoff_detection_window=3,
                        repetitive_handoff_min_unique_agents=2,
                    )

                    # Execute swarm for website development planning
                    swarm_prompt = f"Create a comprehensive website development plan for: {user_input}"
                    swarm_result = swarm(swarm_prompt)

                    console.print(
                        "[bold green]✅ Swarm planning completed successfully![/bold green]"
                    )

                    # Extract the complete plan from the swarm
                    complete_plan = ""
                    for node_name, node_result in swarm_result.results.items():
                        if hasattr(node_result, "result"):
                            complete_plan += f"\n=== {node_name.upper()} OUTPUT ===\n{node_result.result}\n"

                    # Create todo generator agent
                    console.print(
                        "[bold blue]📋 Generating todo list from development plan...[/bold blue]"
                    )

                    todo_generator = create_todo_generator_agent(str(work_path))

                    # Generate structured todo list from the swarm's output
                    todo_prompt = f"Create a structured todo list from this website development plan:\n{complete_plan}"
                    todo_result = todo_generator(todo_prompt)

                    console.print("[bold green]📋 Todo list generated![/bold green]")

                    # Use the generated todo as input for the code agent
                    code_input = f"Execute the following todo list for website development:\n{todo_result}"

                except Exception as e:
                    console.print(f"[bold red]❌ Swarm error: {str(e)}[/bold red]")
                    console.print(
                        "[bold yellow]Falling back to direct code execution...[/bold yellow]"
                    )

                    # Fallback to direct code execution
                    code_input = user_input

                console.print(
                    "[bold blue]🤖 Invoking Code Agent to implement to-do...[/bold blue]"
                )

                code_agent = create_code_agent(str(work_path))
                response = code_agent(code_input)

                console.print(f"[bold green]Agent:[/bold green] {response}")

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
