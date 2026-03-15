"""Windows platform-specific tests.

Tests Windows-specific functionality including:
- PE binary verification
- ZIP extraction
- ZIP format handling
- PowerShell completion

Requirements: 5.1, 5.2, 5.4, 5.5, 10.5
"""

import subprocess
import zipfile
from unittest.mock import MagicMock

import pytest


@pytest.mark.platform
class TestWindowsBinaryFormat:
    """Test Windows-specific binary format and handling."""

    def test_windows_zip_verification(self, temp_config_dir):
        """Test ZIP file verification on Windows (PE header).

        Validates: Requirements 5.5
        """
        from cli_tool.commands.upgrade.core.downloader import verify_binary

        # Create a valid ZIP file with devo.exe
        zip_path = temp_config_dir / "devo-windows-amd64.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            # Add a mock devo.exe file
            zf.writestr("devo/devo.exe", b"MZ" + b"\x00" * 100)  # Mock PE header
            zf.writestr("devo/_internal/base_library.zip", b"PK\x03\x04")  # Mock internal file

        # Verify the ZIP file
        result = verify_binary(zip_path, is_archive=True, archive_type="zip")

        # Should pass verification
        assert result is True

    def test_windows_zip_verification_invalid(self, temp_config_dir):
        """Test ZIP verification fails for invalid ZIP.

        Validates: Requirements 5.5
        """
        from cli_tool.commands.upgrade.core.downloader import verify_binary

        # Create an invalid ZIP file (not actually a ZIP)
        invalid_zip = temp_config_dir / "invalid.zip"
        invalid_zip.write_text("This is not a ZIP file")

        # Verify should fail
        result = verify_binary(invalid_zip, is_archive=True, archive_type="zip")

        # Should fail verification
        assert result is False

    def test_windows_zip_verification_missing_exe(self, temp_config_dir):
        """Test ZIP verification fails when devo.exe is missing.

        Validates: Requirements 5.5
        """
        from cli_tool.commands.upgrade.core.downloader import verify_binary

        # Create a ZIP without devo.exe
        zip_path = temp_config_dir / "incomplete.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("devo/other_file.txt", b"some content")

        # Verify should fail
        result = verify_binary(zip_path, is_archive=True, archive_type="zip")

        # Should fail verification
        assert result is False


@pytest.mark.platform
class TestWindowsZipExtraction:
    """Test ZIP extraction on Windows."""

    def test_windows_zip_extraction_basic(self, temp_config_dir):
        """Test basic ZIP extraction on Windows.

        Validates: Requirements 5.5
        """
        # Create a test ZIP file
        zip_path = temp_config_dir / "test.zip"
        extract_path = temp_config_dir / "extracted"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("devo/devo.exe", b"MZ" + b"\x00" * 100)
            zf.writestr("devo/_internal/base_library.zip", b"PK\x03\x04")
            zf.writestr("devo/_internal/python312.dll", b"MZ" + b"\x00" * 50)

        # Extract the ZIP
        extract_path.mkdir()
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_path)

        # Verify extraction
        assert (extract_path / "devo" / "devo.exe").exists()
        assert (extract_path / "devo" / "_internal" / "base_library.zip").exists()
        assert (extract_path / "devo" / "_internal" / "python312.dll").exists()

    def test_windows_zip_extraction_with_installer(self, temp_config_dir, mocker):
        """Test ZIP extraction through installer module.

        Validates: Requirements 5.5
        """
        from cli_tool.commands.upgrade.core.installer import replace_binary

        # Create a test ZIP file
        zip_path = temp_config_dir / "devo-windows-amd64.zip"
        target_path = temp_config_dir / "devo"
        target_path.mkdir()

        # Create existing installation
        (target_path / "devo.exe").write_bytes(b"MZ" + b"\x00" * 50)

        # Create new version ZIP
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("devo/devo.exe", b"MZ" + b"\x00" * 100)
            zf.writestr("devo/_internal/base_library.zip", b"PK\x03\x04")

        # Mock platform.system to take the Windows path in installer.py
        mocker.patch("platform.system", return_value="Windows")

        # CREATE_NEW_CONSOLE is a Windows-only constant — patch it for Linux CI
        mocker.patch.object(subprocess, "CREATE_NEW_CONSOLE", 0x10, create=True)

        # Mock subprocess.Popen to avoid actually running PowerShell
        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value = MagicMock()

        # Mock os.getpid to return a test PID
        mocker.patch("os.getpid", return_value=12345)

        # Run replacement (should create PowerShell script)
        result = replace_binary(zip_path, target_path, archive_type="zip")

        # Should succeed (script created)
        assert result is True

        # Verify PowerShell script was created
        script_path = target_path.parent / "upgrade_devo.ps1"
        assert script_path.exists()

        # Verify script content
        script_content = script_path.read_text()
        assert "12345" in script_content  # PID
        assert "Wait-Process" in script_content
        assert "Remove-Item" in script_content
        assert "Move-Item" in script_content


