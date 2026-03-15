"""Unit tests for cli_tool.commands.aws_login.core.config module."""

from pathlib import Path

import pytest

from cli_tool.commands.aws_login.core.config import (
    _classify_profile,
    _flush_sso_session,
    _get_profile_section,
    _merge_sso_session,
    _parse_profile_line,
    _read_config_profiles,
    _read_credentials_profiles,
    get_aws_config_path,
    get_aws_credentials_path,
    get_existing_sso_sessions,
    get_profile_config,
    list_aws_profiles,
    parse_sso_config,
    remove_section_from_file,
)

# ---------------------------------------------------------------------------
# get_aws_config_path / get_aws_credentials_path
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_aws_config_path_is_under_home(tmp_path, monkeypatch):
    """Config path is under ~/.aws/config."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = get_aws_config_path()

    assert result == tmp_path / ".aws" / "config"


@pytest.mark.unit
def test_get_aws_credentials_path_is_under_home(tmp_path, monkeypatch):
    """Credentials path is under ~/.aws/credentials."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = get_aws_credentials_path()

    assert result == tmp_path / ".aws" / "credentials"


# ---------------------------------------------------------------------------
# _get_profile_section
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_profile_section_for_default():
    """'default' maps to '[default]' header."""
    assert _get_profile_section("default") == "[default]"


@pytest.mark.unit
def test_get_profile_section_for_named_profile():
    """Named profile maps to '[profile <name>]' header."""
    assert _get_profile_section("dev") == "[profile dev]"


@pytest.mark.unit
def test_get_profile_section_for_profile_with_hyphens():
    """Profiles with hyphens map correctly."""
    assert _get_profile_section("my-dev-profile") == "[profile my-dev-profile]"


# ---------------------------------------------------------------------------
# _parse_profile_line
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_parse_profile_line_matches_profile_header():
    """Recognizes [profile <name>] header and sets in_profile=True."""
    current_profile, in_profile = _parse_profile_line("[profile dev]", "dev", None, False)
    assert current_profile == "dev"
    assert in_profile is True


@pytest.mark.unit
def test_parse_profile_line_mismatches_profile_header():
    """Non-matching [profile <name>] header sets in_profile=False."""
    current_profile, in_profile = _parse_profile_line("[profile prod]", "dev", None, False)
    assert current_profile == "prod"
    assert in_profile is False


@pytest.mark.unit
def test_parse_profile_line_matches_default():
    """Recognizes [default] header when looking for 'default'."""
    current_profile, in_profile = _parse_profile_line("[default]", "default", None, False)
    assert current_profile == "default"
    assert in_profile is True


@pytest.mark.unit
def test_parse_profile_line_other_section_stops_profile():
    """Any other section header sets in_profile=False."""
    current_profile, in_profile = _parse_profile_line("[sso-session foo]", "dev", "dev", True)
    assert in_profile is False


@pytest.mark.unit
def test_parse_profile_line_non_section_preserves_in_profile():
    """Non-section lines preserve the current in_profile state."""
    current_profile, in_profile = _parse_profile_line("region = us-east-1", "dev", "dev", True)
    assert in_profile is True


# ---------------------------------------------------------------------------
# _read_config_profiles
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_read_config_profiles_reads_sso_profiles(tmp_path):
    """Profiles with sso_ keys are marked has_sso=True."""
    config = tmp_path / "config"
    config.write_text(
        "[profile dev]\nsso_start_url = https://example.com/start\nsso_region = us-east-1\n\n" "[profile static-profile]\nregion = us-east-1\n"
    )

    result = _read_config_profiles(config)

    assert result["dev"] is True
    assert result["static-profile"] is False


@pytest.mark.unit
def test_read_config_profiles_handles_default_profile(tmp_path):
    """[default] section is read as 'default' profile."""
    config = tmp_path / "config"
    config.write_text("[default]\nregion = us-east-1\n")

    result = _read_config_profiles(config)

    assert "default" in result


@pytest.mark.unit
def test_read_config_profiles_ignores_sso_session_sections(tmp_path):
    """[sso-session <name>] sections are not counted as profiles."""
    config = tmp_path / "config"
    config.write_text("[profile dev]\nsso_session = my-sso\n\n[sso-session my-sso]\nsso_start_url = https://ex.com\n")

    result = _read_config_profiles(config)

    assert "dev" in result
    assert "my-sso" not in result


