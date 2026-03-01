"""AWS configuration file management."""

from pathlib import Path

from rich.console import Console

console = Console()


def get_aws_config_path():
    """Get AWS config file path."""
    return Path.home() / ".aws" / "config"


def get_aws_credentials_path():
    """Get AWS credentials file path."""
    return Path.home() / ".aws" / "credentials"


def parse_sso_config(profile_name):
    """Parse SSO configuration from AWS config file."""
    config_path = get_aws_config_path()
    if not config_path.exists():
        return None

    sso_config = {}
    in_profile = False
    current_profile = None
    profile_section = f"[profile {profile_name}]" if profile_name != "default" else "[default]"

    try:
        with open(config_path, "r") as f:
            for line in f:
                line = line.strip()

                # Check for profile section
                if line.startswith("[profile "):
                    current_profile = line[9:-1].strip()
                    in_profile = current_profile == profile_name
                elif line == profile_section:
                    in_profile = True
                elif line.startswith("["):
                    in_profile = False

                # Parse SSO settings
                if in_profile:
                    if "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()

                        if key in ["sso_start_url", "sso_region", "sso_account_id", "sso_role_name", "region", "sso_session"]:
                            sso_config[key] = value

        # If profile uses sso_session, get the session details
        if "sso_session" in sso_config:
            session_name = sso_config["sso_session"]
            session_section = f"[sso-session {session_name}]"
            in_session = False

            with open(config_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line == session_section:
                        in_session = True
                    elif line.startswith("["):
                        if in_session:
                            break
                        in_session = False
                    elif in_session and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()
                        # Add session config to sso_config
                        if key in ["sso_start_url", "sso_region"]:
                            sso_config[key] = value

        return sso_config if sso_config else None
    except Exception as e:
        console.print(f"[red]Error reading AWS config: {e}[/red]")
        return None


def list_aws_profiles():
    """List available AWS profiles from config."""
    config_path = get_aws_config_path()
    if not config_path.exists():
        return []

    profiles = []
    try:
        with open(config_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("[profile "):
                    profile_name = line[9:-1].strip()
                    profiles.append(profile_name)
                elif line == "[default]":
                    # Handle [default] profile
                    if "default" not in profiles:
                        profiles.append("default")
                # Skip sso-session sections
                elif line.startswith("[sso-session "):
                    continue

        return profiles
    except Exception:
        return []


def get_profile_config(profile_name):
    """Get configuration for a specific profile."""
    config_path = get_aws_config_path()
    if not config_path.exists():
        return None

    profile_config = {}
    in_profile = False
    profile_section = f"[profile {profile_name}]" if profile_name != "default" else "[default]"

    try:
        with open(config_path, "r") as f:
            for line in f:
                line = line.strip()
                if line == profile_section:
                    in_profile = True
                elif line.startswith("["):
                    if in_profile:
                        break
                    in_profile = False
                elif in_profile and "=" in line:
                    key, value = line.split("=", 1)
                    profile_config[key.strip()] = value.strip()

        # If profile uses sso_session, get the session details
        if "sso_session" in profile_config:
            session_name = profile_config["sso_session"]
            session_section = f"[sso-session {session_name}]"
            in_session = False

            with open(config_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line == session_section:
                        in_session = True
                    elif line.startswith("["):
                        if in_session:
                            break
                        in_session = False
                    elif in_session and "=" in line:
                        key, value = line.split("=", 1)
                        # Add session config to profile config
                        profile_config[key.strip()] = value.strip()

        return profile_config if profile_config else None
    except Exception:
        return None


def get_existing_sso_sessions():
    """Get existing SSO sessions from config."""
    config_path = get_aws_config_path()
    if not config_path.exists():
        return {}

    sessions = {}
    current_section = None
    session_config = {}

    try:
        with open(config_path, "r") as f:
            for line in f:
                line = line.strip()

                # Check for SSO session section
                if line.startswith("[sso-session "):
                    if current_section and session_config:
                        sessions[current_section] = session_config
                    current_section = line[13:-1].strip()
                    session_config = {}
                elif line.startswith("["):
                    if current_section and session_config:
                        sessions[current_section] = session_config
                    current_section = None
                    session_config = {}
                elif current_section and "=" in line:
                    key, value = line.split("=", 1)
                    session_config[key.strip()] = value.strip()

            # Add last session
            if current_section and session_config:
                sessions[current_section] = session_config

        return sessions
    except Exception:
        return {}
