"""Linux platform-specific tests.

Tests Linux-specific functionality including:
- Path handling with forward slashes
- Bash completion installation
- Zsh completion installation
- Fish completion installation
- Linux binary format (single file)
- Binary format detection for Linux

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 10.1, 10.2, 10.3, 10.4
"""

import sys
from pathlib import Path

import pytest


@pytest.mark.platform
@pytest.mark.skipif(sys.platform != "linux", reason="Linux only")
class TestLinuxPathHandling:
    """Test Linux path handling."""

    def test_linux_path_separators_with_pathlib(self):
        """Test that Linux path separators are handled correctly with pathlib.

        Validates: Requirements 5.1, 5.3
        """
        # Test Unix-style path using pathlib
        linux_path = Path("/home/developer/.devo/config.json")

        # Verify Path object handles it correctly
        assert isinstance(linux_path, Path)
        # On Linux, pathlib uses forward slashes
        assert linux_path.parts[0] == "/"
        assert linux_path.parts[1] == "home"

    def test_linux_config_path_handling(self, temp_config_dir):
        """Test that config paths work correctly on Linux.

        Validates: Requirements 5.1, 5.3
        """
        # Create a config file path in temp directory
        config_path = temp_config_dir / "config.json"

        # Write and read to verify path handling
        config_path.write_text('{"test": "value"}')
        content = config_path.read_text()

        assert content == '{"test": "value"}'
        assert config_path.exists()

    def test_linux_nested_path_creation(self, temp_config_dir):
        """Test creating nested directories on Linux.

        Validates: Requirements 5.1, 5.3
        """
        # Create nested path
        nested_path = temp_config_dir / "aws" / "sso" / "profiles" / "dev"
        nested_path.mkdir(parents=True, exist_ok=True)

        # Verify directory was created
        assert nested_path.exists()
        assert nested_path.is_dir()

    def test_linux_home_directory_expansion(self):
        """Test home directory expansion on Linux.

        Validates: Requirements 5.1, 5.3
        """
        # Test tilde expansion
        home_path = Path.home()
        expanded_path = Path("~/.devo/config.json").expanduser()

        # Verify expansion works
        assert expanded_path.is_absolute()
        assert str(expanded_path).startswith(str(home_path))
        assert ".devo" in str(expanded_path)


