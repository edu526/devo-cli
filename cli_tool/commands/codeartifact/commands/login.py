"""CodeArtifact login command."""

import sys

import click
from rich.console import Console

from cli_tool.commands.codeartifact.core.authenticator import CodeArtifactAuthenticator
from cli_tool.config import AWS_ACCOUNT_ID as REQUIRED_ACCOUNT
from cli_tool.config import AWS_REQUIRED_ROLE as REQUIRED_ROLE
from cli_tool.config import (
    AWS_SSO_URL,
    CODEARTIFACT_DOMAINS,
    CODEARTIFACT_REGION,
)
from cli_tool.core.utils.aws import check_aws_cli, verify_aws_credentials

console = Console()


def _display_failed_domains(failed_domains: list) -> None:
    """Print failure summary and troubleshooting tips."""
    click.echo(click.style(f"Failed: {len(failed_domains)}", fg="red"))
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


def _list_available_packages(authenticator, profile) -> None:
    """Print available packages from each configured domain."""
    click.echo(click.style("=== Available Packages ===", fg="green"))
    click.echo("")

    for domain, repository, namespace in CODEARTIFACT_DOMAINS:
        click.echo(click.style(f"Domain: {domain} ({namespace})", fg="blue"))

        with console.status(f"[blue]Fetching packages from {domain}...", spinner="dots"):
            packages_with_versions = authenticator.list_packages_with_versions(domain, repository, namespace, profile)

        if packages_with_versions:
            for package, version in sorted(packages_with_versions.items()):
                if version:
                    click.echo(f"  - {package}@{version}")
                else:
                    click.echo(f"  - {package}")
        else:
            click.echo("  No packages found")

        click.echo("")


def _verify_credentials_or_exit(profile) -> tuple:
    """Verify AWS credentials and account, exit on failure. Returns (account_id, user_arn)."""
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

    return account_id, user_arn


def _authenticate_all_domains(authenticator, profile) -> tuple:
    """Authenticate with all configured domains. Returns (success_count, failed_domains)."""
    success_count = 0
    failed_domains = []

    for domain, repository, namespace in CODEARTIFACT_DOMAINS:
        with console.status(f"[yellow]Authenticating with {domain}/{repository} ({namespace})...", spinner="dots"):
            success, error = authenticator.authenticate_domain(domain, repository, namespace, profile)

        if success:
            click.echo(click.style(f"✓ Successfully authenticated with {domain}/{repository} ({namespace})", fg="green"))
            success_count += 1
        else:
            click.echo(click.style(f"✗ Failed to authenticate with {domain}/{repository} ({namespace})", fg="red"))
            if error:
                click.echo(error)
            failed_domains.append(f"{domain}/{repository} ({namespace})")

        click.echo("")

    return success_count, failed_domains


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
    from cli_tool.core.utils.aws import select_profile

    profile = select_profile(ctx.obj.get("profile"))

    click.echo(click.style("=== CodeArtifact Multi-Domain Login ===", fg="green"))
    click.echo("")
    click.echo(click.style(f"Required AWS Account: {REQUIRED_ACCOUNT}", fg="blue"))
    click.echo(click.style(f"Required IAM Role: {REQUIRED_ROLE}", fg="blue"))
    click.echo("")

    if not check_aws_cli():
        sys.exit(1)

    account_id, user_arn = _verify_credentials_or_exit(profile)

    if profile:
        click.echo(click.style(f"Using profile: {profile}", fg="green"))
    else:
        click.echo(click.style("Using active AWS credentials", fg="green"))

    click.echo(click.style(f"Account: {account_id}", fg="blue"))
    click.echo(click.style(f"User: {user_arn}", fg="blue"))
    click.echo("")

    if REQUIRED_ROLE not in user_arn:
        click.echo(click.style(f"Warning: User ARN does not contain '{REQUIRED_ROLE}' role", fg="yellow"))
        click.echo("Please ensure you have the necessary CodeArtifact permissions")
        click.echo("")
        if not click.confirm("Continue anyway?"):
            click.echo("Aborted")
            sys.exit(1)

    click.echo(click.style(f"Region: {CODEARTIFACT_REGION}", fg="blue"))
    click.echo("")

    authenticator = CodeArtifactAuthenticator(CODEARTIFACT_REGION, CODEARTIFACT_DOMAINS)
    success_count, failed_domains = _authenticate_all_domains(authenticator, profile)

    click.echo(click.style("=== Authentication Summary ===", fg="green"))
    click.echo("")
    click.echo(click.style(f"Successful: {success_count}", fg="green"))

    if failed_domains:
        _display_failed_domains(failed_domains)
        sys.exit(1)

    if success_count > 0:
        click.echo("")
        click.echo(click.style("Note: Tokens expire in 12 hours", fg="yellow"))
        click.echo(click.style("Note: pnpm will automatically use the npm configuration", fg="yellow"))
        click.echo("")
        _list_available_packages(authenticator, profile)
