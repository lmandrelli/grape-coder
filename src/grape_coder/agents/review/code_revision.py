from typing import cast, List
import re

from rich.console import Console
from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.model import Model
from strands.multiagent import MultiAgentResult
from strands.multiagent.base import MultiAgentBase, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import ContentBlock, Message

from grape_coder.agents.identifiers import AgentIdentifier, get_agent_description
from grape_coder.config import get_config_manager
from grape_coder.display import get_conversation_tracker, get_tool_tracker
from grape_coder.tools.web import fetch_url, search
from grape_coder.tools.work_path import (
    edit_file,
    glob_files,
    grep_files,
    list_files,
    read_file,
    set_work_path,
)
from grape_coder.tools.targeted_edit import (
    str_replace_code,
    pattern_replace_code,
    insert_text_code,
)
from grape_coder.tools.tool_limit_hooks import get_tool_limit_hook

console = Console()


def get_base_system_prompt() -> str:
    """Get the base system prompt for code revision."""
    return """You are a Code Revision Specialist working in a multi-agent web development system.

CONTEXT:
A code reviewer has analyzed the website code and provided feedback containing:
1. A REVIEW SUMMARY - brief overview of main issues
2. TASKS TO FIX organized by priority with specific issues to address

Your role is to address each issue raised in the review and improve the code quality.

YOUR TASK:
You will receive a review summary and a task list.
Your responsibilities are:
1. First, read the review summary to understand the overall assessment
2. Then, follow the task list to address each issue in order
3. First tasks are the most important - fix them first
4. Review the affected files to understand the current implementation
5. Make the necessary corrections to address each task
6. Ensure your fixes don't break other functionality
7. Re-test the changes by reading the modified files

WORKFLOW:
1. Read the review summary first for context
2. Follow the task list to fix issues in order (first tasks = highest priority)
3. For each task mentioned:
    a. Find and read the relevant files
    b. Understand what needs to be changed
    c. Make the necessary edits
    d. Verify the changes address the issue

IMPORTANT - FIX SUMMARY REQUIREMENT:
At the END of your work, you MUST provide a summary of fixes applied in the following format:

<fixes_applied>
    <fix>Brief description of fix 1</fix>
    <fix>Brief description of fix 2</fix>
    ...
</fixes_applied>

This summary is critical for tracking progress across review iterations.

GOAL:
Fix all issues in the task list to improve the code quality. Provide a summary of all fixes at the end.

Available tools:
- list_files: List files and directories in a path (automatically called at startup)
- read_file: Read contents of one or more files
- edit_file: Rewrite or create a file with new content
- str_replace_web: Replace exact text in .html, .js, .css, .svg, .json, .md files
- pattern_replace_web: Replace text using regex patterns in web files
- insert_text_web: Insert text after a specific line in web files
- grep_files: Search for patterns in files
- glob_files: Find files using glob patterns
- fetch_url: Fetch content from a URL
- search: Search the web for information

The workspace exploration will be automatically provided to you at the start."""


def extract_fixes_from_response(response_text: str) -> List[str]:
    """Extract the list of fixes from the agent's response.

    Looks for the <fixes_applied> XML block and extracts individual fixes.
    """
    fixes = []

    # Try to extract from XML format
    fixes_match = re.search(
        r"<fixes_applied>(.*?)</fixes_applied>", response_text, re.DOTALL
    )
    if fixes_match:
        fixes_content = fixes_match.group(1)
        fix_matches = re.findall(r"<fix>(.*?)</fix>", fixes_content, re.DOTALL)
        fixes = [fix.strip() for fix in fix_matches if fix.strip()]

    # If no XML format, try to extract from common patterns
    if not fixes:
        # Look for numbered lists
        numbered_fixes = re.findall(
            r"\d+\.\s+(?:Fixed|Added|Updated|Removed|Corrected|Improved)[^.]+\.",
            response_text,
        )
        if numbered_fixes:
            fixes = [fix.strip() for fix in numbered_fixes]

    # If still no fixes, try bullet points
    if not fixes:
        bullet_fixes = re.findall(
            r"[-*]\s+(?:Fixed|Added|Updated|Removed|Corrected|Improved)[^.\n]+",
            response_text,
        )
        if bullet_fixes:
            fixes = [fix.strip() for fix in bullet_fixes]

    return fixes


def create_code_revision_agent(
    work_path: str, agent_id: AgentIdentifier
) -> MultiAgentBase:
    """Create a code revision agent that fixes code based on review feedback."""
    set_work_path(work_path)

    config_manager = get_config_manager()
    model = cast(Model, config_manager.get_model(agent_id))

    return CodeRevisionNode(
        model=model,
        system_prompt=get_base_system_prompt(),
        work_path=work_path,
        tools=[
            list_files,
            read_file,
            edit_file_code,
            str_replace_code,
            pattern_replace_code,
            insert_text_code,
            grep_files,
            glob_files,
            fetch_url,
            search,
        ],
        agent_id=agent_id,
        hooks=[
            get_tool_tracker(agent_id),
            get_conversation_tracker(agent_id),
            get_tool_limit_hook(agent_id),
        ],
    )