@pytest.mark.platform
@pytest.mark.skipif(sys.platform != "linux", reason="Linux only")
class TestLinuxShellCompletion:
    """Test Linux shell completion installation."""

    def test_bash_completion_installation(self, cli_runner, temp_config_dir, mocker):
        """Test bash completion installation on Linux.

        Validates: Requirements 5.2, 5.4, 10.1
        """
        from cli_tool.commands.autocomplete.commands.autocomplete import autocomplete

        # Mock environment to detect bash
        mocker.patch.dict("os.environ", {"SHELL": "/bin/bash"})

        # Mock bash config file path
        bash_rc = temp_config_dir / ".bashrc"

        # Mock the installer methods
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_supported_shell", return_value=True)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_already_configured", return_value=False)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.get_config_file", return_value=bash_rc)
        mocker.patch(
            "cli_tool.commands.autocomplete.core.installer.CompletionInstaller.get_completion_line",
            return_value='eval "$(_DEVO_COMPLETE=bash_source devo)"',
        )
        mocker.patch(
            "cli_tool.commands.autocomplete.core.installer.CompletionInstaller.install",
            return_value=(True, f"Shell completion configured in {bash_rc}"),
        )

        # Run installation
        result = cli_runner.invoke(autocomplete, ["--install", "--yes"])

        # Verify success
        assert result.exit_code == 0
        assert "configured" in result.output.lower() or "success" in result.output.lower()

    def test_zsh_completion_installation(self, cli_runner, temp_config_dir, mocker):
        """Test zsh completion installation on Linux.

        Validates: Requirements 5.2, 5.4, 10.2
        """
        from cli_tool.commands.autocomplete.commands.autocomplete import autocomplete

        # Mock environment to detect zsh
        mocker.patch.dict("os.environ", {"SHELL": "/bin/zsh"})

        # Mock zsh config file path
        zsh_rc = temp_config_dir / ".zshrc"

        # Mock the installer methods
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_supported_shell", return_value=True)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_already_configured", return_value=False)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.get_config_file", return_value=zsh_rc)
        mocker.patch(
            "cli_tool.commands.autocomplete.core.installer.CompletionInstaller.get_completion_line",
            return_value='eval "$(_DEVO_COMPLETE=zsh_source devo)"',
        )
        mocker.patch(
            "cli_tool.commands.autocomplete.core.installer.CompletionInstaller.install",
            return_value=(True, f"Shell completion configured in {zsh_rc}"),
        )

        # Run installation
        result = cli_runner.invoke(autocomplete, ["--install", "--yes"])

        # Verify success
        assert result.exit_code == 0
        assert "configured" in result.output.lower() or "success" in result.output.lower()

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

    def test_bash_completion_already_configured(self, cli_runner, temp_config_dir, mocker):
        """Test bash completion when already configured.

        Validates: Requirements 5.2, 10.1
        """
        from cli_tool.commands.autocomplete.commands.autocomplete import autocomplete

        # Mock environment to detect bash
        mocker.patch.dict("os.environ", {"SHELL": "/bin/bash"})

        # Mock bash config file path
        bash_rc = temp_config_dir / ".bashrc"

        # Mock that completion is already configured
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_supported_shell", return_value=True)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_already_configured", return_value=True)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.get_config_file", return_value=bash_rc)

        # Run installation
        result = cli_runner.invoke(autocomplete, ["--install", "--yes"])

        # Should indicate already configured
        assert result.exit_code == 0
        assert "already" in result.output.lower()

    def test_zsh_completion_already_configured(self, cli_runner, temp_config_dir, mocker):
        """Test zsh completion when already configured.

        Validates: Requirements 5.2, 10.2
        """
        from cli_tool.commands.autocomplete.commands.autocomplete import autocomplete

        # Mock environment to detect zsh
        mocker.patch.dict("os.environ", {"SHELL": "/bin/zsh"})

        # Mock zsh config file path
        zsh_rc = temp_config_dir / ".zshrc"

        # Mock that completion is already configured
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_supported_shell", return_value=True)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_already_configured", return_value=True)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.get_config_file", return_value=zsh_rc)

        # Run installation
        result = cli_runner.invoke(autocomplete, ["--install", "--yes"])

        # Should indicate already configured
        assert result.exit_code == 0
        assert "already" in result.output.lower()

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

    def test_bash_completion_line_format(self):
        """Test bash completion line format.

        Validates: Requirements 5.2, 10.1
        """
        from cli_tool.commands.autocomplete.core.installer import CompletionInstaller

        # Get bash completion line
        completion_line = CompletionInstaller.get_completion_line("bash")

        # Verify format
        assert completion_line is not None
        assert "_DEVO_COMPLETE=bash_source" in completion_line
        assert "devo" in completion_line
        assert "eval" in completion_line

    def test_zsh_completion_line_format(self):
        """Test zsh completion line format.

        Validates: Requirements 5.2, 10.2
        """
        from cli_tool.commands.autocomplete.core.installer import CompletionInstaller

        # Get zsh completion line
        completion_line = CompletionInstaller.get_completion_line("zsh")

        # Verify format
        assert completion_line is not None
        assert "_DEVO_COMPLETE=zsh_source" in completion_line
        assert "devo" in completion_line
        assert "eval" in completion_line

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


