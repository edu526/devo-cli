import os
import subprocess
import sys

import click
from rich.console import Console

from cli_tool.config import AWS_SSO_URL, CODEARTIFACT_DOMAINS, CODEARTIFACT_REGION
from cli_tool.utils.aws import check_aws_cli
from cli_tool.utils.aws_profile import (
    REQUIRED_ACCOUNT,
    REQUIRED_ROLE,
    verify_aws_credentials,
)

# Configuration
REGION = CODEARTIFACT_REGION
DOMAINS = CODEARTIFACT_DOMAINS

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
    # Get profile from context
    profile = ctx.obj.get("profile") if ctx.obj else None

    if not profile:
        profile = os.environ.get("AWS_PROFILE")

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
        click.echo(
            click.style(
                f"Current credentials are for account: {account_id}", fg="yellow"
            )
        )
        click.echo(click.style(f"Required account: {REQUIRED_ACCOUNT}", fg="yellow"))
        click.echo("")
        click.echo(
            click.style("Get credentials for the correct account from:", fg="blue")
        )
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

    click.echo(click.style(f"Region: {REGION}", fg="blue"))
    click.echo("")

    # Track success/failure
    success_count = 0
    failure_count = 0
    failed_domains = []

    # Login to each domain
    for domain, repository, namespace in DOMAINS:
        cmd = [
            "aws",
            "codeartifact",
            "login",
            "--tool",
            "npm",
            "--domain",
            domain,
            "--repository",
            repository,
            "--namespace",
            namespace,
            "--region",
            REGION,
        ]

        if profile:
            cmd.extend(["--profile", profile])

        with console.status(
            f"[yellow]Authenticating with {domain}/{repository} ({namespace})...",
            spinner="dots",
        ):
            try:
                result = subprocess.run(
                    cmd, check=True, capture_output=True, text=True, timeout=30
                )
                click.echo(
                    click.style(
                        f"✓ Successfully authenticated with {domain}/{repository} ({namespace})",
                        fg="green",
                    )
                )
                success_count += 1
            except subprocess.TimeoutExpired:
                click.echo(
                    click.style(
                        f"✗ Timeout authenticating with {domain}/{repository} ({namespace})",
                        fg="red",
                    )
                )
                failure_count += 1
                failed_domains.append(f"{domain}/{repository} ({namespace})")
            except subprocess.CalledProcessError as e:
                click.echo(
                    click.style(
                        f"✗ Failed to authenticate with {domain}/{repository} ({namespace})",
                        fg="red",
                    )
                )
                if e.stderr:
                    click.echo(e.stderr)
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
        click.echo(
            f"  1. Verify you're using account {REQUIRED_ACCOUNT}: aws sts get-caller-identity"
        )
        click.echo(
            f"  2. Ensure you have the {REQUIRED_ROLE} role with CodeArtifact permissions"
        )
        click.echo(
            "  3. Check IAM permissions for CodeArtifact (GetAuthorizationToken, ReadFromRepository)"
        )
        click.echo("  4. Ensure the domains and repositories exist")
        click.echo("")
        click.echo(click.style("Get fresh credentials from:", fg="blue"))
        click.echo(f"  {AWS_SSO_URL}")
        sys.exit(1)

    if success_count > 0:
        click.echo("")
        click.echo(click.style("Note: Tokens expire in 12 hours", fg="yellow"))
        click.echo(
            click.style(
                "Note: pnpm will automatically use the npm configuration", fg="yellow"
            )
        )
        click.echo("")

        # List available packages from each domain
        click.echo(click.style("=== Available Packages ===", fg="green"))
        click.echo("")

        for domain, repository, namespace in DOMAINS:
            click.echo(click.style(f"Domain: {domain} ({namespace})", fg="blue"))

            list_cmd = [
                "aws",
                "codeartifact",
                "list-packages",
                "--domain",
                domain,
                "--repository",
                repository,
                "--region",
                REGION,
                "--format",
                "npm",
                "--query",
                "packages[].package",
                "--output",
                "text",
            ]

            if profile:
                list_cmd.extend(["--profile", profile])

            with console.status(
                f"[blue]Fetching packages from {domain}...", spinner="dots"
            ):
                try:
                    result = subprocess.run(
                        list_cmd, capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        packages = result.stdout.strip().split("\t")
                        for package in packages:
                            if package:
                                # Try to get latest version
                                version_cmd = [
                                    "aws",
                                    "codeartifact",
                                    "list-package-versions",
                                    "--domain",
                                    domain,
                                    "--repository",
                                    repository,
                                    "--format",
                                    "npm",
                                    "--package",
                                    package,
                                    "--namespace",
                                    namespace,
                                    "--region",
                                    REGION,
                                    "--query",
                                    "versions[0].version",
                                    "--output",
                                    "text",
                                ]

                                if profile:
                                    version_cmd.extend(["--profile", profile])

                                try:
                                    version_result = subprocess.run(
                                        version_cmd,
                                        capture_output=True,
                                        text=True,
                                        timeout=5,
                                    )
                                    if (
                                        version_result.returncode == 0
                                        and version_result.stdout.strip()
                                    ):
                                        version = version_result.stdout.strip()
                                        if version and version != "None":
                                            click.echo(
                                                f"  - {namespace}/{package}@{version}"
                                            )
                                        else:
                                            click.echo(f"  - {namespace}/{package}")
                                    else:
                                        click.echo(f"  - {namespace}/{package}")
                                except Exception:
                                    click.echo(f"  - {namespace}/{package}")
                    else:
                        click.echo("  No packages found")
                except Exception:
                    click.echo("  Could not list packages")

            click.echo("")


if __name__ == "__main__":
    codeartifact_login()
