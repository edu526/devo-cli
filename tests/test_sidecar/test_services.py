from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, mock_open

import pytest

from cli_tool.sidecar.services.hosts_service import NeedsElevation

# ---------------------------------------------------------------------------
# preflight_service
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCheckPreflight:
    def _patch_base(self, mocker, *, aws_path="aws", smp_path="session-manager-plugin", socat_path="socat"):
        mocker.patch(
            "subprocess.run",
            return_value=MagicMock(
                stdout="aws-cli/2.15.0 Python/3.11.0\n",
                stderr="",
                returncode=0,
            ),
        )
        mocker.patch(
            "cli_tool.sidecar.services.preflight_service.list_aws_profiles",
            return_value=[("my-profile", "sso")],
        )
        config_path_mock = MagicMock()
        config_path_mock.exists.return_value = True
        mocker.patch(
            "cli_tool.sidecar.services.preflight_service.get_config_file",
            return_value=config_path_mock,
        )
        return config_path_mock

    def test_all_ok(self, mocker):
        self._patch_base(mocker)
        from cli_tool.sidecar.services.preflight_service import check_preflight

        result = check_preflight()
        assert result["aws_cli"]["ok"] is True
        assert result["session_manager_plugin"]["ok"] is True
        assert result["sso_configured"]["ok"] is True
        assert result["config_exists"]["ok"] is True

    def test_aws_cli_missing(self, mocker):
        import subprocess

        original_run = subprocess.run

        def selective_run(cmd, **kwargs):
            if cmd[0] == "aws":
                raise FileNotFoundError
            return MagicMock(stdout="", stderr="", returncode=0)

        mocker.patch("subprocess.run", side_effect=selective_run)
        mocker.patch(
            "cli_tool.sidecar.services.preflight_service.list_aws_profiles",
            return_value=[("my-profile", "sso")],
        )
        config_path_mock = MagicMock()
        config_path_mock.exists.return_value = True
        mocker.patch(
            "cli_tool.sidecar.services.preflight_service.get_config_file",
            return_value=config_path_mock,
        )

        from cli_tool.sidecar.services.preflight_service import check_preflight

        result = check_preflight()
        assert result["aws_cli"]["ok"] is False

    def test_session_manager_plugin_missing(self, mocker):
        import subprocess

        def selective_run(cmd, **kwargs):
            if cmd[0] == "session-manager-plugin":
                raise FileNotFoundError
            return MagicMock(stdout="aws-cli/2.15.0 Python/3.11.0\n", stderr="", returncode=0)

        mocker.patch("subprocess.run", side_effect=selective_run)
        mocker.patch(
            "cli_tool.sidecar.services.preflight_service.list_aws_profiles",
            return_value=[("my-profile", "sso")],
        )
        config_path_mock = MagicMock()
        config_path_mock.exists.return_value = True
        mocker.patch(
            "cli_tool.sidecar.services.preflight_service.get_config_file",
            return_value=config_path_mock,
        )

        from cli_tool.sidecar.services.preflight_service import check_preflight

        result = check_preflight()
        assert result["session_manager_plugin"]["ok"] is False


# ---------------------------------------------------------------------------
# hosts_service
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNeedsElevation:
    def test_command_attribute(self):
        exc = NeedsElevation("sudo cmd")
        assert exc.command == "sudo cmd"


@pytest.mark.unit
class TestListHosts:
    def test_returns_parsed_entries(self, mocker):
        mock_mgr = MagicMock()
        mock_mgr.get_managed_entries.return_value = [
            ("127.0.0.1", "mydb.local"),
            ("10.0.0.5", "other.local"),
        ]
        mocker.patch(
            "cli_tool.sidecar.services.hosts_service.HostsManager",
            return_value=mock_mgr,
        )

        from cli_tool.sidecar.services.hosts_service import list_hosts

        result = list_hosts()
        assert result == [
            {"ip": "127.0.0.1", "hostname": "mydb.local"},
            {"ip": "10.0.0.5", "hostname": "other.local"},
        ]


