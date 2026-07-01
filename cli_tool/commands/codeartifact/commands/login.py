"""CodeArtifact login command."""

import sys

import click
from rich.console import Console

from cli_tool.commands.codeartifact.core.authenticator import CodeArtifactAuthenticator
from cli_tool.core.utils.aws import check_aws_cli

console = Console()


def _load_domain_configs():
    """Load full domain configs from ~/.devo/config.json. Returns list of dicts with keys:
    domain, repository, namespace, account_id, profile, region."""
    from cli_tool.core.utils.config_manager import get_config_value

    global_region = get_config_value("codeartifact.region", "us-east-1")
    domains = get_config_value("codeartifact.domains", [])
    result = []
    for d in domains:
        result.append(
            {
                "domain": d["domain"],
                "repository": d["repository"],
                "namespace": d.get("namespace", ""),
                "account_id": d.get("account_id", ""),
                "profile": d.get("profile", ""),
                "region": d.get("region", global_region),
            }
        )
    return result


def _resolve_profile(domain_cfg: dict, cli_profile: str | None) -> str | None:
    return domain_cfg.get("profile") or cli_profile


def _resolve_region(domain_cfg: dict) -> str:
    return domain_cfg["region"]


def _display_failed_domains(failed_domains: list) -> None:
    click.echo(click.style(f"Failed: {len(failed_domains)}", fg="red"))
    click.echo("")
    click.echo("Failed domains:")
    for domain in failed_domains:
        click.echo(f"  - {domain}")
    click.echo("")
    click.echo("Troubleshooting:")
    click.echo("  1. Verify your profile has valid SSO credentials: devo aws-login refresh")
    click.echo("  2. Ensure the profile has CodeArtifact permissions (GetAuthorizationToken)")
    click.echo("  3. Ensure the domain and repository exist in the target account")
    click.echo("")


def _list_available_packages(auth, domain_cfgs: list[dict], cli_profile: str | None) -> None:
    click.echo(click.style("=== Available Packages ===", fg="green"))
    click.echo("")

    for dc in domain_cfgs:
        profile = _resolve_profile(dc, cli_profile)
        region = _resolve_region(dc)
        label = f"{dc['domain']}/{dc['repository']}"
        if dc["namespace"]:
            label += f" ({dc['namespace']})"
        click.echo(click.style(f"Domain: {label}", fg="blue"))

        with console.status(f"[blue]Fetching packages from {dc['domain']}...", spinner="dots"):
            packages_with_versions = auth.list_packages_with_versions(
                dc["domain"],
                dc["repository"],
                dc["namespace"],
                profile,
                region,
            )

        if packages_with_versions:
            for package, version in sorted(packages_with_versions.items()):
                if version:
                    click.echo(f"  - {package}@{version}")
                else:
                    click.echo(f"  - {package}")
        else:
            click.echo("  No packages found")

        click.echo("")


@click.command()
@click.pass_context
def codeartifact_login(ctx):
    """Login to AWS CodeArtifact for npm access.

    Authenticates with configured CodeArtifact domains and repositories.
    Supports multi-account: each domain can specify its own profile and region.

    Examples:
      devo codeartifact-login
      devo --profile my-profile codeartifact-login
    """
    from cli_tool.core.utils.aws import select_profile

    cli_profile = select_profile(ctx.obj.get("profile"))
    domain_cfgs = _load_domain_configs()

    if not domain_cfgs:
        click.echo(click.style("No CodeArtifact domains configured.", fg="yellow"))
        click.echo("Add domains to ~/.devo/config.json under codeartifact.domains")
        sys.exit(1)

    click.echo(click.style("=== CodeArtifact Multi-Domain Login ===", fg="green"))
    click.echo("")

    if not check_aws_cli():
        sys.exit(1)

    # Show what we're working with
    if cli_profile:
        click.echo(click.style(f"CLI profile: {cli_profile}", fg="green"))
    click.echo(click.style(f"Domains configured: {len(domain_cfgs)}", fg="blue"))
    click.echo("")

    # Authenticate each domain with its own profile/region
    success_count = 0
    failed_domains = []

    for dc in domain_cfgs:
        profile = _resolve_profile(dc, cli_profile)
        region = _resolve_region(dc)
        label = f"{dc['domain']}/{dc['repository']}"
        if dc["namespace"]:
            label += f" ({dc['namespace']})"
        extra = f" [profile={profile}, region={region}]" if profile else f" [region={region}]"

        with console.status(f"[yellow]Authenticating with {label}{extra}...", spinner="dots"):
            auth = CodeArtifactAuthenticator(region, [(dc["domain"], dc["repository"], dc["namespace"])])
            success, error = auth.authenticate_domain(
                dc["domain"],
                dc["repository"],
                dc["namespace"],
                profile,
                region,
            )

        if success:
            click.echo(click.style(f"✓ {label}", fg="green"))
            success_count += 1
        else:
            click.echo(click.style(f"✗ {label} — {error or 'Authentication failed'}", fg="red"))
            failed_domains.append(label)

        click.echo("")

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
        # Reuse the last authenticator (any region works for listing)
        _list_available_packages(auth, domain_cfgs, cli_profile)
