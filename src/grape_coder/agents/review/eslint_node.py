import subprocess
from pathlib import Path

from strands.agent import AgentResult
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import ContentBlock, Message


ESLINT_CONFIG_TEMPLATE = """export default [
  {
    ignores: ["node_modules/", "dist/", "build/", ".git/"],
  },
  {
    files: ["**/*.{js,html,css}"],
    plugins: {
      // Built-in rules, no external plugins needed
    },
    rules: {
      "no-unused-vars": "warn",
      "no-undef": "warn",
      "no-console": "warn",
      "eqeqeq": ["error", "always"],
      "curly": "error",
      "no-else-return": "warn",
      "no-empty": "warn",
      "no-eval": "error",
      "no-implicit-globals": "warn",
      "no-redeclare": "error",
      "semi": ["error", "always"],
      "no-extra-semi": "error",
    },
  },
];
"""


class ESLintNode(MultiAgentBase):
    """
    A deterministic node that runs ESLint on the work path directory.
    Generates an eslint.config.js file and executes ESLint analysis.
    """

    def __init__(
        self,
        work_path: str,
        eslint_command: str = 'npx eslint "**/*.{js,html,css}" --format json',
    ):
        super().__init__()
        self.work_path = Path(work_path)
        self.eslint_command = eslint_command

    def _generate_eslint_config(self) -> bool:
        """Generate an eslint.config.js file in the work path directory."""
        try:
            config_path = self.work_path / "eslint.config.js"
            config_path.write_text(ESLINT_CONFIG_TEMPLATE)
            return True
        except Exception:
            return False

    def _run_eslint(self) -> tuple[bool, str]:
        """Run ESLint command and return (success, output)."""
        try:
            result = subprocess.run(
                self.eslint_command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=str(self.work_path),
                timeout=120,
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "ESLint timed out after 120 seconds"
        except FileNotFoundError:
            return (
                False,
                "ESLint command not found. Please ensure Node.js and ESLint are installed.",
            )
        except Exception as e:
            return False, f"ESLint execution error: {str(e)}"

    async def invoke_async(self, task, invocation_state=None, **kwargs):
        config_success = self._generate_eslint_config()
        if not config_success:
            agent_result = AgentResult(
                stop_reason="end_turn",
                state=Status.COMPLETED,
                metrics=EventLoopMetrics(),
                message=Message(
                    role="assistant",
                    content=[
                        ContentBlock(text="ESLint configuration generation failed")
                    ],
                ),
            )
            return MultiAgentResult(
                status=Status.COMPLETED,
                results={
                    "eslint_linter": NodeResult(
                        result=agent_result, status=Status.COMPLETED
                    )
                },
            )

        success, output = self._run_eslint()

        if success:
            formatted_output = (
                f"ESLint Results:\n{output}"
                if output
                else ""
            )
        else:
            formatted_output = ""

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
                "eslint_linter": NodeResult(
                    result=agent_result, status=Status.COMPLETED
                )
            },
        )
