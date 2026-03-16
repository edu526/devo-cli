"""AWS configuration file management."""

from pathlib import Path

from rich.console import Console

console = Console()

_DEFAULT_PROFILE = "[default]"
_SSO_START_URL = "sso_start_url"
_SSO_REGION = "sso_region"
_SSO_ACCOUNT_ID = "sso_account_id"
_SSO_ROLE_NAME = "sso_role_name"
_SSO_SESSION = "sso_session"
_SSO_KEYS = {_SSO_START_URL, _SSO_REGION, _SSO_ACCOUNT_ID, _SSO_ROLE_NAME, "region", _SSO_SESSION}


def _merge_sso_session(config_path: Path, session_name: str, target: dict) -> None:
    """Read an [sso-session <name>] block and merge sso_start_url/sso_region into target."""
    session_section = f"[sso-session {session_name}]"
    in_session = False
    try:
        with config_path.open("r") as f:
            for line in f:
                line = line.strip()
                if line == session_section:
                    in_session = True
                elif line.startswith("["):
                    if in_session:
                        break
                elif in_session and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    if key in (_SSO_START_URL, _SSO_REGION):
                        target[key] = value.strip()
    except Exception:
        pass


def get_aws_config_path():
    """Get AWS config file path."""
    return Path.home() / ".aws" / "config"


def get_aws_credentials_path():
    """Get AWS credentials file path."""
    return Path.home() / ".aws" / "credentials"


def _get_profile_section(profile_name: str) -> str:
    """Return the INI section header for a given profile name."""
    return _DEFAULT_PROFILE if profile_name == "default" else f"[profile {profile_name}]"


def _parse_profile_line(line: str, profile_name: str, current_profile: str, in_profile: bool):
    """Update in_profile state based on the current line.

    Returns (current_profile, in_profile).
    """
    if line.startswith("[profile "):
        new_profile = line[9:-1].strip()
        return new_profile, new_profile == profile_name
    if line == _DEFAULT_PROFILE:
        return "default", profile_name == "default"
    if line.startswith("["):
        return current_profile, False
    return current_profile, in_profile


def parse_sso_config(profile_name):
    """Parse SSO configuration from AWS config file."""
    config_path = get_aws_config_path()
    if not config_path.exists():
        return None

    sso_config = {}
    in_profile = False
    current_profile = None

    try:
        with config_path.open("r") as f:
            for line in f:
                line = line.strip()

                if line.startswith("["):
                    current_profile, in_profile = _parse_profile_line(line, profile_name, current_profile, in_profile)
                elif in_profile and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    if key in _SSO_KEYS:
                        sso_config[key] = value.strip()

        if _SSO_SESSION in sso_config:
            _merge_sso_session(config_path, sso_config[_SSO_SESSION], sso_config)

        return sso_config if sso_config else None
    except Exception as e:
        console.print(f"[red]Error reading AWS config: {e}[/red]")
        return None


def _flush_profile(current_profile: str, has_sso: bool, config_profiles: dict) -> None:
    """Save the current profile entry into config_profiles if a profile is active."""
    if current_profile is not None:
        config_profiles[current_profile] = has_sso


def _parse_config_line(line: str, current_profile, has_sso: bool, config_profiles: dict) -> tuple:
    """Process a single line from the AWS config file.

    Returns (current_profile, has_sso) reflecting the updated parser state.
    """
    if line.startswith("[profile "):
        _flush_profile(current_profile, has_sso, config_profiles)
        return line[9:-1].strip(), False
    if line == _DEFAULT_PROFILE:
        _flush_profile(current_profile, has_sso, config_profiles)
        return "default", False
    if line.startswith("[sso-session "):
        _flush_profile(current_profile, has_sso, config_profiles)
        return None, False
    if current_profile and ("sso_" in line or line.startswith("sso_")):
        return current_profile, True
    return current_profile, has_sso


