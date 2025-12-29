#!/usr/bin/env python3
"""Test script to launch the review loop directly.

Usage:
    python test_review.py --path /path/to/workdir --prompt "Build a portfolio website"

This script initializes the review graph and runs it with the given prompt,
capturing all strands logs for debugging.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import typer
from rich.console import Console

from grape_coder import set_debug_mode
from grape_coder.agents.review import build_review_graph
from grape_coder.globals import set_original_user_prompt

console = Console()

file_handler = logging.FileHandler("review_test.log", mode="w")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(levelname)s | %(name)s | %(message)s"))

strand_logger = logging.getLogger("strands")
strand_logger.setLevel(logging.DEBUG)
strand_logger.addHandler(file_handler)

litellm_logger = logging.getLogger("liteLLM")
litellm_logger.setLevel(logging.WARNING)
litellm_logger.addHandler(file_handler)


def display_result(result) -> None:
    """Display the review results in a formatted way."""
    console.print("\n" + "=" * 60)
    console.print("[bold blue]📊 REVIEW RESULTS[/bold blue]")
    console.print("=" * 60)

    console.print(f"\n[bold]Status:[/bold] {result.status}")

    for node_name, node_result in result.results.items():
        console.print(f"\n--- {node_name.upper().replace('_', ' ')} ---")
        if hasattr(node_result, "result"):
            result_str = str(node_result.result)
            if len(result_str) > 2000:
                console.print(result_str[:2000] + "\n... (truncated)")
            else:
                console.print(result_str)

    console.print("\n" + "=" * 60)


def main(
    path: str = typer.Argument(..., help="Path to work directory"),
    prompt: str = typer.Option(
        ..., "--prompt", "-p", help="User prompt for the review"
    ),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug mode"),
):
    """Run the review graph with the given prompt and work path."""

    work_path = Path(path).resolve()

    if not work_path.exists():
        console.print(f"[red]Error: Path '{path}' does not exist[/red]")
        raise typer.Exit(1)

    console.print("[bold green]Starting Review Test[/bold green]")
    console.print(f"Work path: {work_path}")
    console.print(f"Prompt: {prompt}")

    set_debug_mode(debug)
    set_original_user_prompt(prompt)

    original_cwd = os.getcwd()
    os.chdir(work_path)

    try:
        console.print("\n[bold]Building Review Graph...[/bold]")

        review_graph = build_review_graph(str(work_path))

        console.print("[bold green]✓ Review Graph built successfully[/bold green]")

        console.print("\n[bold]Running Review Graph...[/bold]")

        graph_input = f"""
        You are a system for reviewing code that has been generated.
        Review the code files in the workspace and provide feedback for improvement if needed.

        ORIGINAL USER REQUEST:
        {prompt}

        Please review the code files and provide detailed feedback on:
        1. Visual aesthetics and modern design
        2. Code validity and syntax
        3. Integration of all components
        4. Responsiveness across devices
        5. Best practices compliance
        6. Accessibility considerations
        """

        result = review_graph(graph_input)

        display_result(result)

        console.print("[bold green]✓ Review test completed![/bold green]")
        console.print(f"\nLogs written to: {Path('review_test.log').resolve()}")

    except Exception as e:
        console.print(f"[red]Error during review: {str(e)}[/red]")
        strand_logger.exception("Review error")
        raise typer.Exit(1)
    finally:
        os.chdir(original_cwd)


if __name__ == "__main__":
    typer.run(main)