@pytest.mark.unit
def test_read_config_profiles_returns_empty_on_missing_file(tmp_path):
    """Returns empty dict when file doesn't exist."""
    result = _read_config_profiles(tmp_path / "nonexistent")
    assert result == {}


# ---------------------------------------------------------------------------
# _read_credentials_profiles
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_read_credentials_profiles_reads_profile_names(tmp_path):
    """Reads all section names from credentials file."""
    creds = tmp_path / "credentials"
    creds.write_text("[default]\naws_access_key_id = AKIA\n\n[dev]\naws_access_key_id = AKIA2\n")

    result = _read_credentials_profiles(creds)

    assert "default" in result
    assert "dev" in result


@pytest.mark.unit
def test_read_credentials_profiles_returns_empty_on_missing_file(tmp_path):
    """Returns empty set when file doesn't exist."""
    result = _read_credentials_profiles(tmp_path / "nonexistent")
    assert result == set()


# ---------------------------------------------------------------------------
# _classify_profile
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_classify_profile_sso_only():
    """Profile in config with SSO is classified as 'sso'."""
    result = _classify_profile("dev", {"dev": True}, set())
    assert result == "sso"


@pytest.mark.unit
def test_classify_profile_static_only():
    """Profile only in credentials is classified as 'static'."""
    result = _classify_profile("dev", {}, {"dev"})
    assert result == "static"


@pytest.mark.unit
def test_classify_profile_both():
    """Profile in both config and credentials is classified as 'both'."""
    result = _classify_profile("dev", {"dev": True}, {"dev"})
    assert result == "both"


@pytest.mark.unit
def test_classify_profile_config_only_no_sso():
    """Profile in config without SSO is classified as 'config'."""
    result = _classify_profile("dev", {"dev": False}, set())
    assert result == "config"


# ---------------------------------------------------------------------------
# list_aws_profiles
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_list_aws_profiles_empty_when_no_files(tmp_path, monkeypatch):
    """Returns empty list when neither config nor credentials exist."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = list_aws_profiles()

    assert result == []


@pytest.mark.unit
def test_list_aws_profiles_returns_sorted_list(tmp_path, monkeypatch):
    """Returns profiles sorted alphabetically."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    (aws_dir / "config").write_text("[profile zoo]\nregion = us-east-1\n\n[profile alpha]\nregion = us-east-1\n")

    result = list_aws_profiles()

    names = [p[0] for p in result]
    assert names == sorted(names)


@pytest.mark.unit
def test_list_aws_profiles_combines_config_and_credentials(tmp_path, monkeypatch):
    """Profiles from both config and credentials files are combined."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    (aws_dir / "config").write_text("[profile sso-dev]\nsso_start_url = https://ex.com\n")
    (aws_dir / "credentials").write_text("[static-dev]\naws_access_key_id = AKIA\n")

    result = list_aws_profiles()

    names = [p[0] for p in result]
    assert "sso-dev" in names
    assert "static-dev" in names


# ---------------------------------------------------------------------------
# parse_sso_config
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_parse_sso_config_returns_none_when_no_config(tmp_path, monkeypatch):
    """Returns None when AWS config file doesn't exist."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = parse_sso_config("dev")

    assert result is None


@pytest.mark.unit
def test_parse_sso_config_returns_profile_values(tmp_path, monkeypatch):
    """Returns parsed SSO config for a named profile."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    (aws_dir / "config").write_text(
        "[profile dev]\nsso_start_url = https://example.awsapps.com/start\n"
        "sso_region = us-east-1\nsso_account_id = 123456789012\nsso_role_name = Developer\n"
    )

    result = parse_sso_config("dev")

    assert result is not None
    assert result["sso_start_url"] == "https://example.awsapps.com/start"
    assert result["sso_region"] == "us-east-1"


@pytest.mark.unit
def test_parse_sso_config_returns_none_for_missing_profile(tmp_path, monkeypatch):
    """Returns None when profile doesn't exist in config."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    (aws_dir / "config").write_text("[profile dev]\nregion = us-east-1\n")

    result = parse_sso_config("nonexistent")

    assert result is None


