"""AWS credentials management and expiration checking."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console

from cli_tool.commands.aws_login.core.config import get_profile_config

console = Console()


def get_sso_cache_token(sso_start_url):
    """Get cached SSO token if available and valid."""
    cache_dir = Path.home() / ".aws" / "sso" / "cache"
    if not cache_dir.exists():
        return None

    try:
        # Find cache file for this SSO start URL
        for cache_file in cache_dir.glob("*.json"):
            with open(cache_file, "r") as f:
                cache_data = json.load(f)

                if cache_data.get("startUrl") == sso_start_url:
                    # Check if token is still valid
                    expires_at = cache_data.get("expiresAt")
                    if expires_at:
                        expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                        if expires_dt > datetime.now(expires_dt.tzinfo):
                            return cache_data.get("accessToken")

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
            with open(cache_file, "r") as f:
                cache_data = json.load(f)

                if cache_data.get("startUrl") == sso_start_url:
                    expires_at = cache_data.get("expiresAt")
                    if expires_at:
                        expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                        return expires_dt

        return None
    except Exception:
        return None


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
                expiration_dt = datetime.fromisoformat(expiration_str.replace("Z", "+00:00"))
                return expiration_dt

        return None
    except Exception:
        return None


def check_profile_needs_refresh(profile_name, threshold_minutes=10):
    """Check if a profile needs credential refresh.

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
