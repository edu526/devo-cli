"""AWS credentials management and expiration checking."""

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console

from cli_tool.commands.aws_login.core.config import get_aws_credentials_path, get_profile_config, remove_section_from_file

_UTC_OFFSET = "+00:00"

console = Console()

_SSO_START_URL_KEY = "startUrl"
_EXPIRES_AT_KEY = "expiresAt"
_ACCESS_TOKEN_KEY = "accessToken"


def get_sso_cache_token(sso_start_url):
    """Get cached SSO token if available and valid."""
    cache_dir = Path.home() / ".aws" / "sso" / "cache"
    if not cache_dir.exists():
        return None

    try:
        # Find cache file for this SSO start URL
        for cache_file in cache_dir.glob("*.json"):
            with cache_file.open("r") as f:
                cache_data = json.load(f)

                if cache_data.get(_SSO_START_URL_KEY) == sso_start_url:
                    # Check if token is still valid
                    expires_at = cache_data.get(_EXPIRES_AT_KEY)
                    if expires_at:
                        expires_dt = datetime.fromisoformat(expires_at.replace("Z", _UTC_OFFSET))
                        if expires_dt > datetime.now(expires_dt.tzinfo):
                            return cache_data.get(_ACCESS_TOKEN_KEY)

        return None
    except Exception:
        return None


def get_sso_token_expiration(sso_start_url):
    """Get SSO token expiration time."""
    cache_dir = Path.home() / ".aws" / "sso" / "cache"
    if not cache_dir.exists():
        return None

    try:
        # Find cache file for this SSO start URL
        for cache_file in cache_dir.glob("*.json"):
            with cache_file.open("r") as f:
                cache_data = json.load(f)

                if cache_data.get(_SSO_START_URL_KEY) == sso_start_url:
                    expires_at = cache_data.get(_EXPIRES_AT_KEY)
                    if expires_at:
                        expires_dt = datetime.fromisoformat(expires_at.replace("Z", _UTC_OFFSET))
                        return expires_dt

        return None
    except Exception:
        return None


def write_default_credentials(profile_name):
    """Export temporary credentials for a profile and write them as [default] in ~/.aws/credentials.

    Replaces any existing [default] section in the credentials file.

    Returns:
        dict with keys 'expiration' (str or None) on success, or None on failure.
    """
    try:
        cmd = ["aws", "configure", "export-credentials", "--profile", profile_name]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

        if result.returncode != 0:
            console.print(f"[red]Could not export credentials for '{profile_name}': {result.stderr.strip()}[/red]")
            return None

        creds = json.loads(result.stdout)
        access_key = creds.get("AccessKeyId")
        secret_key = creds.get("SecretAccessKey")
        session_token = creds.get("SessionToken")
        expiration = creds.get("Expiration")

        if not access_key or not secret_key:
            console.print("[red]Incomplete credentials received — missing AccessKeyId or SecretAccessKey[/red]")
            return None

    except subprocess.TimeoutExpired:
        console.print("[red]Timed out while exporting credentials[/red]")
        return None
    except Exception as e:
        console.print(f"[red]Error exporting credentials: {e}[/red]")
        return None

    # Get region from profile config
    profile_config = get_profile_config(profile_name)
    region = profile_config.get("region") if profile_config else None

    credentials_path = get_aws_credentials_path()
    credentials_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing [default] section before writing
    remove_section_from_file(credentials_path, "[default]")

    # Append new [default] section
    try:
        new_section = "[default]\n"
        new_section += f"aws_access_key_id = {access_key}\n"
        new_section += f"aws_secret_access_key = {secret_key}\n"
        if session_token:
            new_section += f"aws_session_token = {session_token}\n"
        if region:
            new_section += f"region = {region}\n"

        with open(credentials_path, "a") as f:
            f.write("\n")
            f.write(new_section)

        return {"expiration": expiration}
    except Exception as e:
        console.print(f"[red]Error writing credentials file: {e}[/red]")
        return None