@pytest.mark.platform
class TestWindowsShellCompletion:
    """Test Windows-specific shell completion (PowerShell)."""

    def test_powershell_completion_installation(self, cli_runner, temp_config_dir, mocker):
        """Test PowerShell completion installation on Windows.

        Validates: Requirements 5.2, 5.4, 10.5
        """
        from cli_tool.commands.autocomplete.commands.autocomplete import autocomplete

        # Mock PowerShell profile path
        ps_profile = temp_config_dir / "Microsoft.PowerShell_profile.ps1"
        ps_profile.parent.mkdir(parents=True, exist_ok=True)

        # Mock the installer methods directly
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_supported_shell", return_value=True)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_already_configured", return_value=False)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.get_config_file", return_value=ps_profile)
        mocker.patch(
            "cli_tool.commands.autocomplete.core.installer.CompletionInstaller.install",
            return_value=(True, f"Shell completion configured in {ps_profile}"),
        )

        # Mock SHELL environment variable (PowerShell on Windows)
        mocker.patch.dict("os.environ", {"SHELL": "powershell"})

        # Run installation
        result = cli_runner.invoke(autocomplete, ["--install", "--yes"])

        # Verify success
        assert result.exit_code == 0
        assert "configured" in result.output.lower() or "success" in result.output.lower() or "✅" in result.output

    def test_cmd_completion_not_supported(self, cli_runner):
        """Test that CMD completion shows appropriate message.

        Note: CMD doesn't support the same completion mechanism as PowerShell.

        Validates: Requirements 5.2, 10.5
        """
        from cli_tool.commands.autocomplete.commands.autocomplete import autocomplete

        # Try to install for CMD (not supported)
        result = cli_runner.invoke(autocomplete, ["--install", "cmd", "--yes"])

        # Should indicate CMD is not supported or provide alternative instructions
        assert result.exit_code != 0 or "not supported" in result.output.lower() or "unsupported" in result.output.lower()

    def test_powershell_completion_already_configured(self, cli_runner, temp_config_dir, mocker):
        """Test PowerShell completion when already configured.

        Validates: Requirements 5.2, 10.5
        """
        from cli_tool.commands.autocomplete.commands.autocomplete import autocomplete

        # Mock PowerShell profile path
        ps_profile = temp_config_dir / "Microsoft.PowerShell_profile.ps1"

        # Mock that completion is already configured
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_supported_shell", return_value=True)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_already_configured", return_value=True)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.get_config_file", return_value=ps_profile)

        # Mock SHELL environment variable
        mocker.patch.dict("os.environ", {"SHELL": "powershell"})

        # Run installation
        result = cli_runner.invoke(autocomplete, ["--install", "--yes"])

        # Should indicate already configured
        assert result.exit_code == 0
        assert "already" in result.output.lower()