def _read_config_profiles(config_path: Path) -> dict:
    """Read profile names and SSO presence from ~/.aws/config.

    Returns a dict mapping profile_name -> has_sso (bool).
    """
    config_profiles = {}
    current_profile = None
    has_sso = False

    try:
        with config_path.open("r") as f:
            for line in f:
                current_profile, has_sso = _parse_config_line(line.strip(), current_profile, has_sso, config_profiles)

        _flush_profile(current_profile, has_sso, config_profiles)
    except Exception:
        pass

    return config_profiles


def _read_credentials_profiles(credentials_path: Path) -> set:
    """Read profile names from ~/.aws/credentials."""
    profiles = set()
    try:
        with credentials_path.open("r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("[") and line.endswith("]"):
                    profiles.add(line[1:-1].strip())
    except Exception:
        pass
    return profiles


def _classify_profile(profile: str, config_profiles: dict, credentials_profiles: set) -> str:
    """Return the source label for a profile."""
    in_config = profile in config_profiles
    in_credentials = profile in credentials_profiles
    has_sso = config_profiles.get(profile, False)

    if in_config and in_credentials:
        return "both"
    if in_credentials:
        return "static"
    if has_sso:
        return "sso"
    return "config"


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
    config_profiles = {}
    credentials_profiles = set()

    config_path = get_aws_config_path()
    if config_path.exists():
        config_profiles = _read_config_profiles(config_path)

    credentials_path = get_aws_credentials_path()
    if credentials_path.exists():
        credentials_profiles = _read_credentials_profiles(credentials_path)

    all_profiles = set(config_profiles.keys()) | credentials_profiles
    return [(p, _classify_profile(p, config_profiles, credentials_profiles)) for p in sorted(all_profiles, key=str.lower)]


def get_profile_config(profile_name):
    """Get configuration for a specific profile."""
    config_path = get_aws_config_path()
    if not config_path.exists():
        return None

    profile_config = {}
    in_profile = False
    profile_section = _get_profile_section(profile_name)

    try:
        with config_path.open("r") as f:
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

        if _SSO_SESSION in profile_config:
            _merge_sso_session(config_path, profile_config[_SSO_SESSION], profile_config)

        return profile_config if profile_config else None
    except Exception:
        return None


def remove_section_from_file(file_path, section_header):
    """Remove a named section and its key-value lines from an INI-style file.

    Reads the file, skips the matching section header and all lines until the
    next section, then writes the result back.
    """
    if not file_path.exists():
        return

    try:
        with file_path.open("r") as f:
            lines = f.readlines()

        new_lines = []
        skip = False

        for line in lines:
            stripped = line.strip()
            if stripped == section_header:
                skip = True
                continue
            elif stripped.startswith("[") and skip:
                skip = False

            if not skip:
                new_lines.append(line)

        with file_path.open("w") as f:
            f.writelines(new_lines)
    except Exception as e:
        console.print(f"[red]Error removing section '{section_header}' from {file_path}: {e}[/red]")


def remove_profile_section(profile_name):
    """Remove a profile section from the AWS config file."""
    section = _get_profile_section(profile_name)
    remove_section_from_file(get_aws_config_path(), section)


def _flush_sso_session(current_section: str, session_config: dict, sessions: dict) -> None:
    """Save current_section/session_config into sessions if both are non-empty."""
    if current_section and session_config:
        sessions[current_section] = session_config


def get_existing_sso_sessions():
    """Get existing SSO sessions from config."""
    config_path = get_aws_config_path()
    if not config_path.exists():
        return {}

    sessions = {}
    current_section = None
    session_config = {}

    try:
        with config_path.open("r") as f:
            for line in f:
                line = line.strip()

                if line.startswith("[sso-session "):
                    _flush_sso_session(current_section, session_config, sessions)
                    current_section = line[13:-1].strip()
                    session_config = {}
                elif line.startswith("["):
                    _flush_sso_session(current_section, session_config, sessions)
                    current_section = None
                    session_config = {}
                elif current_section and "=" in line:
                    key, value = line.split("=", 1)
                    session_config[key.strip()] = value.strip()

        _flush_sso_session(current_section, session_config, sessions)
        return sessions
    except Exception:
        return {}
