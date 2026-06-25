"""
Integration tests for CodeArtifact login command.
"""

from unittest.mock import MagicMock, call, patch

import pytest
from click.testing import CliRunner

from cli_tool.commands.codeartifact.commands.login import codeartifact_login

_TEST_DOMAINS = [
    {"domain": "test-domain", "repository": "test-repo", "namespace": "@test", "account_id": "", "profile": "", "region": "us-east-1"},
    {"domain": "test-domain-2", "repository": "test-repo-2", "namespace": "@test2", "account_id": "", "profile": "", "region": "us-east-1"},
]


@pytest.fixture(autouse=True)
def mock_config_values(mocker):
    """Mock configuration values for CodeArtifact."""
    mocker.patch("cli_tool.commands.codeartifact.commands.login._load_domain_configs", return_value=_TEST_DOMAINS)
    mocker.patch("cli_tool.commands.codeartifact.commands.login.check_aws_cli", return_value=True)
    mocker.patch("cli_tool.core.utils.aws.select_profile", return_value=None)


@pytest.fixture
def mock_subprocess(mocker):
    """Mock subprocess.run for AWS CLI commands."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    return mock_run


@pytest.mark.integration
def test_codeartifact_login_success(cli_runner, mock_subprocess):
    result = cli_runner.invoke(codeartifact_login, [], obj={})
    assert result.exit_code == 0
    assert "test-domain" in result.output
    assert "test-domain-2" in result.output
    assert "Successful: 2" in result.output


@pytest.mark.integration
def test_codeartifact_login_with_profile(cli_runner, mock_subprocess, mocker):
    mocker.patch("cli_tool.core.utils.aws.select_profile", return_value="test-profile")
    result = cli_runner.invoke(codeartifact_login, [], obj={"profile": "test-profile"})
    assert result.exit_code == 0
    assert "CLI profile: test-profile" in result.output


@pytest.mark.integration
def test_codeartifact_login_no_domains(cli_runner, mocker):
    mocker.patch("cli_tool.commands.codeartifact.commands.login._load_domain_configs", return_value=[])
    mocker.patch("cli_tool.core.utils.aws.select_profile", return_value=None)
    result = cli_runner.invoke(codeartifact_login, [], obj={})
    assert result.exit_code == 1
    assert "No CodeArtifact domains configured" in result.output


@pytest.mark.integration
def test_codeartifact_login_no_aws_cli(cli_runner, mocker):
    mocker.patch("cli_tool.commands.codeartifact.commands.login.check_aws_cli", return_value=False)
    mocker.patch("cli_tool.core.utils.aws.select_profile", return_value=None)
    result = cli_runner.invoke(codeartifact_login, [], obj={})
    assert result.exit_code == 1


@pytest.mark.integration
def test_codeartifact_login_authentication_failure(cli_runner, mock_config_values, mocker):
    import subprocess

    mock_run = mocker.patch("subprocess.run")
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd=["aws", "codeartifact", "login"], stderr="AccessDeniedException"
    )
    result = cli_runner.invoke(codeartifact_login, [], obj={})
    assert result.exit_code == 1
    assert "Failed: 2" in result.output


@pytest.mark.integration
def test_codeartifact_login_partial_failure(cli_runner, mock_config_values, mocker):
    import subprocess

    mock_run = mocker.patch("subprocess.run")

    def side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("cmd", [])
        if "test-domain-2" in str(cmd):
            raise subprocess.CalledProcessError(returncode=1, cmd=cmd, stderr="Domain not found")
        return MagicMock(returncode=0, stdout="", stderr="")

    mock_run.side_effect = side_effect
    result = cli_runner.invoke(codeartifact_login, [], obj={})
    assert result.exit_code == 1
    assert "Successful: 1" in result.output
    assert "Failed: 1" in result.output


@pytest.mark.integration
def test_codeartifact_login_timeout(cli_runner, mock_config_values, mocker):
    import subprocess

    mock_run = mocker.patch("subprocess.run")
    mock_run.side_effect = subprocess.TimeoutExpired(cmd=["aws", "codeartifact", "login"], timeout=30)
    result = cli_runner.invoke(codeartifact_login, [], obj={})
    assert result.exit_code == 1


@pytest.mark.integration
def test_codeartifact_login_token_expiration_note(cli_runner, mock_subprocess):
    result = cli_runner.invoke(codeartifact_login, [], obj={})
    assert result.exit_code == 0
    assert "Tokens expire in 12 hours" in result.output


@pytest.mark.integration
def test_codeartifact_login_lists_packages(cli_runner, mock_config_values, mocker):
    mock_run = mocker.patch("subprocess.run")

    def side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("cmd", [])
        if "list-packages" in str(cmd) and "list-package-versions" not in str(cmd):
            return MagicMock(returncode=0, stdout="test\tpackage1\ntest\tpackage2", stderr="")
        elif "list-package-versions" in str(cmd):
            return MagicMock(returncode=0, stdout="1.0.0", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    mock_run.side_effect = side_effect
    result = cli_runner.invoke(codeartifact_login, [], obj={})
    assert result.exit_code == 0
    assert "Available Packages" in result.output
    assert "@test/package1" in result.output


@pytest.mark.integration
def test_codeartifact_login_no_packages(cli_runner, mock_config_values, mocker):
    mock_run = mocker.patch("subprocess.run")

    def side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("cmd", [])
        if "list-packages" in str(cmd):
            return MagicMock(returncode=0, stdout="", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    mock_run.side_effect = side_effect
    result = cli_runner.invoke(codeartifact_login, [], obj={})
    assert result.exit_code == 0
    assert "No packages found" in result.output


@pytest.mark.integration
def test_codeartifact_login_package_version_retrieval(cli_runner, mock_config_values, mocker):
    mock_run = mocker.patch("subprocess.run")

    def side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("cmd", [])
        if "list-packages" in str(cmd) and "list-package-versions" not in str(cmd):
            return MagicMock(returncode=0, stdout="test\tmy-package", stderr="")
        elif "list-package-versions" in str(cmd):
            return MagicMock(returncode=0, stdout="2.5.1", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    mock_run.side_effect = side_effect
    result = cli_runner.invoke(codeartifact_login, [], obj={})
    assert result.exit_code == 0
    assert "@test/my-package@2.5.1" in result.output


@pytest.mark.integration
def test_codeartifact_login_multiple_domains(cli_runner, mock_subprocess):
    result = cli_runner.invoke(codeartifact_login, [], obj={})
    assert result.exit_code == 0
    assert "test-domain/test-repo (@test)" in result.output
    assert "test-domain-2/test-repo-2 (@test2)" in result.output
    assert "Successful: 2" in result.output


@pytest.mark.integration
def test_codeartifact_login_command_parameters(cli_runner, mock_subprocess):
    result = cli_runner.invoke(codeartifact_login, [], obj={})
    assert result.exit_code == 0
    login_calls = [call for call in mock_subprocess.call_args_list if "codeartifact" in str(call) and "login" in str(call)]
    first_call = login_calls[0]
    call_args = first_call[0][0]
    assert "aws" in call_args
    assert "codeartifact" in call_args
    assert "login" in call_args
    assert "--tool" in call_args
    assert "npm" in call_args
    assert "--domain" in call_args


@pytest.mark.integration
def test_codeartifact_login_pnpm_note(cli_runner, mock_subprocess):
    result = cli_runner.invoke(codeartifact_login, [], obj={})
    assert result.exit_code == 0
    assert "pnpm will automatically use the npm configuration" in result.output


@pytest.mark.integration
def test_codeartifact_login_troubleshooting_info(cli_runner, mock_config_values, mocker):
    import subprocess

    mock_run = mocker.patch("subprocess.run")
    mock_run.side_effect = subprocess.CalledProcessError(returncode=1, cmd=["aws", "codeartifact", "login"], stderr="AccessDeniedException")
    result = cli_runner.invoke(codeartifact_login, [], obj={})
    assert result.exit_code == 1
    assert "Troubleshooting:" in result.output


@pytest.mark.integration
def test_codeartifact_login_summary_display(cli_runner, mock_subprocess):
    result = cli_runner.invoke(codeartifact_login, [], obj={})
    assert result.exit_code == 0
    assert "Authentication Summary" in result.output
    assert "Successful: 2" in result.output


@pytest.mark.integration
def test_codeartifact_login_domains_count(cli_runner, mock_subprocess):
    result = cli_runner.invoke(codeartifact_login, [], obj={})
    assert result.exit_code == 0
    assert "Domains configured: 2" in result.output


# ---------------------------------------------------------------------------
# Unit tests for CodeArtifactAuthenticator methods
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_list_packages_returns_empty_on_exception(mocker):
    from cli_tool.commands.codeartifact.core.authenticator import CodeArtifactAuthenticator

    auth = CodeArtifactAuthenticator(region="us-east-1", domains=[])
    mocker.patch("subprocess.run", side_effect=Exception("unexpected error"))
    result = auth.list_packages("domain", "repo")
    assert result == []


@pytest.mark.unit
def test_list_packages_appends_profile_flag(mocker):
    from unittest.mock import MagicMock

    from cli_tool.commands.codeartifact.core.authenticator import CodeArtifactAuthenticator

    auth = CodeArtifactAuthenticator(region="us-east-1", domains=[])
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stdout="ns\tpkg1\n")
    result = auth.list_packages("domain", "repo", profile="my-profile")
    assert result == [("ns", "pkg1")]
    call_cmd = mock_run.call_args[0][0]
    assert "--profile" in call_cmd
    assert "my-profile" in call_cmd


@pytest.mark.unit
def test_get_package_version_returns_none_on_exception(mocker):
    from cli_tool.commands.codeartifact.core.authenticator import CodeArtifactAuthenticator

    auth = CodeArtifactAuthenticator(region="us-east-1", domains=[])
    mocker.patch("subprocess.run", side_effect=Exception("timeout"))
    result = auth.get_package_version("domain", "repo", "pkg", "@ns")
    assert result is None


@pytest.mark.unit
def test_get_package_version_returns_none_on_empty_stdout(mocker):
    from unittest.mock import MagicMock

    from cli_tool.commands.codeartifact.core.authenticator import CodeArtifactAuthenticator

    auth = CodeArtifactAuthenticator(region="us-east-1", domains=[])
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=""))
    result = auth.get_package_version("domain", "repo", "pkg", "@ns")
    assert result is None


@pytest.mark.unit
def test_list_packages_with_versions_handles_future_exception(mocker):
    from concurrent.futures import Future

    from cli_tool.commands.codeartifact.core.authenticator import CodeArtifactAuthenticator

    auth = CodeArtifactAuthenticator(region="us-east-1", domains=[])
    mocker.patch.object(auth, "list_packages", return_value=[("testns", "testpkg")])

    failing_future = Future()
    failing_future.set_exception(RuntimeError("version fetch failed"))

    mock_executor = mocker.MagicMock()
    mock_executor.__enter__ = mocker.MagicMock(return_value=mock_executor)
    mock_executor.__exit__ = mocker.MagicMock(return_value=False)
    mock_executor.submit = mocker.MagicMock(return_value=failing_future)

    mocker.patch(
        "cli_tool.commands.codeartifact.core.authenticator.ThreadPoolExecutor",
        return_value=mock_executor,
    )
    result = auth.list_packages_with_versions("domain", "repo", "@testns")
    assert "@testns/testpkg" in result
    assert result["@testns/testpkg"] is None


@pytest.mark.unit
def test_get_package_version_appends_profile_flag(mocker):
    from unittest.mock import MagicMock

    from cli_tool.commands.codeartifact.core.authenticator import CodeArtifactAuthenticator

    auth = CodeArtifactAuthenticator(region="us-east-1", domains=[])
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stdout="1.2.3\n")
    result = auth.get_package_version("domain", "repo", "pkg", "@ns", profile="my-profile")
    assert result == "1.2.3"
    call_cmd = mock_run.call_args[0][0]
    assert "--profile" in call_cmd
    assert "my-profile" in call_cmd


@pytest.mark.unit
def test_authenticate_domain_with_region_override(mocker):
    from unittest.mock import MagicMock

    from cli_tool.commands.codeartifact.core.authenticator import CodeArtifactAuthenticator

    auth = CodeArtifactAuthenticator(region="us-east-1", domains=[])
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    success, error = auth.authenticate_domain("dom", "repo", "@ns", region="us-west-2")
    assert success
    assert error is None
    call_cmd = mock_run.call_args[0][0]
    assert "--region" in call_cmd
    assert "us-west-2" in call_cmd
