import subprocess
import sys
from unittest.mock import MagicMock, call

import pytest

from cli_tool.sidecar.services.sso_service import run_sso_login_sync
from cli_tool.sidecar.state import EventHub


class TestRunSsoLoginSync:
    @pytest.fixture
    def hub(self):
        return EventHub()

    @pytest.fixture
    def mock_verify_credentials(self, mocker):
        return mocker.patch("cli_tool.sidecar.services.sso_service.verify_credentials")

    @pytest.fixture
    def mock_popen(self, mocker):
        mock_process = MagicMock()
        mock_process.stdout = MagicMock()
        # By default, mock wait to return immediately
        mock_process.wait.return_value = 0
        mock_process.returncode = 0
        
        # We need a way to mock iter(process.stdout.readline, '')
        # In python, iter(callable, sentinel) calls callable until it returns sentinel.
        # We can just mock stdout.readline with a side_effect
        
        return mocker.patch("subprocess.Popen", return_value=mock_process)

    def test_emits_oidc_url(self, hub, mock_popen, mock_verify_credentials):
        """Test that OIDC URL is correctly parsed and emitted."""
        mock_verify_credentials.return_value = True
        
        # Setup mock stdout to emit an OIDC URL
        mock_process = mock_popen.return_value
        lines = [
            "Attempting to automatically open the SSO authorization page in your default browser.\n",
            "If the browser does not open or you wish to use a different device to authorize this request, open the following URL:\n",
            "\n",
            "https://oidc.us-east-1.amazonaws.com/authorize?client_id=xxx&redirect_uri=xxx\n",
            ""
        ]
        mock_process.stdout.readline.side_effect = lines
        
        # We want to capture the events published
        published_events = []
        original_publish = hub.publish
        def mock_publish(event_name, payload):
            published_events.append((event_name, payload))
            original_publish(event_name, payload)
            
        hub.publish = mock_publish
        
        result = run_sso_login_sync(hub, "my-profile", "test")
        
        assert result is True
        
        # Check that we emitted started
        assert published_events[0] == ("sso.login.started", {"profile": "my-profile", "source": "test"})
        
        # Check that we emitted url_ready
        assert published_events[1] == ("sso.login.url_ready", {
            "profile": "my-profile",
            "source": "test",
            "url": "https://oidc.us-east-1.amazonaws.com/authorize?client_id=xxx&redirect_uri=xxx",
            "code": ""
        })
        
        # Check that we emitted completed
        assert published_events[2] == ("sso.login.completed", {"profile": "my-profile", "source": "test", "success": True})
        
        # Check Popen args
        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args
        assert args[0] == ["aws", "sso", "login", "--profile", "my-profile"]
        assert kwargs["text"] is True

    def test_emits_device_code_url(self, hub, mock_popen, mock_verify_credentials):
        """Test that Device SSO URL and code are correctly parsed and emitted."""
        mock_verify_credentials.return_value = True
        
        mock_process = mock_popen.return_value
        lines = [
            "Attempting to automatically open the SSO authorization page in your default browser.\n",
            "If the browser does not open or you wish to use a different device to authorize this request, open the following URL:\n",
            "\n",
            "https://device.sso.us-east-1.amazonaws.com/\n",
            "\n",
            "Then enter the code:\n",
            "\n",
            "ABCD-1234\n",
            ""
        ]
        mock_process.stdout.readline.side_effect = lines
        
        published_events = []
        hub.publish = lambda name, p: published_events.append((name, p))
        
        result = run_sso_login_sync(hub, "my-profile", "test")
        
        assert result is True
        
        url_ready_event = next(e for e in published_events if e[0] == "sso.login.url_ready")
        assert url_ready_event[1] == {
            "profile": "my-profile",
            "source": "test",
            "url": "https://device.sso.us-east-1.amazonaws.com/",
            "code": "ABCD-1234"
        }

    def test_fails_if_verify_credentials_fails(self, hub, mock_popen, mock_verify_credentials):
        mock_verify_credentials.return_value = False
        mock_popen.return_value.stdout.readline.side_effect = [""]
        
        published_events = []
        hub.publish = lambda name, p: published_events.append((name, p))
        
        result = run_sso_login_sync(hub, "my-profile", "test")
        
        assert result is False
        completed_event = next(e for e in published_events if e[0] == "sso.login.completed")
        assert completed_event[1]["success"] is False
        assert "Credential verification failed" in completed_event[1]["error"]

    def test_fails_if_subprocess_returns_nonzero(self, hub, mock_popen, mock_verify_credentials):
        mock_process = mock_popen.return_value
        mock_process.returncode = 1
        mock_process.stdout.readline.side_effect = [""]
        
        published_events = []
        hub.publish = lambda name, p: published_events.append((name, p))
        
        result = run_sso_login_sync(hub, "my-profile", "test")
        
        assert result is False
        mock_verify_credentials.assert_not_called()
        completed_event = next(e for e in published_events if e[0] == "sso.login.completed")
        assert completed_event[1]["success"] is False
        assert "exit 1" in completed_event[1]["error"]

    def test_handles_timeout(self, hub, mock_popen, mock_verify_credentials):
        mock_process = mock_popen.return_value
        mock_process.stdout.readline.side_effect = [""]
        mock_process.wait.side_effect = subprocess.TimeoutExpired(cmd="aws sso login", timeout=120)
        
        published_events = []
        hub.publish = lambda name, p: published_events.append((name, p))
        
        result = run_sso_login_sync(hub, "my-profile", "test")
        
        assert result is False
        mock_process.kill.assert_called_once()
        completed_event = next(e for e in published_events if e[0] == "sso.login.completed")
        assert completed_event[1]["success"] is False
        assert "timed out" in completed_event[1]["error"]

    def test_handles_unexpected_exceptions(self, hub, mock_popen, mock_verify_credentials):
        mock_popen.side_effect = FileNotFoundError("aws not found")
        
        published_events = []
        hub.publish = lambda name, p: published_events.append((name, p))
        
        result = run_sso_login_sync(hub, "my-profile", "test")
        
        assert result is False
        completed_event = next(e for e in published_events if e[0] == "sso.login.completed")
        assert completed_event[1]["success"] is False
        assert "aws not found" in completed_event[1]["error"]