@pytest.mark.unit
def test_parse_sso_config_merges_sso_session(tmp_path, monkeypatch):
    """When profile has sso_session, merges sso_start_url from session block."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    (aws_dir / "config").write_text(
        "[profile dev]\nsso_session = my-org\nsso_account_id = 123456789012\n\n"
        "[sso-session my-org]\nsso_start_url = https://myorg.awsapps.com/start\nsso_region = us-east-1\n"
    )

    result = parse_sso_config("dev")

    assert result is not None
    assert result["sso_start_url"] == "https://myorg.awsapps.com/start"
    assert result["sso_region"] == "us-east-1"


# ---------------------------------------------------------------------------
# get_profile_config
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_profile_config_returns_none_when_no_config(tmp_path, monkeypatch):
    """Returns None when config file doesn't exist."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = get_profile_config("dev")

    assert result is None


@pytest.mark.unit
def test_get_profile_config_returns_dict(tmp_path, monkeypatch):
    """Returns config dict for existing profile."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    (aws_dir / "config").write_text("[profile dev]\nregion = us-east-1\noutput = json\n")

    result = get_profile_config("dev")

    assert result is not None
    assert result["region"] == "us-east-1"
    assert result["output"] == "json"


@pytest.mark.unit
def test_get_profile_config_returns_none_for_missing_profile(tmp_path, monkeypatch):
    """Returns None when the profile does not exist in the config."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    (aws_dir / "config").write_text("[profile dev]\nregion = us-east-1\n")

    result = get_profile_config("nonexistent")

    assert result is None


@pytest.mark.unit
def test_get_profile_config_for_default_profile(tmp_path, monkeypatch):
    """Reads [default] section correctly."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    (aws_dir / "config").write_text("[default]\nregion = us-west-2\n")

    result = get_profile_config("default")

    assert result is not None
    assert result["region"] == "us-west-2"


# ---------------------------------------------------------------------------
# _merge_sso_session
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_merge_sso_session_adds_url_and_region(tmp_path):
    """Merges sso_start_url and sso_region from [sso-session] block."""
    config = tmp_path / "config"
    config.write_text("[sso-session my-org]\nsso_start_url = https://org.awsapps.com/start\nsso_region = us-east-1\n")
    target = {}

    _merge_sso_session(config, "my-org", target)

    assert target["sso_start_url"] == "https://org.awsapps.com/start"
    assert target["sso_region"] == "us-east-1"


@pytest.mark.unit
def test_merge_sso_session_noop_when_session_not_found(tmp_path):
    """Does nothing when session name doesn't exist in config."""
    config = tmp_path / "config"
    config.write_text("[sso-session other-org]\nsso_start_url = https://other.awsapps.com/start\n")
    target = {}

    _merge_sso_session(config, "my-org", target)

    assert target == {}


# ---------------------------------------------------------------------------
# get_existing_sso_sessions
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_existing_sso_sessions_returns_sessions(tmp_path, monkeypatch):
    """Returns dict of session names to configs."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    (aws_dir / "config").write_text("[sso-session my-org]\nsso_start_url = https://org.awsapps.com/start\nsso_region = us-east-1\n")

    result = get_existing_sso_sessions()

    assert "my-org" in result
    assert result["my-org"]["sso_start_url"] == "https://org.awsapps.com/start"


@pytest.mark.unit
def test_get_existing_sso_sessions_returns_empty_when_no_config(tmp_path, monkeypatch):
    """Returns empty dict when config file doesn't exist."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = get_existing_sso_sessions()

    assert result == {}


@pytest.mark.unit
def test_get_existing_sso_sessions_multiple_sessions(tmp_path, monkeypatch):
    """Returns all sessions from config."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    (aws_dir / "config").write_text(
        "[sso-session org-a]\nsso_start_url = https://a.com/start\n\n" "[sso-session org-b]\nsso_start_url = https://b.com/start\n"
    )

    result = get_existing_sso_sessions()

    assert "org-a" in result
    assert "org-b" in result


# ---------------------------------------------------------------------------
# _flush_sso_session
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_flush_sso_session_adds_to_dict():
    """Stores session config when both section and config are non-empty."""
    sessions = {}
    _flush_sso_session("my-org", {"sso_start_url": "https://x.com"}, sessions)
    assert "my-org" in sessions


@pytest.mark.unit
def test_flush_sso_session_skips_when_empty_section():
    """Skips when section name is None or empty."""
    sessions = {}
    _flush_sso_session(None, {"sso_start_url": "https://x.com"}, sessions)
    _flush_sso_session("", {"sso_start_url": "https://x.com"}, sessions)
    assert sessions == {}


@pytest.mark.unit
def test_flush_sso_session_skips_when_empty_config():
    """Skips when session_config is empty."""
    sessions = {}
    _flush_sso_session("my-org", {}, sessions)
    assert sessions == {}
