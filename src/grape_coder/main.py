import importlib.metadata
from typing import Optional

import typer

app = typer.Typer(no_args_is_help=True)


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
