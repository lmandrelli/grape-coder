import importlib.metadata
import logging
import os
import shutil
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from grape_coder import set_debug_mode
from grape_coder.agents.todo import create_todo_generator_agent

from .agents.composer import build_composer
from .agents.mono_agent import create_mono_agent
from .agents.planner import build_planner
from .config import run_config_setup
from .config.manager import get_config_manager

logging.getLogger("strands").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
    handlers=[logging.FileHandler("grape_coder.log", mode="a")],
)

app = typer.Typer(no_args_is_help=True)

console = Console()


def validate_config(panic: bool = True):
    """Validate configuration and provide detailed error messages.

    Args:
        panic: If True, raise exceptions on invalid config (for non-config commands).
               If False, return validation result without panicking (for config command).
    """
    config_manager = get_config_manager()

    # Try non-panicking mode first to get detailed errors
    validation_result = config_manager.validate_config(panic=False)

    if isinstance(validation_result, dict) and validation_result:
        # Display detailed validation errors
        config_manager.display_validation_errors(validation_result)

        if panic:
            # For non-config commands, fallback to panicking mode
            try:
                return config_manager.validate_config(panic=True)
            except Exception as e:
                console.print(f"[red]Configuration validation failed: {str(e)}[/red]")
                console.print(
                    "[yellow]Run 'grape-coder config' to fix your configuration.[/yellow]"
                )
                return False
        else:
            # For config command, just return False without panicking
            return False
    elif isinstance(validation_result, bool):
        return validation_result
    else:
        # Fallback to panicking mode if something unexpected happens
        try:
            return config_manager.validate_config(panic=panic)
        except Exception as e:
            console.print(f"[red]Configuration validation failed: {str(e)}[/red]")
            if not panic:
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
    # Display validation errors first without panicking
    is_valid = validate_config(panic=False)

    if is_valid:
        console.print("[green]Configuration is valid![/green]\n")

    run_config_setup()


@app.command()
def mono_agent(
    path: str = typer.Argument(
        ".", help="Path to work in (default: current directory)"
    ),
):
    """Run a single coding agent with the given prompt."""

    # Validate configuration first with panic mode
    if not validate_config(panic=True):
        raise typer.Exit(1)

    # Resolve and validate the path
    work_path = Path(path).resolve()
    if not work_path.exists():
        console.print(f"[red]Error: Path '{path}' does not exist[/red]")
        raise typer.Exit(1)

    # Change to the target directory
    original_cwd = os.getcwd()
    os.chdir(work_path)

    console.print(f"[green]Running Mono-Agent in: {work_path}[/green]")

    try:
        user_input = console.input("\n[bold cyan]You:[/bold cyan] ")

        console.print("[blue]💻 Mono-Agent[/blue]")

        # Create and run the mono-agent
        mono_agent = create_mono_agent(str(work_path))
        
        prompt = f"""
        This is the task assigned to you:
        {user_input}
        You can't ask the user for more information. You must complete the task with the information you have.
        """
        
        result = mono_agent(prompt)

        if result.status.value == "completed":
            console.print("[green]✓ Task completed successfully[/green]")
        else:
            console.print("[red]✗ Task failed[/red]")

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)
    finally:
        # Restore original working directory
        os.chdir(original_cwd)


@app.command()
def code(
    path: str = typer.Argument(
        ".", help="Path to work in (default: current directory)"
    ),
    debug: bool = typer.Option(
        False, "--debug", help="Enable debug mode with verbose output"
    ),
):
    """Start an interactive code session with file system tools."""

    # Set global debug flag
    set_debug_mode(debug)

    # Validate configuration first with panic mode
    if not validate_config(panic=True):
        raise typer.Exit(1)

    # Resolve and validate the path
    work_path = Path(path).resolve()
    if not work_path.exists():
        console.print(f"[red]Error: Path '{path}' does not exist[/red]")
        raise typer.Exit(1)

    # Copy templates folder if target directory is empty
    templates_dir = Path(os.path.join(os.path.dirname(__file__), "templates")).resolve()
    if templates_dir.exists():
        # Check if work_path is empty, ignoring hidden files like .DS_Store
        if not any(
            item for item in work_path.iterdir() if not item.name.startswith(".")
        ):  # if work_path is empty (ignoring hidden files)
            try:
                shutil.copytree(templates_dir, work_path, dirs_exist_ok=True)
            except Exception as e:
                console.print(
                    f"[yellow]Warning: Could not copy templates: {str(e)}[/yellow]"
                )
        else:
            console.print(
                "[yellow]Templates folder already exists, skipping copy[/yellow]"
            )

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
                
                global_system_prompt = """
                You are grape-coder, an AI multi-agent system. Each agent has a specialized role and should strictly limit itself to that assigned role.
                The website must be developed using best practices, it will be writen with HTML, CSS and Vanilla JavaScript only. If a file or ressource fails to be created, do not try to reference it later.
                You can only create svg files for graphics, you can use svg to do placeholders for images and videos.
                """

                console.print("[bold green]Agent:[/bold green]")

                console.print("\n[green]📄 Planner[/green]")

                try:
                    planner = build_planner(str(work_path))

                    planner_prompt = """Create a comprehensive website development plan based on the user's task. Break down the plan into clear, manageable steps.
                    The user will provide you a high-level prompt for website development. You cannot ask the user for more information. You must complete the task with the information you have."""
                    planner_result = planner(f"{global_system_prompt}\n{planner_prompt}\nUSER TASK: {user_input}")

                    # Extract the complete plan from the swarm
                    complete_plan = ""
                    for node_name, node_result in planner_result.results.items():
                        if hasattr(node_result, "result"):
                            complete_plan += f"\n=== {node_name.upper()} OUTPUT ===\n{node_result.result}\n"

                    console.print("\n[green]📋 Todo[/green]")

                    todo_generator = create_todo_generator_agent(str(work_path))

                    todo_prompt = f"Create a structured todo list from this website development plan:\n{complete_plan}"
                    todo_result = todo_generator(f"{global_system_prompt}\n{todo_prompt}")

                    graph_input = f"""{global_system_prompt}
                    Execute the following todo list for website development:\n{todo_result}
                    """

                except Exception as e:
                    console.print(f"[bold red]Swarm error: {str(e)}[/bold red]")
                    console.print(
                        "[bold yellow]Falling back to direct code execution...[/bold yellow]"
                    )

                    # Fallback to direct code execution
                    graph_input = f"""
                    {global_system_prompt}
                    USER TASK: {user_input}
                    """

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
