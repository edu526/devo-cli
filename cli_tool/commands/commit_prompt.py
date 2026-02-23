import re
import subprocess
import webbrowser

import click

from cli_tool.agents.base_agent import BaseAgent
from cli_tool.utils.git_utils import get_branch_name, get_remote_url, get_staged_diff


@click.command()
@click.option("--push", "-p", is_flag=True, help="Push the commit to the remote origin.")
@click.option("--pull-request", "-pr", is_flag=True, help="Open a pull request on GitHub.")
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
        system_prompt="""You are an AI that generates ONE conventional commit message.

CRITICAL: Generate ONLY ONE commit message, not multiple. Find the PRIMARY purpose of all changes.

FORMAT (first line):
type(scope): summary

VALID TYPES: feat, fix, refactor, chore, docs, test, style, perf

RULES:
1. First line: type(scope): summary (max 50 chars)
2. Summary explains WHY, not what
3. Optional: blank line + bullet points with details
4. NO markdown, NO multiple messages, NO explanations

CORRECT EXAMPLES:
refactor(agents): simplify commit message generation

fix(auth): resolve credential validation error

- Fixed caching logic
- Added error handling

INCORRECT (DO NOT DO):
❌ Multiple commit messages listed
❌ refactor(agents): improve X
   fix(base): enhance Y
   refactor(commit): replace Z

Generate ONE message capturing the main purpose of ALL changes.""",
        enable_rich_logging=False,  # Disable rich logging to avoid duplicate output
    )
    diff_text = get_staged_diff()
    if not diff_text:
        click.echo("No staged changes found.")
        return

    branch_name = get_branch_name()
    # Extract ticket number from branch name (e.g., feature/TICKET-123-description)
    match = re.match(r"feature/([A-Z]+-\d+)", branch_name)
    ticket_number = match.group(1) if match else None

    # Get additional git context for better commit message generation
    try:
        # Get git status to understand what files are being committed
        git_status_result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
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
    context_prompt = f"""Generate ONE commit message for these changes.

IMPORTANT: All these changes are part of ONE commit. Find the PRIMARY purpose and create ONE message.

CONTEXT:
Branch: {branch_name}
Ticket: {ticket_number or 'None'} (will be added automatically if present, do NOT include it in your message)

STAGED DIFF:
{diff_text}

GIT STATUS:
{git_status}

RECENT COMMITS (for style):
{recent_commits}

Remember: Generate ONLY ONE commit message that captures the main purpose of ALL these changes together.
Do NOT include the ticket number in your response - it will be added automatically if present in branch name."""

    try:
        # Show loading message
        click.echo("Generating commit message...")

        # Get AI response as text and parse it
        ai_response = agent_ai.query(context_prompt)

        # Parse the response to extract commit message components
        # Expected format: type(scope): summary\n\ndetails (optional)
        lines = ai_response.strip().split("\n")
        first_line = lines[0].strip()

        # Extract type, scope, and summary from first line
        # Format: type(scope): summary
        if ":" in first_line:
            type_scope, summary = first_line.split(":", 1)
            summary = summary.strip()

            # Extract type and scope
            if "(" in type_scope and ")" in type_scope:
                commit_type = type_scope.split("(")[0].strip()
                scope = type_scope.split("(")[1].split(")")[0].strip()
            else:
                commit_type = type_scope.strip()
                scope = "general"
        else:
            # Fallback if format is not as expected
            commit_type = "chore"
            scope = "general"
            summary = first_line

        # Get details if present (everything after first line)
        details = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
        details_formatted = "" if not details else "\n\n{}".format(details)

        # Add ticket number to summary if present and not already included
        if ticket_number and ticket_number not in summary:
            summary = "{} {}".format(ticket_number, summary)

        commit_message = "{}({}): {}{}".format(commit_type, scope, summary, details_formatted).strip()

        # Display the generated commit message
        click.echo("\n" + "=" * 60)
        click.echo("Generated commit message:")
        click.echo("=" * 60)
        click.echo(commit_message)
        click.echo("=" * 60 + "\n")

        if click.confirm("Do you want to use this commit message?"):
            subprocess.run(["git", "commit", "-m", commit_message], check=True)
            click.echo("\n✅ Commit message accepted")
        else:
            manual_message = click.prompt("Enter your commit message")
            if ticket_number and ticket_number not in manual_message:
                manual_message = "{} {}".format(ticket_number, manual_message)
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
                pr_url = remote_url.replace(".git", "") + "/compare/{}?expand=1".format(branch_name)
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
