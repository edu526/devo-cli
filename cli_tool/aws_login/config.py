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
    """
    List available AWS profiles from both config and credentials files.

    Returns:
        List of tuples (profile_name, source) where source is:
        - 'sso': Profile only in config with SSO configuration
        - 'static': Profile only in credentials
        - 'both': Profile in both config and credentials
        - 'config': Profile in config without SSO
    """
    config_profiles = {}  # profile_name -> has_sso
    credentials_profiles = set()

    # Read from ~/.aws/config
    config_path = get_aws_config_path()
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                current_profile = None
                has_sso = False

                for line in f:
                    line = line.strip()

                    # Check for profile section
                    if line.startswith("[profile "):
                        # Save previous profile
                        if current_profile:
                            config_profiles[current_profile] = has_sso
                        # Start new profile
                        current_profile = line[9:-1].strip()
                        has_sso = False
                    elif line == "[default]":
                        # Save previous profile
                        if current_profile:
                            config_profiles[current_profile] = has_sso
                        # Start default profile
                        current_profile = "default"
                        has_sso = False
                    elif line.startswith("[sso-session "):
                        # Save previous profile and skip sso-session sections
                        if current_profile:
                            config_profiles[current_profile] = has_sso
                        current_profile = None
                        has_sso = False
                    elif current_profile and ("sso_" in line or line.startswith("sso_")):
                        # Profile has SSO configuration
                        has_sso = True

                # Save last profile
                if current_profile:
                    config_profiles[current_profile] = has_sso
        except Exception:
            pass

    # Read from ~/.aws/credentials
    credentials_path = get_aws_credentials_path()
    if credentials_path.exists():
        try:
            with open(credentials_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("[") and line.endswith("]"):
                        profile_name = line[1:-1].strip()
                        credentials_profiles.add(profile_name)
        except Exception:
            pass

    # Combine results with source information
    all_profiles = set(config_profiles.keys()) | credentials_profiles
    result = []

    for profile in sorted(all_profiles):
        in_config = profile in config_profiles
        in_credentials = profile in credentials_profiles
        has_sso = config_profiles.get(profile, False)

        if in_config and in_credentials:
            source = "both"
        elif in_credentials:
            source = "static"
        elif has_sso:
            source = "sso"
        else:
            source = "config"

        result.append((profile, source))

    return result


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