@tool
def edit_file_code(path: str, content: str) -> str:
    """Edit or create a web file. Only .html, .js, .css, .svg, .json and .md files are allowed."""
    allowed_extensions = (".html", ".js", ".css", ".svg", ".json", ".md")
    if not path.endswith(allowed_extensions):
        return f"ERROR: You are only allowed to create and edit web files with extensions: .html, .js, .css, .svg, .json, .md. The path '{path}' does not have an allowed extension."

    return edit_file(path, content)


class CodeRevisionNode(MultiAgentBase):
    """Custom node that handles code revision with workspace exploration and fix tracking."""

    def __init__(
        self,
        model,
        system_prompt,
        work_path: str,
        tools,
        agent_id,
        hooks=None,
    ):
        super().__init__()
        self.model = model
        self.system_prompt = system_prompt
        self.work_path = work_path
        self.tools = tools
        self.agent_id = agent_id
        self.hooks = hooks or []

    def _create_agent(self, context_prompt: str) -> Agent:
        """Create the agent with optional context prepended."""
        if context_prompt:
            full_prompt = f"{context_prompt}\n\n{self.system_prompt}"
        else:
            full_prompt = self.system_prompt

        return Agent(
            model=self.model,
            tools=self.tools,
            system_prompt=full_prompt,
            name=self.agent_id,
            description=get_agent_description(self.agent_id),
            hooks=self.hooks,
        )

    async def invoke_async(self, task, invocation_state=None, **kwargs):
        """Execute workspace exploration before processing revision tasks"""
        try:
            # Remove input propagation
            task = task[1:]

            task_str = task if isinstance(task, str) else str(task)

            if len(task) == 0:
                agent_result = AgentResult(
                    stop_reason="end_turn",
                    state=Status.COMPLETED,
                    metrics=EventLoopMetrics(),
                    message=Message(
                        role="assistant",
                        content=[ContentBlock(text="No tasks remaining to process.")],
                    ),
                )

                return MultiAgentResult(
                    status=Status.COMPLETED,
                    results={
                        "code_revision": NodeResult(
                            result=agent_result, status=Status.COMPLETED
                        )
                    },
                )

            # Get context from review history
            from grape_coder.agents.review.review_graph import get_review_context

            context = get_review_context()
            context_prompt = ""

            # Add context about previous fixes if this is not the first iteration
            if context.current_iteration > 1:
                previous_fixes = context.get_all_fixes_applied()
                if previous_fixes:
                    context_prompt = f"""=== PREVIOUS ITERATION CONTEXT ===
Iteration: {context.current_iteration} of {context.max_iterations}

FIXES ALREADY APPLIED IN PREVIOUS ITERATIONS:
{chr(10).join(f"- {fix}" for fix in previous_fixes[:10])}

IMPORTANT:
- Do NOT re-apply fixes that were already made
- Focus on NEW issues identified in this iteration's review
- If a previous fix didn't work, try a DIFFERENT approach
================================
"""

            agent = self._create_agent(context_prompt)

            exploration_result = list_files(path=self.work_path, recursive=True)

            workspace_context = f"""WORKSPACE EXPLORATION RESULTS:
{exploration_result}

REVISION TASKS TO COMPLETE:
{task_str}

Please fix all the issues mentioned in the revision tasks. Focus on the most important issues first.

REMINDER: At the end of your work, provide a <fixes_applied> summary listing all fixes you made."""

            response = await agent.invoke_async(workspace_context)

            # Extract response text
            response_text = str(response)

            # Extract fixes and store them in context
            fixes = extract_fixes_from_response(response_text)
            if fixes:
                # Update the most recent iteration with fixes
                if context.iterations:
                    context.iterations[-1].fixes_applied = fixes
                console.print(
                    f"[green]Recorded {len(fixes)} fixes from this iteration[/green]"
                )
                for i, fix in enumerate(fixes[:5], 1):
                    console.print(f"  [dim]{i}. {fix[:80]}...[/dim]")
                if len(fixes) > 5:
                    console.print(f"  [dim]... and {len(fixes) - 5} more[/dim]")

            agent_result = AgentResult(
                stop_reason="end_turn",
                state=Status.COMPLETED,
                metrics=EventLoopMetrics(),
                message=response.message
                if hasattr(response, "message")
                else Message(
                    role="assistant", content=[ContentBlock(text=response_text)]
                ),
            )

            return MultiAgentResult(
                status=Status.COMPLETED,
                results={
                    "code_revision": NodeResult(
                        result=agent_result, status=Status.COMPLETED
                    )
                },
            )

        except Exception as e:
            agent_result = AgentResult(
                stop_reason="guardrail_intervened",
                state=Status.FAILED,
                metrics=EventLoopMetrics(),
                message=Message(
                    role="assistant",
                    content=[ContentBlock(text=f"Error: {str(e)}")],
                ),
            )

            return MultiAgentResult(
                status=Status.FAILED,
                results={
                    "code_revision": NodeResult(
                        result=agent_result, status=Status.FAILED
                    )
                },
            )
