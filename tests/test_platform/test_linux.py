"""Linux platform-specific tests.

Tests Linux-specific functionality including:
- ELF binary verification
- Binary permissions (chmod)
- Single file binary format
- Fish shell completion

Requirements: 5.1, 5.2, 5.4, 5.5, 10.3
"""

import sys

import pytest


@pytest.mark.platform
@pytest.mark.skipif(sys.platform != "linux", reason="Linux only")
class TestLinuxBinaryFormat:
    """Test Linux-specific binary format and handling."""

    def test_linux_binary_format_is_single_file(self):
        """Test that Linux binary is a single file (not archive).

        Validates: Requirements 5.4, 5.5
        """
        from cli_tool.commands.upgrade.core.platform import get_binary_name

        # Get binary name for Linux
        binary_name = get_binary_name("linux", "amd64")

        # Verify single file format (no extension)
        assert not binary_name.endswith(".zip")
        assert not binary_name.endswith(".tar.gz")
        assert "linux" in binary_name.lower()
        assert "amd64" in binary_name.lower()

    def test_linux_binary_name_arm64(self):
        """Test Linux binary name for ARM64 architecture.

        Validates: Requirements 5.4, 5.5
        """
        from cli_tool.commands.upgrade.core.platform import get_binary_name

        # Get binary name for Linux ARM64
        binary_name = get_binary_name("linux", "arm64")

        # Verify format
        assert not binary_name.endswith(".zip")
        assert not binary_name.endswith(".tar.gz")
        assert "linux" in binary_name.lower()
        assert "arm64" in binary_name.lower()

    def test_linux_binary_verification(self, temp_config_dir):
        """Test binary file verification on Linux (ELF header).

        Validates: Requirements 5.5
        """
        from cli_tool.commands.upgrade.core.downloader import verify_binary

        # Create a valid ELF binary (mock) with sufficient size (>10MB)
        binary_path = temp_config_dir / "devo-linux-amd64"

        # Write ELF header (magic bytes) + padding to reach 10MB
        binary_content = b"\x7fELF" + b"\x00" * (10 * 1024 * 1024)
        binary_path.write_bytes(binary_content)

        # Verify the binary
        result = verify_binary(binary_path, is_archive=False)

        # Should pass verification
        assert result is True

    def test_linux_binary_verification_invalid(self, temp_config_dir):
        """Test binary verification fails for invalid binary.

        Validates: Requirements 5.5
        """
        from cli_tool.commands.upgrade.core.downloader import verify_binary

        # Create an invalid binary (not ELF)
        invalid_binary = temp_config_dir / "invalid"
        invalid_binary.write_text("This is not a binary file")

        # Verify should fail
        result = verify_binary(invalid_binary, is_archive=False)

        # Should fail verification
        assert result is False

    def test_linux_binary_permissions(self, temp_config_dir, mocker):
        """Test that binary has executable permissions after replacement.

        Validates: Requirements 5.5
        """
        from cli_tool.commands.upgrade.core.installer import replace_binary

        # Create test binary
        binary_path = temp_config_dir / "devo-linux-amd64"
        target_path = temp_config_dir / "devo"

        # Create existing installation
        target_path.write_bytes(b"\x7fELF" + b"\x00" * 50)

        # Create new version binary
        binary_path.write_bytes(b"\x7fELF" + b"\x00" * 100)

        # Mock platform.system
        mocker.patch("platform.system", return_value="Linux")

        # Run replacement
        result = replace_binary(binary_path, target_path, archive_type=None)

        # Should succeed
        assert result is True

        # Verify new binary is executable
        import os

        assert os.access(target_path, os.X_OK)


@pytest.mark.platform
@pytest.mark.skipif(sys.platform != "linux", reason="Linux only")
class TestLinuxShellCompletion:
    """Test Linux-specific shell completion (Fish)."""

    def test_fish_completion_installation(self, cli_runner, temp_config_dir, mocker):
        """Test fish completion installation on Linux.

        Validates: Requirements 5.2, 5.4, 10.3
        """
        from cli_tool.commands.autocomplete.commands.autocomplete import autocomplete

        # Mock environment to detect fish
        mocker.patch.dict("os.environ", {"SHELL": "/usr/bin/fish"})

        # Mock fish config file path
        fish_config = temp_config_dir / ".config" / "fish" / "config.fish"

        # Mock the installer methods
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_supported_shell", return_value=True)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_already_configured", return_value=False)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.get_config_file", return_value=fish_config)
        mocker.patch(
            "cli_tool.commands.autocomplete.core.installer.CompletionInstaller.get_completion_line",
            return_value="_DEVO_COMPLETE=fish_source devo | source",
        )
        mocker.patch(
            "cli_tool.commands.autocomplete.core.installer.CompletionInstaller.install",
            return_value=(True, f"Shell completion configured in {fish_config}"),
        )

        # Run installation
        result = cli_runner.invoke(autocomplete, ["--install", "--yes"])

        # Verify success
        assert result.exit_code == 0
        assert "configured" in result.output.lower() or "success" in result.output.lower()

    def test_fish_completion_already_configured(self, cli_runner, temp_config_dir, mocker):
        """Test fish completion when already configured.

        Validates: Requirements 5.2, 10.3
        """
        from cli_tool.commands.autocomplete.commands.autocomplete import autocomplete

        # Mock environment to detect fish
        mocker.patch.dict("os.environ", {"SHELL": "/usr/bin/fish"})

        # Mock fish config file path
        fish_config = temp_config_dir / ".config" / "fish" / "config.fish"

        # Mock that completion is already configured
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_supported_shell", return_value=True)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_already_configured", return_value=True)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.get_config_file", return_value=fish_config)

        # Run installation
        result = cli_runner.invoke(autocomplete, ["--install", "--yes"])

        # Should indicate already configured
        assert result.exit_code == 0
        assert "already" in result.output.lower()

    def test_fish_completion_line_format(self):
        """Test fish completion line format.

        Validates: Requirements 5.2, 10.3
        """
        from cli_tool.commands.autocomplete.core.installer import CompletionInstaller

        # Get fish completion line
        completion_line = CompletionInstaller.get_completion_line("fish")

        # Verify format
        assert completion_line is not None
        assert "_DEVO_COMPLETE=fish_source" in completion_line
        assert "devo" in completion_line
        assert "source" in completion_line
