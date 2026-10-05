"""Refresh expired/expiring credentials for all profiles."""

import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import click
from rich.console import Console
from rich.table import Table

from cli_tool.commands.aws_login.core.config import get_profile_config, list_aws_profiles
from cli_tool.commands.aws_login.core.credentials import (
    check_profile_needs_refresh,
    verify_credentials,
    write_default_credentials,
)
from cli_tool.core.ui.brand import spinner
from cli_tool.core.utils.config_manager import get_config_value

console = Console()

# Cap on concurrent `aws` subprocesses when verifying/renewing profiles.
_SILENT_MAX_WORKERS = 8

# Silent renewals share SSO tokens that may be renewed from a single-use
# refresh token, so two of them must never run at the same time (the monitor
# and a refresh-all can both start one).
_silent_lock = threading.Lock()


def _verify_in_parallel(profile_names: list) -> list:
    """Run `verify_credentials` for every profile concurrently.

    Returns one bool per profile, in input order (not completion order). An
    exception while verifying one profile counts as a failure for that profile
    only. Each check is an `aws` subprocess that mostly waits on the network,
    so threads are enough.
    """

    def _check(name) -> bool:
        try:
            return bool(verify_credentials(name))
        except Exception:
            return False

    if len(profile_names) <= 1:
        return [_check(name) for name in profile_names]

    with ThreadPoolExecutor(max_workers=min(_SILENT_MAX_WORKERS, len(profile_names))) as pool:
        return list(pool.map(_check, profile_names))


def _build_sso_login_cmd(first_profile: str) -> list:
    """Build the 'aws sso login' command for the given profile."""
    prof_config = get_profile_config(first_profile)
    if prof_config and "sso_session" in prof_config:
        return ["aws", "sso", "login", "--sso-session", prof_config["sso_session"]]
    return ["aws", "sso", "login", "--profile", first_profile]


def _verify_session_profiles(session_profs: list) -> tuple:
    """Verify credentials for each profile in the session.

    The checks run concurrently (the fresh login just renewed the shared SSO
    token, so they only fetch role credentials), but the results are printed
    in profile order once all of them are done.

    Returns (verified_count, failed_count, verified_profile_names).
    """
    console.print("[green]✓ Session refreshed successfully[/green]")
    verified = failed = 0
    verified_names = []
    for prof, ok in zip(session_profs, _verify_in_parallel(session_profs)):
        if ok:
            console.print(f"  ✓ {prof}")
            verified += 1
            verified_names.append(prof)
        else:
            console.print(f"  ✗ {prof} (verification failed)")
            failed += 1
    return verified, failed, verified_names


def _refresh_session(_session_key: str, session_profs: list) -> tuple:
    """Login to an SSO session and verify all profiles in it.

    Returns (success, verified_count, failed_count, verified_profile_names).
    """
    console.print(f"\n[blue]Refreshing session for {len(session_profs)} profile(s)...[/blue]")
    login_cmd = _build_sso_login_cmd(session_profs[0])

    try:
        result = subprocess.run(login_cmd, timeout=120)
        if result.returncode != 0:
            console.print("[red]✗ Session refresh failed[/red]")
            for prof in session_profs:
                console.print(f"  ✗ {prof}")
            return False, 0, len(session_profs), []

        verified, failed, verified_names = _verify_session_profiles(session_profs)
        return True, verified, failed, verified_names

    except subprocess.TimeoutExpired:
        console.print("[red]✗ Session refresh timed out[/red]")
        return False, 0, len(session_profs), []
    except KeyboardInterrupt:
        console.print("\n[yellow]Refresh cancelled[/yellow]")
        sys.exit(1)


