"""
Tests for CompletionInstaller.

Covers:
- is_already_configured (active line, commented-out line, absent, missing file)
- install (fresh install, idempotent, fish directory creation, write error)
- get_config_file / get_completion_line / get_instructions (unsupported shell)
- is_supported_shell
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from cli_tool.commands.autocomplete.core.installer import CompletionInstaller

SUPPORTED_SHELLS = ["bash", "zsh", "fish"]


# ---------------------------------------------------------------------------
# is_already_configured
# ---------------------------------------------------------------------------


def test_is_already_configured_returns_false_when_rc_missing(tmp_path):
    """No config file → not configured."""
    rc = tmp_path / ".zshrc"  # does not exist
    with patch.object(CompletionInstaller, "SHELL_CONFIGS", {"zsh": {"line": 'eval "$(_DEVO_COMPLETE=zsh_source devo)"', "file": rc}}):
        assert CompletionInstaller.is_already_configured("zsh") is False


def test_is_already_configured_returns_false_when_line_absent(tmp_path):
    """Config file exists but has no completion line → not configured."""
    rc = tmp_path / ".zshrc"
    rc.write_text("export PATH=$PATH:/usr/local/bin\n")
    with patch.object(CompletionInstaller, "SHELL_CONFIGS", {"zsh": {"line": 'eval "$(_DEVO_COMPLETE=zsh_source devo)"', "file": rc}}):
        assert CompletionInstaller.is_already_configured("zsh") is False


def test_is_already_configured_returns_true_when_line_active(tmp_path):
    """Active (uncommented) completion line → configured."""
    rc = tmp_path / ".zshrc"
    rc.write_text('export PATH=$PATH:/usr/local/bin\neval "$(_DEVO_COMPLETE=zsh_source devo)"\n')
    with patch.object(CompletionInstaller, "SHELL_CONFIGS", {"zsh": {"line": 'eval "$(_DEVO_COMPLETE=zsh_source devo)"', "file": rc}}):
        assert CompletionInstaller.is_already_configured("zsh") is True


def test_is_already_configured_returns_false_when_line_commented_out(tmp_path):
    """Commented-out completion line must NOT be treated as configured.

    This is the regression test for the bug where a commented line was
    mistakenly detected as an active completion setup, causing --install
    to silently skip installation.
    """
    rc = tmp_path / ".zshrc"
    rc.write_text('export PATH=$PATH:/usr/local/bin\n# eval "$(_DEVO_COMPLETE=zsh_source devo)"\n')
    with patch.object(CompletionInstaller, "SHELL_CONFIGS", {"zsh": {"line": 'eval "$(_DEVO_COMPLETE=zsh_source devo)"', "file": rc}}):
        assert CompletionInstaller.is_already_configured("zsh") is False


def test_is_already_configured_returns_false_for_unsupported_shell():
    """Unknown shell always returns False."""
    assert CompletionInstaller.is_already_configured("powershell") is False


@pytest.mark.parametrize("shell", SUPPORTED_SHELLS)
def test_is_already_configured_detects_active_line_for_all_shells(tmp_path, shell):
    """Active completion line is detected for every supported shell."""
    config = CompletionInstaller.SHELL_CONFIGS[shell]
    rc = tmp_path / config["file"].name
    rc.write_text(f"{config['line']}\n")
    with patch.object(CompletionInstaller, "SHELL_CONFIGS", {shell: {**config, "file": rc}}):
        assert CompletionInstaller.is_already_configured(shell) is True


@pytest.mark.parametrize("shell", SUPPORTED_SHELLS)
def test_is_already_configured_ignores_commented_line_for_all_shells(tmp_path, shell):
    """Commented completion line is ignored for every supported shell."""
    config = CompletionInstaller.SHELL_CONFIGS[shell]
    rc = tmp_path / config["file"].name
    rc.write_text(f"# {config['line']}\n")
    with patch.object(CompletionInstaller, "SHELL_CONFIGS", {shell: {**config, "file": rc}}):
        assert CompletionInstaller.is_already_configured(shell) is False


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


def test_install_writes_completion_line_to_rc_file(tmp_path):
    """Fresh install appends the completion line to the rc file."""
    rc = tmp_path / ".zshrc"
    rc.write_text("export PATH=$PATH:/usr/local/bin\n")
    config = {"line": 'eval "$(_DEVO_COMPLETE=zsh_source devo)"', "file": rc}
    with patch.object(CompletionInstaller, "SHELL_CONFIGS", {"zsh": config}):
        success, message = CompletionInstaller.install("zsh")

    assert success is True
    assert "zsh" in message.lower() or str(rc) in message
    content = rc.read_text()
    assert 'eval "$(_DEVO_COMPLETE=zsh_source devo)"' in content


def test_install_creates_rc_file_if_missing(tmp_path):
    """install() creates the rc file when it does not yet exist."""
    rc = tmp_path / ".zshrc"
    config = {"line": 'eval "$(_DEVO_COMPLETE=zsh_source devo)"', "file": rc}
    with patch.object(CompletionInstaller, "SHELL_CONFIGS", {"zsh": config}):
        success, _ = CompletionInstaller.install("zsh")

    assert success is True
    assert rc.exists()
    assert "_DEVO_COMPLETE" in rc.read_text()


def test_install_is_idempotent(tmp_path):
    """Calling install() twice does not duplicate the completion line."""
    rc = tmp_path / ".zshrc"
    rc.write_text("")
    config = {"line": 'eval "$(_DEVO_COMPLETE=zsh_source devo)"', "file": rc}
    with patch.object(CompletionInstaller, "SHELL_CONFIGS", {"zsh": config}):
        CompletionInstaller.install("zsh")
        success, message = CompletionInstaller.install("zsh")

    assert success is True
    assert rc.read_text().count("_DEVO_COMPLETE") == 1


def test_install_creates_parent_directory_for_fish(tmp_path):
    """install() creates the parent directory for fish config if needed."""
    fish_config = tmp_path / ".config" / "fish" / "config.fish"
    config = {"line": "_DEVO_COMPLETE=fish_source devo | source", "file": fish_config}
    with patch.object(CompletionInstaller, "SHELL_CONFIGS", {"fish": config}):
        success, _ = CompletionInstaller.install("fish")

    assert success is True
    assert fish_config.exists()
    assert "_DEVO_COMPLETE" in fish_config.read_text()


def test_install_returns_failure_for_unsupported_shell():
    """install() with an unknown shell returns (False, error message)."""
    success, message = CompletionInstaller.install("powershell")
    assert success is False
    assert "powershell" in message.lower() or "unsupported" in message.lower()


def test_install_returns_failure_on_write_error(tmp_path):
    """install() returns (False, message) when the file cannot be written."""
    rc = tmp_path / ".zshrc"
    rc.write_text("")
    rc.chmod(0o444)  # read-only
    config = {"line": 'eval "$(_DEVO_COMPLETE=zsh_source devo)"', "file": rc}
    with patch.object(CompletionInstaller, "SHELL_CONFIGS", {"zsh": config}):
        success, _ = CompletionInstaller.install("zsh")

    assert success is False
    rc.chmod(0o644)  # restore for cleanup


# ---------------------------------------------------------------------------
# Accessors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("shell", SUPPORTED_SHELLS)
def test_get_config_file_returns_path_for_supported_shells(shell):
    result = CompletionInstaller.get_config_file(shell)
    assert isinstance(result, Path)


def test_get_config_file_returns_none_for_unsupported_shell():
    assert CompletionInstaller.get_config_file("powershell") is None


@pytest.mark.parametrize("shell", SUPPORTED_SHELLS)
def test_get_completion_line_returns_string_for_supported_shells(shell):
    result = CompletionInstaller.get_completion_line(shell)
    assert isinstance(result, str)
    assert "_DEVO_COMPLETE" in result


def test_get_completion_line_returns_none_for_unsupported_shell():
    assert CompletionInstaller.get_completion_line("powershell") is None


@pytest.mark.parametrize("shell", SUPPORTED_SHELLS)
def test_get_instructions_returns_string_for_supported_shells(shell):
    result = CompletionInstaller.get_instructions(shell)
    assert isinstance(result, str)
    assert "_DEVO_COMPLETE" in result


def test_get_instructions_returns_none_for_unsupported_shell():
    assert CompletionInstaller.get_instructions("powershell") is None


# ---------------------------------------------------------------------------
# is_supported_shell
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("shell", SUPPORTED_SHELLS)
def test_is_supported_shell_true_for_known_shells(shell):
    assert CompletionInstaller.is_supported_shell(shell) is True


def test_is_supported_shell_false_for_unknown_shell():
    assert CompletionInstaller.is_supported_shell("powershell") is False
