"""Commit message generation command."""

import subprocess
import webbrowser

import click

from cli_tool.commit.core.generator import CommitMessageGenerator
from cli_tool.utils.aws import select_profile
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

    # Get profile from context or prompt user to select
    ctx.ensure_object(dict)
    profile = select_profile(ctx.obj.get("profile"))

    # Get staged diff
    diff_text = get_staged_diff()
    if not diff_text:
        click.echo("No staged changes found.")
        return

    branch_name = get_branch_name()

    try:
        # Show loading message
        click.echo("Generating commit message...")

        # Initialize generator and create commit message
        generator = CommitMessageGenerator(profile_name=profile)
        commit_message = generator.generate(diff_text, branch_name)

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
            manual_message = generator.add_ticket_to_message(manual_message, branch_name)
            subprocess.run(["git", "commit", "-m", manual_message], check=True)
            click.echo("✅ Manual commit message accepted")

        if push:
            click.echo(f"\nPushing changes to origin/{branch_name}...")
            subprocess.run(["git", "push", "origin", branch_name], check=True)
            click.echo(f"✅ Changes pushed to origin/{branch_name}")

        if pull_request:
            remote_url = get_remote_url()
            if remote_url:
                # GitHub URL format for creating pull requests
                pr_url = remote_url.replace(".git", "") + f"/compare/{branch_name}?expand=1"
                click.echo(f"\nOpening pull request URL in browser: {pr_url}")
                webbrowser.open(pr_url)
            else:
                click.echo("Could not determine remote URL. Cannot open pull request.")

    except Exception as e:
        # Handle both requests.exceptions.RequestException and botocore.exceptions.NoCredentialsError
        msg = str(e)
        if "NoCredentialsError" in msg or "credentials" in msg:
            click.echo("❌ No AWS credentials found. Please configure your AWS CLI.")
        else:
            click.echo(f"❌ Error sending request: {msg}")
