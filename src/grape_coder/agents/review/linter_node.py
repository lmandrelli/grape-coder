import subprocess
from pathlib import Path

from strands.agent import AgentResult
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import ContentBlock, Message

from grape_coder.config.models import LinterConfig

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text


class LinterNode(MultiAgentBase):
    """
    A deterministic node that runs multiple linters on the work path directory.
    Uses oxlint, markuplint, purgecss, and linkinator for linting.
    """

    def __init__(
        self,
        work_path: str,
        linter_config: LinterConfig | None = None,
    ):
        super().__init__()
        self.work_path = Path(work_path)
        self.linter_config = linter_config or LinterConfig()

    def _run_command(self, name: str, command: str) -> tuple[bool, str]:
        """Run a linter command and return (success, output)."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=str(self.work_path),
                timeout=120,
            )
            output = result.stdout + result.stderr
            return True, output if output is not None else ""
        except subprocess.TimeoutExpired:
            return False, ""
        except FileNotFoundError:
            return False, ""
        except Exception:
            return False, ""

    def _get_commands(self) -> dict[str, str]:
        """Get linter commands from config."""
        return {
            "oxlint": self.linter_config.oxlint,
            "markuplint": self.linter_config.markuplint,
            "purgecss": self.linter_config.purgecss,
            "linkinator": self.linter_config.linkinator,
        }

    def run_linters(self) -> dict[str, dict]:
        """Run all linters and return results."""
        results = {}
        commands = self._get_commands()

        for name, command in commands.items():
            success, output = self._run_command(name, command)
            results[name] = {"success": success, "output": output}

        return results

    def print_results(self) -> None:
        """Print linter results to user using typer and rich."""
        results = self.run_linters()
        console = Console()

        all_passed = all(r["success"] for r in results.values())
        all_failed = all(not r["success"] for r in results.values())

        if all_failed:
            typer.secho("All linters failed", fg=typer.colors.RED)
            return

        for name, result in results.items():
            if result["success"]:
                status = "✓ PASS" if result["success"] else "✗ FAIL"
                color = typer.colors.GREEN if result["success"] else typer.colors.RED
                typer.secho(f"{name}: {status}", fg=color)

                if result["output"]:
                    console.print(
                        Panel(
                            Text(result["output"]),
                            title=f"{name} output",
                            expand=False,
                        )
                    )
            else:
                typer.secho(f"{name}: ✗ FAIL", fg=typer.colors.RED)

    async def invoke_async(self, task, invocation_state=None, **kwargs):
        # Linter runs first, so task is the original user task
        # We run linters and output results for the next node (Reviewer)
        results = self.run_linters()

        linter_output = self._format_results(results)

        # Print results to console since linter is the entry point
        self.print_results()

        # Format output for the next node (Reviewer)
        if linter_output:
            formatted_output = f"\nLinter Results:\n{linter_output}"
        else:
            formatted_output = "\nLinter Results:\n  (no output)"

        agent_result = AgentResult(
            stop_reason="end_turn",
            state=Status.COMPLETED,
            metrics=EventLoopMetrics(),
            message=Message(
                role="assistant",
                content=[ContentBlock(text=formatted_output)],
            ),
        )

        return MultiAgentResult(
            status=Status.COMPLETED,
            results={
                "linter": NodeResult(result=agent_result, status=Status.COMPLETED)
            },
        )

    def _format_results(self, results: dict[str, dict]) -> str:
        """Format linter results for next agent."""
        output_lines = []

        for name, result in results.items():
            if result["success"]:
                status = "✓ PASS"
                output_lines.append(f"\n{name}: {status}")
            else:
                continue
            if result["output"]:
                output_lines.append(result["output"])

        return "\n".join(output_lines)
