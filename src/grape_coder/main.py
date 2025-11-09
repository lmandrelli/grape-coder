import typer
import importlib.metadata
from typing import Optional

app = typer.Typer(no_args_is_help=True)


def version_callback(value: bool):
    if value:
        version = importlib.metadata.version("grape-coder")
        typer.echo(version)
        raise typer.Exit()


@app.command(no_args_is_help=True)
def main(
    arg: str = typer.Argument(..., help="Argument to greet"),
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    """Hello {arg} ! This is grape-coder."""
    typer.echo(f"Hello {arg} ! This is grape-coder.")
