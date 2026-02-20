import re
import subprocess
import webbrowser

import click
from pydantic import BaseModel

from cli_tool.agents.base_agent import BaseAgent
from cli_tool.utils.git_utils import get_branch_name, get_remote_url, get_staged_diff


class CommitMessageResponse(BaseModel):
    """Model for the commit message response with structured output."""

    type: str  # feat, fix, chore, docs, refactor, test, style, perf
    scope: str  # component or area affected
    summary: str  # concise description (max 50 chars)
    details: str = ""  # optional detailed explanation


@click.command()
@click.option(
    "--push", "-p", is_flag=True, help="Push the commit to the remote origin."
)
@click.option(
    "--pull-request", "-pr", is_flag=True, help="Open a pull request on GitHub."
)
@click.option(
    "--add",
    "-a",
    is_flag=True,
    help="Add all changes to the staging area before committing.",
)
@click.option(
    "--all",
    "-A",
    is_flag=True,
    help="Perform add, commit, push, and open pull request.",
)
@click.pass_context
def commit(ctx, push, pull_request, add, all):
    """Generate a commit message based on staged changes with AI."""
    if all:
        add = True
        push = True
        pull_request = True

    if add:
        click.echo("Adding all changes to the staging area...")
        subprocess.run(["git", "add", "."], check=True)
        click.echo("✅ All changes added.")

    agent_ai = BaseAgent(
        name="CommitMessageGenerator",
        system_prompt="""
        You are an AI assistant that generates meaningful Git commit messages following conventional commit format and best practices.

        COMMIT MESSAGE ANALYSIS PROCESS:
        When generating a commit message, you should:

        1. Analyze the staged changes to understand:
           - Which files have been changed or added
           - The nature of changes (new feature, enhancement, bug fix, refactoring, test, docs, etc.)
           - The purpose or motivation behind these changes
           - The impact on the overall project
           - Check for any sensitive information that shouldn't be committed

        2. Draft a concise commit message that focuses on the "why" rather than the "what"

        COMMIT MESSAGE FORMAT:
        * Primary format: <type>(<scope>): <ticket number> <short summary>
        * If details needed: Add bullet points with specific changes
        * Types: feat, fix, chore, docs, refactor, test, style, perf
        * Include NDT-<ticket_number> if branch follows 'feature/NDT-<number>' pattern
        * Short summary should be max 50 chars and explain the purpose
        * Focus on why the change was made, not just what was changed

        QUALITY GUIDELINES:
        - Ensure language is clear, concise, and to the point
        - Message should accurately reflect changes and their purpose
        - "add" means wholly new feature, "update" means enhancement, "fix" means bug fix
        - Avoid generic messages like "Update" or "Fix" without context
        - Summarize what changed and why, not just list file modifications

        EXAMPLES:
        Good: "feat(cli): NDT-123 add AI-powered commit message generation"
        Bad: "Update commit_prompt.py"

        Good: "fix(auth): NDT-456 resolve AWS credential validation error"
        Bad: "Fix bug"
        """,
        enable_rich_logging=True,
    )
    diff_text = get_staged_diff()
    if not diff_text:
        click.echo("No staged changes found.")
        return

    branch_name = get_branch_name()
    match = re.match(r"feature/NDT-(\d+)", branch_name)
    ticket_number = match.group(1) if match else None
    ticket_refers_branch = f" NDT-{ticket_number}" if match else ""

    # Get additional git context for better commit message generation
    try:
        # Get git status to understand what files are being committed
        git_status_result = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
        )
        git_status = git_status_result.stdout

        # Get recent commit messages for style consistency
        git_log_result = subprocess.run(
            ["git", "log", "--oneline", "-10"],
            capture_output=True,
            text=True,
            check=True,
        )
        recent_commits = git_log_result.stdout

    except subprocess.CalledProcessError:
        git_status = "Unable to get git status"
        recent_commits = "Unable to get recent commits"

    # Prepare the context for the AI agent
    context_prompt = f"""
    Generate a meaningful commit message based on the staged changes.

    Follow this analysis process:
    1. Review the staged diff to understand what files changed
    2. Analyze the git status to see the scope of changes
    3. Consider recent commit messages for style consistency
    4. Determine the type and scope of changes
    5. Focus on WHY the changes were made, not just WHAT changed
    6. Create a concise, purposeful commit message

    The commit message should explain the motivation and impact of the changes.

    CONTEXT:
    Branch name: {branch_name}
    Ticket number: {ticket_number or 'None'}
    Ticket reference: {ticket_refers_branch}

    STAGED DIFF:
    {diff_text}

    GIT STATUS:
    {git_status}

    RECENT COMMITS (for style consistency):
    {recent_commits}
    """

    try:
        # Use Strands structured output for reliable parsing
        # BaseAgent now handles the conversion automatically
        response = agent_ai.query_structured(context_prompt, CommitMessageResponse)
        details = (
            "" if not response.details else "\n\n{}".format(response.details.strip())
        )

        commit_message = "{}({}): {}{}".format(
            response.type, response.scope, response.summary.strip(), details
        ).strip()

        if click.confirm(
            "Commit message generated: \n\n{}\n\nDo you want to accept this message?".format(
                commit_message
            )
        ):
            subprocess.run(["git", "commit", "-m", commit_message], check=True)
            click.echo("\n✅ Commit message accepted")
        else:
            manual_message = click.prompt("Enter your commit message")
            if ticket_number and "NDT-" not in manual_message:
                manual_message = " NDT-{} {}".format(ticket_number, manual_message)
            subprocess.run(["git", "commit", "-m", manual_message], check=True)
            click.echo("✅ Manual commit message accepted")

        if push:
            click.echo("\nPushing changes to origin/{}...".format(branch_name))
            subprocess.run(["git", "push", "origin", branch_name], check=True)
            click.echo("✅ Changes pushed to origin/{}".format(branch_name))

        if pull_request:
            remote_url = get_remote_url()
            if remote_url:
                # GitHub URL format for creating pull requests
                pr_url = remote_url.replace(".git", "") + "/compare/{}?expand=1".format(
                    branch_name
                )
                click.echo("\nOpening pull request URL in browser: {}".format(pr_url))
                webbrowser.open(pr_url)
            else:
                click.echo("Could not determine remote URL. Cannot open pull request.")
    except Exception as e:
        # Handle both requests.exceptions.RequestException and botocore.exceptions.NoCredentialsError
        msg = str(e)
        if "NoCredentialsError" in msg or "credentials" in msg:
            click.echo("❌ No AWS credentials found. Please configure your AWS CLI.")
        else:
            click.echo("❌ Error sending request: {}".format(msg))