def _cli_credential_cache_key(profile_config):
    """Name (without extension) of the AWS CLI's cache file for an SSO profile.

    The CLI stores the role credentials it fetched in
    ``~/.aws/cli/cache/<sha1>.json``, where the hash is over the JSON of the
    SSO identity: the session name (or the start URL for legacy profiles),
    the role and the account. This is a CLI implementation detail (verified
    against AWS CLI 2.x with ``sso-session`` profiles), so callers must treat
    a missing file as "unknown", never as "expired".
    """
    if profile_config.get("sso_session"):
        identity = {
            "sessionName": profile_config["sso_session"],
            "roleName": profile_config.get("sso_role_name"),
            "accountId": profile_config.get("sso_account_id"),
        }
    elif profile_config.get("sso_start_url"):
        identity = {
            "startUrl": profile_config["sso_start_url"],
            "roleName": profile_config.get("sso_role_name"),
            "accountId": profile_config.get("sso_account_id"),
        }
    else:
        return None
    return hashlib.sha1(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def read_cached_credentials_expiration(profile_name):
    """Expiration of the role credentials the AWS CLI has cached for a profile.

    Pure file read: no subprocess, no network and, unlike
    ``get_profile_credentials_expiration``, no side effects (it never renews
    anything). That makes it ~1000x faster than spawning ``aws`` per profile.

    Returns a datetime, which may be in the past (cached but expired), or
    None when there is no usable cache entry for the profile.
    """
    try:
        profile_config = get_profile_config(profile_name)
        if not profile_config:
            return None
        key = _cli_credential_cache_key(profile_config)
        if not key:
            return None

        cache_file = Path.home() / ".aws" / "cli" / "cache" / f"{key}.json"
        if not cache_file.is_file():
            return None

        with cache_file.open("r", encoding="utf-8") as f:
            expiration_str = (json.load(f).get("Credentials") or {}).get("Expiration")
        if not expiration_str:
            return None
        return datetime.fromisoformat(expiration_str.replace("Z", _UTC_OFFSET))
    except Exception:
        return None


def clear_cached_role_credentials(profile_name):
    """Delete the AWS CLI's cached role credentials for one profile.

    ``aws sso login`` only renews the SSO session token; the role credentials
    the CLI already cached keep being used until they expire. A forced
    re-login (e.g. after a permission change) must drop them so the next call
    fetches new ones. Only this profile's cache file is touched.

    Returns True if a file was removed.
    """
    try:
        profile_config = get_profile_config(profile_name)
        key = _cli_credential_cache_key(profile_config) if profile_config else None
        if not key:
            return False
        cache_file = Path.home() / ".aws" / "cli" / "cache" / f"{key}.json"
        if cache_file.is_file():
            cache_file.unlink()
            return True
        return False
    except Exception:
        return False


def get_profile_credentials_expiration(profile_name):
    """Get the expiration time of cached credentials for a profile.

    Returns the expiration datetime of the temporary AWS credentials.
    Uses AWS CLI's credential resolution to get the correct credentials.
    """
    try:
        # Use AWS CLI to get credentials with expiration
        # This uses the same credential resolution logic as AWS CLI
        cmd = ["aws", "configure", "export-credentials", "--profile", profile_name]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            creds = json.loads(result.stdout)
            expiration_str = creds.get("Expiration")

            if expiration_str:
                # Parse expiration time (format: 2026-03-01T05:30:29+00:00)
                expiration_dt = datetime.fromisoformat(expiration_str.replace("Z", _UTC_OFFSET))
                return expiration_dt

        return None
    except Exception:
        return None


def check_profile_credentials_available(profile_name):
    """Check if a profile's credentials can be exported (i.e. not expired / not missing).

    Returns:
        tuple: (available: bool, error_message: str | None)
            available=True  → credentials are accessible (may or may not have expiration)
            available=False → credentials are expired, missing, or the export failed
    """
    try:
        cmd = ["aws", "configure", "export-credentials", "--profile", profile_name]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            return True, None

        stderr = result.stderr.strip()
        return False, stderr if stderr else "Could not export credentials"
    except subprocess.TimeoutExpired:
        return False, "Timed out while checking credentials"
    except Exception as e:
        return False, str(e)


def check_profile_needs_refresh(profile_name, threshold_minutes=10, cached_only=False):
    """Check if a profile needs credential refresh.

    By default the expiration comes from ``aws configure export-credentials``,
    which also renews the credentials silently when it can (one subprocess per
    profile). With ``cached_only=True`` it only reads the AWS CLI's credential
    cache: instant and side-effect free, but a profile without a cache entry is
    reported as needing a refresh instead of being renewed on the spot.

    Returns:
      tuple: (needs_refresh, expiration_time, reason)
    """
    # Get profile config (this merges sso-session config if present)
    profile_config = get_profile_config(profile_name)
    if not profile_config:
        return False, None, "Profile not found"

    # Check if it's an SSO profile (either legacy or new format)
    has_sso_session = "sso_session" in profile_config
    has_sso_url = "sso_start_url" in profile_config

    if not has_sso_session and not has_sso_url:
        return False, None, "Not an SSO profile"

    # Get expiration time of cached credentials (not SSO token)
    if cached_only:
        expiration = read_cached_credentials_expiration(profile_name)
    else:
        expiration = get_profile_credentials_expiration(profile_name)

    if not expiration:
        return True, None, "No valid credentials found"

    # Check if expired or expiring soon
    # IMPORTANT: expiration is in UTC, so we need to compare with UTC time
    now_utc = datetime.now(timezone.utc)
    time_left = expiration - now_utc

    if time_left.total_seconds() <= 0:
        return True, expiration, "Expired"
    elif time_left.total_seconds() <= (threshold_minutes * 60):
        minutes_left = int(time_left.total_seconds() / 60)
        return True, expiration, f"Expiring in {minutes_left} minutes"

    return False, expiration, "Valid"


def verify_credentials(profile_name):
    """Verify if credentials are valid and show info."""
    cmd = ["aws", "sts", "get-caller-identity", "--profile", profile_name, "--output", "json"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            identity = json.loads(result.stdout)
            return {
                "account": identity.get("Account"),
                "arn": identity.get("Arn"),
                "user_id": identity.get("UserId"),
            }
        return None
    except Exception:
        return None
