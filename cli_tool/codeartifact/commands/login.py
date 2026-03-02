"""CodeArtifact login command."""

import sys

import click
from rich.console import Console

from cli_tool.codeartifact.core.authenticator import CodeArtifactAuthenticator
from cli_tool.config import (
    AWS_SSO_URL,
    CODEARTIFACT_DOMAINS,
    CODEARTIFACT_REGION,
)
from cli_tool.utils.aws import check_aws_cli
from cli_tool.utils.aws_profile import (
    REQUIRED_ACCOUNT,
    REQUIRED_ROLE,
    verify_aws_credentials,
)

console = Console()


@click.command()
@click.pass_context
def codeartifact_login(ctx):
    """Login to AWS CodeArtifact for npm access.

    Authenticates with configured CodeArtifact domains and repositories.
    Supports multiple domains with different namespaces.

    Examples:
      devo codeartifact-login
      devo --profile my-profile codeartifact-login
    """
    from cli_tool.utils.aws import select_profile

    # Get profile from context or prompt user to select
    profile = select_profile(ctx.obj.get("profile"))

    click.echo(click.style("=== CodeArtifact Multi-Domain Login ===", fg="green"))
    click.echo("")
    click.echo(click.style(f"Required AWS Account: {REQUIRED_ACCOUNT}", fg="blue"))
    click.echo(click.style(f"Required IAM Role: {REQUIRED_ROLE}", fg="blue"))
    click.echo("")

    # Check if AWS CLI is installed
    if not check_aws_cli():
        sys.exit(1)

    # Verify credentials and account with spinner
    with console.status("[blue]Verifying AWS credentials...", spinner="dots"):
        account_id, user_arn = verify_aws_credentials(profile)

    if not account_id:
        click.echo(click.style("No AWS credentials found", fg="red"))
        click.echo("")
        click.echo(click.style("Get your AWS credentials from:", fg="blue"))
        click.echo(f"  {AWS_SSO_URL}")
        sys.exit(1)

    if account_id != REQUIRED_ACCOUNT:
        click.echo(click.style(f"Current credentials are for account: {account_id}", fg="yellow"))
        click.echo(click.style(f"Required account: {REQUIRED_ACCOUNT}", fg="yellow"))
        click.echo("")
        click.echo(click.style("Get credentials for the correct account from:", fg="blue"))
        click.echo(f"  {AWS_SSO_URL}")
        sys.exit(1)

    # Display credential info
    if profile:
        click.echo(click.style(f"Using profile: {profile}", fg="green"))
    else:
        click.echo(click.style("Using active AWS credentials", fg="green"))

    click.echo(click.style(f"Account: {account_id}", fg="blue"))
    click.echo(click.style(f"User: {user_arn}", fg="blue"))
    click.echo("")

    # Check if user has the required role
    if REQUIRED_ROLE not in user_arn:
        click.echo(
            click.style(
                f"Warning: User ARN does not contain '{REQUIRED_ROLE}' role",
                fg="yellow",
            )
        )
        click.echo("Please ensure you have the necessary CodeArtifact permissions")
        click.echo("")
        if not click.confirm("Continue anyway?"):
            click.echo("Aborted")
            sys.exit(1)

    click.echo(click.style(f"Region: {CODEARTIFACT_REGION}", fg="blue"))
    click.echo("")

    # Initialize authenticator
    authenticator = CodeArtifactAuthenticator(CODEARTIFACT_REGION, CODEARTIFACT_DOMAINS)

    # Track success/failure
    success_count = 0
    failure_count = 0
    failed_domains = []

    # Login to each domain
    for domain, repository, namespace in CODEARTIFACT_DOMAINS:
        with console.status(
            f"[yellow]Authenticating with {domain}/{repository} ({namespace})...",
            spinner="dots",
        ):
            success, error = authenticator.authenticate_domain(domain, repository, namespace, profile)

            if success:
                click.echo(
                    click.style(
                        f"✓ Successfully authenticated with {domain}/{repository} ({namespace})",
                        fg="green",
                    )
                )
                success_count += 1
            else:
                click.echo(
                    click.style(
                        f"✗ Failed to authenticate with {domain}/{repository} ({namespace})",
                        fg="red",
                    )
                )
                if error:
                    click.echo(error)
                failure_count += 1
                failed_domains.append(f"{domain}/{repository} ({namespace})")

        click.echo("")

    # Summary
    click.echo(click.style("=== Authentication Summary ===", fg="green"))
    click.echo("")
    click.echo(click.style(f"Successful: {success_count}", fg="green"))

    if failure_count > 0:
        click.echo(click.style(f"Failed: {failure_count}", fg="red"))
        click.echo("")
        click.echo("Failed domains:")
        for domain in failed_domains:
            click.echo(f"  - {domain}")
        click.echo("")
        click.echo("Troubleshooting:")
        click.echo(f"  1. Verify you're using account {REQUIRED_ACCOUNT}: aws sts get-caller-identity")
        click.echo(f"  2. Ensure you have the {REQUIRED_ROLE} role with CodeArtifact permissions")
        click.echo("  3. Check IAM permissions for CodeArtifact (GetAuthorizationToken, ReadFromRepository)")
        click.echo("  4. Ensure the domains and repositories exist")
        click.echo("")
        click.echo(click.style("Get fresh credentials from:", fg="blue"))
        click.echo(f"  {AWS_SSO_URL}")
        sys.exit(1)

    if success_count > 0:
        click.echo("")
        click.echo(click.style("Note: Tokens expire in 12 hours", fg="yellow"))
        click.echo(click.style("Note: pnpm will automatically use the npm configuration", fg="yellow"))
        click.echo("")

        # List available packages from each domain
        click.echo(click.style("=== Available Packages ===", fg="green"))
        click.echo("")

        for domain, repository, namespace in CODEARTIFACT_DOMAINS:
            click.echo(click.style(f"Domain: {domain} ({namespace})", fg="blue"))

            with console.status(f"[blue]Fetching packages from {domain}...", spinner="dots"):
                packages = authenticator.list_packages(domain, repository, profile)

                if packages:
                    for package in packages:
                        version = authenticator.get_package_version(domain, repository, package, namespace, profile)
                        if version:
                            click.echo(f"  - {namespace}/{package}@{version}")
                        else:
                            click.echo(f"  - {namespace}/{package}")
                else:
                    click.echo("  No packages found")

            click.echo("")