@pytest.mark.platform
@pytest.mark.skipif(sys.platform != "linux", reason="Linux only")
class TestLinuxBinaryFormat:
    """Test Linux binary format and handling."""

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
        """Test binary file verification on Linux.

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

    def test_linux_executable_path_detection(self, mocker):
        """Test executable path detection on Linux.

        Validates: Requirements 5.1, 5.4
        """
        from cli_tool.commands.upgrade.core.platform import get_executable_path

        # Mock sys.frozen to simulate PyInstaller bundle
        mocker.patch("sys.frozen", True, create=True)

        # Mock sys.executable to return Linux path
        mock_exe_path = Path("/usr/local/bin/devo")
        mocker.patch("sys.executable", str(mock_exe_path))

        # Mock platform.system to return Linux
        mocker.patch("platform.system", return_value="Linux")

        # Get executable path
        exe_path = get_executable_path()

        # Should return the executable itself (onefile mode)
        assert exe_path == mock_exe_path

    def test_linux_path_with_spaces(self, temp_config_dir):
        """Test handling paths with spaces on Linux.

        Validates: Requirements 5.1, 5.3
        """
        # Create path with spaces
        path_with_spaces = temp_config_dir / "My Documents" / "Devo CLI" / "config.json"
        path_with_spaces.parent.mkdir(parents=True, exist_ok=True)

        # Write and read
        path_with_spaces.write_text('{"test": "value"}')
        content = path_with_spaces.read_text()

        assert content == '{"test": "value"}'
        assert path_with_spaces.exists()


@pytest.mark.platform
@pytest.mark.skipif(sys.platform != "linux", reason="Linux only")
class TestLinuxBinaryReplacement:
    """Test binary replacement workflow on Linux."""

    def test_linux_direct_replacement(self, temp_config_dir, mocker):
        """Test that Linux can replace binary directly while running.

        Validates: Requirements 5.4, 5.5
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

        # Verify backup exists
        backup_path = target_path.parent / f"{target_path.name}.backup"
        assert backup_path.exists()

    def test_linux_backup_creation(self, temp_config_dir, mocker):
        """Test that backup is created before replacement.

        Validates: Requirements 5.5
        """
        from cli_tool.commands.upgrade.core.installer import replace_binary

        # Create test setup
        binary_path = temp_config_dir / "devo-linux-amd64"
        target_path = temp_config_dir / "devo"

        # Create existing installation
        old_content = b"\x7fELF" + b"\x00" * 50
        target_path.write_bytes(old_content)

        # Create new version binary
        binary_path.write_bytes(b"\x7fELF" + b"\x00" * 100)

        # Mock platform.system
        mocker.patch("platform.system", return_value="Linux")

        # Run replacement
        result = replace_binary(binary_path, target_path, archive_type=None)

        # Should succeed
        assert result is True

        # Verify backup contains old content
        backup_path = target_path.parent / f"{target_path.name}.backup"
        assert backup_path.exists()
        assert backup_path.read_bytes() == old_content

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
class TestLinuxPlatformDetection:
    """Test platform detection on Linux."""

    def test_detect_linux_platform(self, mocker):
        """Test platform detection returns Linux.

        Validates: Requirements 5.1, 5.4
        """
        from cli_tool.commands.upgrade.core.platform import detect_platform

        # Mock platform.system and platform.machine
        mocker.patch("platform.system", return_value="Linux")
        mocker.patch("platform.machine", return_value="x86_64")

        # Detect platform
        result = detect_platform()

        # Should return linux, amd64
        assert result == ("linux", "amd64")

    def test_detect_linux_arm64(self, mocker):
        """Test platform detection for Linux ARM64.

        Validates: Requirements 5.1, 5.4
        """
        from cli_tool.commands.upgrade.core.platform import detect_platform

        # Mock platform.system and platform.machine
        mocker.patch("platform.system", return_value="Linux")
        mocker.patch("platform.machine", return_value="arm64")

        # Detect platform
        result = detect_platform()

        # Should return linux, arm64
        assert result == ("linux", "arm64")

    def test_detect_linux_aarch64_alias(self, mocker):
        """Test platform detection for Linux with aarch64 machine type.

        Validates: Requirements 5.1, 5.4
        """
        from cli_tool.commands.upgrade.core.platform import detect_platform

        # Mock platform.system and platform.machine (aarch64 is alias for arm64)
        mocker.patch("platform.system", return_value="Linux")
        mocker.patch("platform.machine", return_value="aarch64")

        # Detect platform
        result = detect_platform()

        # Should return linux, arm64
        assert result == ("linux", "arm64")