@pytest.mark.unit
class TestAddHost:
    def test_permission_error_raises_needs_elevation(self, mocker):
        mock_mgr = MagicMock()
        mock_mgr.add_entry.side_effect = PermissionError
        mocker.patch(
            "cli_tool.sidecar.services.hosts_service.HostsManager",
            return_value=mock_mgr,
        )

        from cli_tool.sidecar.services.hosts_service import add_host

        with pytest.raises(NeedsElevation):
            add_host("10.0.0.1", "mydb.local")


@pytest.mark.unit
class TestRemoveHost:
    def test_permission_error_raises_needs_elevation(self, mocker):
        mock_mgr = MagicMock()
        mock_mgr.remove_entry.side_effect = PermissionError
        mocker.patch(
            "cli_tool.sidecar.services.hosts_service.HostsManager",
            return_value=mock_mgr,
        )

        from cli_tool.sidecar.services.hosts_service import remove_host

        with pytest.raises(NeedsElevation):
            remove_host("mydb.local")


@pytest.mark.unit
class TestSetupHosts:
    def _patch_setup(self, mocker, succeeded, failed):
        mocker.patch(
            "cli_tool.sidecar.services.hosts_service.setup_databases",
            return_value=(succeeded, failed),
        )

    def test_returns_structured_results(self, mocker):
        self._patch_setup(
            mocker,
            [{"name": "db1", "host": "h", "ip": "127.0.0.2", "local_port": 15432, "port_reassigned": False}],
            [],
        )
        from cli_tool.sidecar.services.hosts_service import setup_hosts

        result = setup_hosts()
        assert result["succeeded"][0]["name"] == "db1"
        assert result["failed"] == []

    def test_elevation_failure_raises_needs_elevation(self, mocker):
        self._patch_setup(
            mocker,
            [],
            [{"name": "db1", "host": "h", "error": "denied", "needs_elevation": True}],
        )
        from cli_tool.sidecar.services.hosts_service import setup_hosts

        with pytest.raises(NeedsElevation):
            setup_hosts()

    def test_non_elevation_failure_does_not_raise(self, mocker):
        self._patch_setup(
            mocker,
            [{"name": "db1", "host": "h", "ip": "127.0.0.2", "local_port": 15432, "port_reassigned": False}],
            [{"name": "db2", "host": "h2", "error": "boom", "needs_elevation": False}],
        )
        from cli_tool.sidecar.services.hosts_service import setup_hosts

        result = setup_hosts()
        assert len(result["succeeded"]) == 1
        assert result["failed"][0]["name"] == "db2"


# ---------------------------------------------------------------------------
# profile_service
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetProfilesInfo:
    def _patch(self, mocker, profiles, expiration):
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.list_aws_profiles",
            return_value=profiles,
        )
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.get_profile_credentials_expiration",
            return_value=expiration,
        )

    def test_returns_list(self, mocker):
        future_exp = datetime.now(timezone.utc) + timedelta(hours=2)
        self._patch(mocker, [("dev", "sso")], future_exp)

        from cli_tool.sidecar.services.profile_service import get_profiles_info

        result = get_profiles_info()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "dev"

    def test_expired_profile_has_status_expired(self, mocker):
        past_exp = datetime.now(timezone.utc) - timedelta(hours=1)
        self._patch(mocker, [("old-profile", "sso")], past_exp)

        from cli_tool.sidecar.services.profile_service import get_profiles_info

        result = get_profiles_info()
        assert result[0]["status"] == "expired"

    def test_valid_profile_has_status_valid(self, mocker):
        future_exp = datetime.now(timezone.utc) + timedelta(hours=8)
        self._patch(mocker, [("fresh-profile", "both")], future_exp)

        from cli_tool.sidecar.services.profile_service import get_profiles_info

        result = get_profiles_info()
        assert result[0]["status"] == "valid"