def _classify_profiles(profiles: list, cached_only: bool = False) -> tuple:
    """Classify each profile as needing refresh or still valid.

    With ``cached_only`` the decision is made from the AWS CLI's credential
    cache (instant) instead of spawning ``aws`` for every profile; profiles
    with no cache entry count as needing a refresh.

    Returns (profiles_to_refresh, profiles_valid) where:
      - profiles_to_refresh: list of (prof, reason)
      - profiles_valid: list of (prof, time_remaining_str)
    """
    profiles_to_refresh = []
    profiles_valid = []

    for prof, _source in profiles:
        needs_refresh, expiration, reason = check_profile_needs_refresh(prof, cached_only=cached_only)
        if needs_refresh:
            profiles_to_refresh.append((prof, reason))
        elif expiration:
            now_utc = datetime.now(timezone.utc)
            time_left = expiration - now_utc
            hours = int(time_left.total_seconds() // 3600)
            minutes = int((time_left.total_seconds() % 3600) // 60)
            profiles_valid.append((prof, f"{hours}h {minutes}m remaining"))

    return profiles_to_refresh, profiles_valid


def _silent_refresh_profiles(profiles_to_refresh: list) -> tuple:
    """Renew credentials without any browser interaction.

    `aws sts get-caller-identity --profile X` makes the AWS CLI re-resolve the
    profile's credentials: it renews the role credentials from the cached SSO
    access token, and with `sso-session` configs it also renews that access
    token from its refresh token. It only fails when the SSO session itself is
    gone, which is the case that really needs `aws sso login`.

    Profiles that share an SSO session share its token, so the work is done
    in two phases to be both fast and safe:

      1. one "probe" profile per session, in parallel across sessions. If it
         fails, the rest of that session is reported as failed without trying
         (each try would cost a timeout). If it succeeds, the shared SSO
         access token has been renewed and cached.
      2. the remaining profiles of the sessions that passed, in parallel.
         They only need role credentials from an already-valid token.

    Never run several profiles of one session at once before the probe: the
    access token is renewed from a refresh token that may be single-use, so
    concurrent renewals could invalidate each other.

    Returns (renewed_profile_names, still_failing) in the input order, where
    still_failing keeps the original (profile, reason) tuples.
    """
    with _silent_lock:
        return _silent_refresh_locked(profiles_to_refresh)


def _silent_refresh_locked(profiles_to_refresh: list) -> tuple:
    entries = []
    for idx, (prof, reason) in enumerate(profiles_to_refresh):
        prof_config = get_profile_config(prof) or {}
        key = prof_config.get("sso_session") or prof_config.get("sso_start_url")
        entries.append((idx, prof, reason, key))

    # Phase 1 targets: the first profile of every session, plus every profile
    # without a session key (nothing to share, so each is its own probe).
    probes = []
    followers: dict = {}
    seen_sessions = set()
    for entry in entries:
        key = entry[3]
        if key is None or key not in seen_sessions:
            probes.append(entry)
            if key is not None:
                seen_sessions.add(key)
        else:
            followers.setdefault(key, []).append(entry)

    ok = {entry[0]: False for entry in entries}

    def _run(batch: list) -> list:
        return _verify_in_parallel([entry[1] for entry in batch])

    second_phase = []
    for entry, alive in zip(probes, _run(probes)):
        ok[entry[0]] = alive
        if alive and entry[3] is not None:
            second_phase.extend(followers.get(entry[3], []))

    for entry, alive in zip(second_phase, _run(second_phase)):
        ok[entry[0]] = alive

    renewed = [prof for idx, prof, _reason, _key in entries if ok[idx]]
    failing = [(prof, reason) for idx, prof, reason, _key in entries if not ok[idx]]
    return renewed, failing


def _show_valid_profiles_table(profiles_valid: list) -> None:
    """Render a Rich table of valid profiles and their remaining time."""
    table = Table(title="Profile Status")
    table.add_column("Profile", style="cyan")
    table.add_column("Time Remaining", style="green")
    for prof, time_info in profiles_valid:
        table.add_row(prof, time_info)
    console.print(table)


def _group_profiles_by_session(profiles_to_refresh: list) -> dict:
    """Group profiles by their SSO session key to minimise login prompts."""
    session_profiles = {}
    for prof, _reason in profiles_to_refresh:
        prof_config = get_profile_config(prof)
        if not prof_config:
            continue
        key = prof_config.get("sso_session") or prof_config.get("sso_start_url")
        if key:
            session_profiles.setdefault(key, []).append(prof)
    return session_profiles


def _confirm_refresh(profiles_to_refresh: list) -> bool:
    """Display profiles that need refresh and ask for user confirmation. Returns True if confirmed."""
    console.print(f"[yellow]Found {len(profiles_to_refresh)} profile(s) that need refresh:[/yellow]\n")
    for prof, reason in profiles_to_refresh:
        console.print(f"  • {prof}: {reason}")
    console.print("")
    return click.confirm("Refresh these profiles?", default=True)


def _refresh_all_sessions(session_profiles: dict) -> tuple:
    """Refresh each session group and aggregate counts.

    Returns (success_count, fail_count, verified_profile_names).
    """
    success_count = 0
    fail_count = 0
    all_verified = []
    for session_key, session_profs in session_profiles.items():
        _, verified, failed, verified_names = _refresh_session(session_key, session_profs)
        success_count += verified
        fail_count += failed
        all_verified.extend(verified_names)
    return success_count, fail_count, all_verified


def _update_default_credentials_after_refresh(refreshed_profiles: list) -> None:
    """Re-write [default] credentials if the configured default profile was refreshed."""
    default_profile = get_config_value("aws_login.default_credentials_profile")
    if not default_profile:
        return
    if default_profile not in refreshed_profiles:
        return

    console.print(f"\n[blue]Updating [default] credentials for '{default_profile}'...[/blue]")
    result = write_default_credentials(default_profile)
    if result:
        console.print("[green]✓ ~/.aws/credentials [default] updated[/green]")
        if result.get("expiration"):
            console.print(f"[dim]  Expires: {result['expiration']}[/dim]")
    else:
        console.print("[yellow]⚠ Could not update [default] credentials[/yellow]")


def refresh_all_profiles(force: bool = False):
    """Refresh all profiles that are expired or expiring soon.
    If force is True, refreshes all profiles regardless of expiration.
    """
    profiles = list_aws_profiles()
    if not profiles:
        console.print("[yellow]No AWS profiles found[/yellow]")
        sys.exit(0)

    with spinner("Checking all profiles for expiration..."):
        profiles_to_refresh, profiles_valid = _classify_profiles(profiles)

    if force:
        # If forced, move all valid profiles to the refresh list
        for prof, _ in profiles_valid:
            profiles_to_refresh.append((prof, "Forced refresh"))
        profiles_valid = []

    if not profiles_to_refresh:
        console.print("[green]✓ All profiles have valid credentials[/green]\n")
        if profiles_valid:
            _show_valid_profiles_table(profiles_valid)
        sys.exit(0)

    if not _confirm_refresh(profiles_to_refresh):
        console.print("[yellow]Refresh cancelled[/yellow]")
        sys.exit(0)

    # Group profiles by SSO session to minimize logins
    session_profiles = _group_profiles_by_session(profiles_to_refresh)

    success_count, fail_count, verified_profiles = _refresh_all_sessions(session_profiles)

    # Summary
    console.print("\n[blue]═══ Refresh Summary ═══[/blue]")
    console.print(f"[green]✓ Refreshed: {success_count}[/green]")
    if fail_count > 0:
        console.print(f"[red]✗ Failed: {fail_count}[/red]")

    if verified_profiles:
        _update_default_credentials_after_refresh(verified_profiles)
