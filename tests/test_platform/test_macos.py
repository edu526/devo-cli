"""macOS platform-specific tests.

Tests macOS-specific functionality including:
- Path handling with forward slashes
- Zsh completion installation
- Bash completion installation
- macOS binary format (tarball with onedir)
- Tarball extraction on macOS

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 10.2, 10.3
"""

import sys
import tarfile
from pathlib import Path

import pytest


@pytest.mark.platform
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
class TestMacOSPathHandling:
    """Test macOS path handling."""

    def test_macos_path_separators_with_pathlib(self):
        """Test that macOS path separators are handled correctly with pathlib.

        Validates: Requirements 5.1, 5.3
        """
        # Test Unix-style path using pathlib
        macos_path = Path("/Users/Developer/.devo/config.json")

        # Verify Path object handles it correctly
        assert isinstance(macos_path, Path)
        # On macOS, pathlib uses forward slashes
        assert macos_path.parts[0] == "/"
        assert macos_path.parts[1] == "Users"

    def test_macos_config_path_handling(self, temp_config_dir):
        """Test that config paths work correctly on macOS.

        Validates: Requirements 5.1, 5.3
        """
        # Create a config file path in temp directory
        config_path = temp_config_dir / "config.json"

        # Write and read to verify path handling
        config_path.write_text('{"test": "value"}')
        content = config_path.read_text()

        assert content == '{"test": "value"}'
        assert config_path.exists()

    def test_macos_nested_path_creation(self, temp_config_dir):
        """Test creating nested directories on macOS.

        Validates: Requirements 5.1, 5.3
        """
        # Create nested path
        nested_path = temp_config_dir / "aws" / "sso" / "profiles" / "dev"
        nested_path.mkdir(parents=True, exist_ok=True)

        # Verify directory was created
        assert nested_path.exists()
        assert nested_path.is_dir()

    def test_macos_home_directory_expansion(self):
        """Test home directory expansion on macOS.

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
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
class TestMacOSShellCompletion:
    """Test macOS shell completion installation."""

    def test_zsh_completion_installation(self, cli_runner, temp_config_dir, mocker):
        """Test zsh completion installation on macOS.

        Validates: Requirements 5.2, 5.4, 10.2
        """
        from cli_tool.commands.autocomplete.commands.autocomplete import autocomplete

        # Mock zsh config file path
        zsh_rc = temp_config_dir / ".zshrc"

        # Mock the installer methods directly
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_supported_shell", return_value=True)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_already_configured", return_value=False)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.get_config_file", return_value=zsh_rc)
        mocker.patch(
            "cli_tool.commands.autocomplete.core.installer.CompletionInstaller.install",
            return_value=(True, f"Shell completion configured in {zsh_rc}"),
        )

        # Mock SHELL environment variable
        mocker.patch.dict("os.environ", {"SHELL": "/bin/zsh"})

        # Run installation
        result = cli_runner.invoke(autocomplete, ["--install", "--yes"])

        # Verify success
        assert result.exit_code == 0
        assert "configured" in result.output.lower() or "success" in result.output.lower() or "✅" in result.output

    def test_bash_completion_installation(self, cli_runner, temp_config_dir, mocker):
        """Test bash completion installation on macOS.

        Validates: Requirements 5.2, 5.4, 10.3
        """
        from cli_tool.commands.autocomplete.commands.autocomplete import autocomplete

        # Mock bash config file path
        bash_rc = temp_config_dir / ".bashrc"

        # Mock the installer methods directly
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_supported_shell", return_value=True)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_already_configured", return_value=False)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.get_config_file", return_value=bash_rc)
        mocker.patch(
            "cli_tool.commands.autocomplete.core.installer.CompletionInstaller.install",
            return_value=(True, f"Shell completion configured in {bash_rc}"),
        )

        # Mock SHELL environment variable
        mocker.patch.dict("os.environ", {"SHELL": "/bin/bash"})

        # Run installation
        result = cli_runner.invoke(autocomplete, ["--install", "--yes"])

        # Verify success
        assert result.exit_code == 0
        assert "configured" in result.output.lower() or "success" in result.output.lower() or "✅" in result.output

    def test_zsh_completion_already_configured(self, cli_runner, temp_config_dir, mocker):
        """Test zsh completion when already configured.

        Validates: Requirements 5.2, 10.2
        """
        from cli_tool.commands.autocomplete.commands.autocomplete import autocomplete

        # Mock zsh config file path
        zsh_rc = temp_config_dir / ".zshrc"

        # Mock that completion is already configured
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_supported_shell", return_value=True)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_already_configured", return_value=True)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.get_config_file", return_value=zsh_rc)

        # Mock SHELL environment variable
        mocker.patch.dict("os.environ", {"SHELL": "/bin/zsh"})

        # Run installation
        result = cli_runner.invoke(autocomplete, ["--install", "--yes"])

        # Should indicate already configured
        assert result.exit_code == 0
        assert "already" in result.output.lower()

    def test_bash_completion_already_configured(self, cli_runner, temp_config_dir, mocker):
        """Test bash completion when already configured.

        Validates: Requirements 5.2, 10.3
        """
        from cli_tool.commands.autocomplete.commands.autocomplete import autocomplete

        # Mock bash config file path
        bash_rc = temp_config_dir / ".bashrc"

        # Mock that completion is already configured
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_supported_shell", return_value=True)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.is_already_configured", return_value=True)
        mocker.patch("cli_tool.commands.autocomplete.core.installer.CompletionInstaller.get_config_file", return_value=bash_rc)

        # Mock SHELL environment variable
        mocker.patch.dict("os.environ", {"SHELL": "/bin/bash"})

        # Run installation
        result = cli_runner.invoke(autocomplete, ["--install", "--yes"])

        # Should indicate already configured
        assert result.exit_code == 0
        assert "already" in result.output.lower()

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

    def test_bash_completion_line_format(self):
        """Test bash completion line format.

        Validates: Requirements 5.2, 10.3
        """
        from cli_tool.commands.autocomplete.core.installer import CompletionInstaller

        # Get bash completion line
        completion_line = CompletionInstaller.get_completion_line("bash")

        # Verify format
        assert completion_line is not None
        assert "_DEVO_COMPLETE=bash_source" in completion_line
        assert "devo" in completion_line
        assert "eval" in completion_line


@pytest.mark.platform
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
class TestMacOSBinaryFormat:
    """Test macOS binary format and handling."""

    def test_macos_binary_format_is_tarball(self):
        """Test that macOS binary is in tarball format.

        Validates: Requirements 5.4, 5.5
        """
        from cli_tool.commands.upgrade.core.platform import get_binary_name

        # Get binary name for macOS
        binary_name = get_binary_name("darwin", "amd64")

        # Verify tarball extension
        assert binary_name.endswith(".tar.gz")
        assert "darwin" in binary_name.lower()
        assert "amd64" in binary_name.lower()

    def test_macos_binary_name_arm64(self):
        """Test macOS binary name for ARM64 (Apple Silicon) architecture.

        Validates: Requirements 5.4, 5.5
        """
        from cli_tool.commands.upgrade.core.platform import get_binary_name

        # Get binary name for macOS ARM64
        binary_name = get_binary_name("darwin", "arm64")

        # Verify format
        assert binary_name.endswith(".tar.gz")
        assert "darwin" in binary_name.lower()
        assert "arm64" in binary_name.lower()

    def test_macos_tarball_verification(self, temp_config_dir):
        """Test tarball verification on macOS.

        Validates: Requirements 5.5
        """
        from cli_tool.commands.upgrade.core.downloader import verify_binary

        # Create a valid tarball with devo executable
        tarball_path = temp_config_dir / "devo-darwin-amd64.tar.gz"

        with tarfile.open(tarball_path, "w:gz") as tf:
            # Add a mock devo executable (Mach-O header)
            import io

            devo_content = b"\xcf\xfa\xed\xfe" + b"\x00" * 100  # Mock Mach-O header
            devo_info = tarfile.TarInfo(name="devo/devo")
            devo_info.size = len(devo_content)
            tf.addfile(devo_info, io.BytesIO(devo_content))

            # Add internal files
            lib_content = b"library content"
            lib_info = tarfile.TarInfo(name="devo/_internal/base_library.zip")
            lib_info.size = len(lib_content)
            tf.addfile(lib_info, io.BytesIO(lib_content))

        # Verify the tarball
        result = verify_binary(tarball_path, is_archive=True, archive_type="tar.gz")

        # Should pass verification
        assert result is True

    def test_macos_tarball_verification_invalid(self, temp_config_dir):
        """Test tarball verification fails for invalid tarball.

        Validates: Requirements 5.5
        """
        from cli_tool.commands.upgrade.core.downloader import verify_binary

        # Create an invalid tarball (not actually a tarball)
        invalid_tarball = temp_config_dir / "invalid.tar.gz"
        invalid_tarball.write_text("This is not a tarball")

        # Verify should fail
        result = verify_binary(invalid_tarball, is_archive=True, archive_type="tar.gz")

        # Should fail verification
        assert result is False

    def test_macos_tarball_verification_missing_executable(self, temp_config_dir):
        """Test tarball verification fails when devo executable is missing.

        Validates: Requirements 5.5
        """
        from cli_tool.commands.upgrade.core.downloader import verify_binary

        # Create a tarball without devo executable
        tarball_path = temp_config_dir / "incomplete.tar.gz"

        with tarfile.open(tarball_path, "w:gz") as tf:
            import io

            # Add only internal files, no devo executable
            content = b"some content"
            info = tarfile.TarInfo(name="devo/other_file.txt")
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))

        # Verify should fail
        result = verify_binary(tarball_path, is_archive=True, archive_type="tar.gz")

        # Should fail verification
        assert result is False


@pytest.mark.platform
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
class TestMacOSTarballExtraction:
    """Test tarball extraction on macOS."""

    def test_macos_tarball_extraction_basic(self, temp_config_dir):
        """Test basic tarball extraction on macOS.

        Validates: Requirements 5.5
        """
        # Create a test tarball
        tarball_path = temp_config_dir / "test.tar.gz"
        extract_path = temp_config_dir / "extracted"

        with tarfile.open(tarball_path, "w:gz") as tf:
            import io

            # Add devo executable
            devo_content = b"\xcf\xfa\xed\xfe" + b"\x00" * 100
            devo_info = tarfile.TarInfo(name="devo/devo")
            devo_info.size = len(devo_content)
            devo_info.mode = 0o755  # Executable permissions
            tf.addfile(devo_info, io.BytesIO(devo_content))

            # Add internal files
            lib_content = b"library content"
            lib_info = tarfile.TarInfo(name="devo/_internal/base_library.zip")
            lib_info.size = len(lib_content)
            tf.addfile(lib_info, io.BytesIO(lib_content))

            # Add Python library
            py_content = b"python library"
            py_info = tarfile.TarInfo(name="devo/_internal/libpython3.12.dylib")
            py_info.size = len(py_content)
            tf.addfile(py_info, io.BytesIO(py_content))

        # Extract the tarball
        extract_path.mkdir()
        with tarfile.open(tarball_path, "r:gz") as tf:
            tf.extractall(extract_path)

        # Verify extraction
        assert (extract_path / "devo" / "devo").exists()
        assert (extract_path / "devo" / "_internal" / "base_library.zip").exists()
        assert (extract_path / "devo" / "_internal" / "libpython3.12.dylib").exists()

    def test_macos_tarball_extraction_with_installer(self, temp_config_dir, mocker):
        """Test tarball extraction through installer module.

        Validates: Requirements 5.5
        """
        from cli_tool.commands.upgrade.core.installer import replace_binary

        # Create a test tarball
        tarball_path = temp_config_dir / "devo-darwin-amd64.tar.gz"
        target_path = temp_config_dir / "devo"
        target_path.mkdir()

        # Create existing installation
        (target_path / "devo").write_bytes(b"\xcf\xfa\xed\xfe" + b"\x00" * 50)

        # Create new version tarball
        with tarfile.open(tarball_path, "w:gz") as tf:
            import io

            # Add larger executable (newer version)
            devo_content = b"\xcf\xfa\xed\xfe" + b"\x00" * 100
            devo_info = tarfile.TarInfo(name="devo/devo")
            devo_info.size = len(devo_content)
            devo_info.mode = 0o755
            tf.addfile(devo_info, io.BytesIO(devo_content))

            # Add internal files
            lib_content = b"library content"
            lib_info = tarfile.TarInfo(name="devo/_internal/base_library.zip")
            lib_info.size = len(lib_content)
            tf.addfile(lib_info, io.BytesIO(lib_content))

        # Mock platform.system to return Darwin
        mocker.patch("platform.system", return_value="Darwin")

        # Run replacement
        result = replace_binary(tarball_path, target_path, archive_type="tar.gz")

        # Should succeed
        assert result is True

        # Verify backup was created
        backup_path = target_path.parent / f"{target_path.name}.backup"
        assert backup_path.exists()

        # Verify new installation exists
        assert target_path.exists()
        assert (target_path / "devo").exists()

    def test_macos_tarball_extraction_preserves_permissions(self, temp_config_dir):
        """Test that tarball extraction preserves executable permissions.

        Validates: Requirements 5.5
        """
        # Create a test tarball with specific permissions
        tarball_path = temp_config_dir / "test.tar.gz"
        extract_path = temp_config_dir / "extracted"

        with tarfile.open(tarball_path, "w:gz") as tf:
            import io

            # Add executable with specific permissions
            content = b"\xcf\xfa\xed\xfe" + b"\x00" * 100
            info = tarfile.TarInfo(name="devo/devo")
            info.size = len(content)
            info.mode = 0o755  # rwxr-xr-x
            tf.addfile(info, io.BytesIO(content))

        # Extract
        extract_path.mkdir()
        with tarfile.open(tarball_path, "r:gz") as tf:
            tf.extractall(extract_path)

        # Verify permissions
        exe_path = extract_path / "devo" / "devo"
        assert exe_path.exists()
        # Check that file is executable
        import os

        assert os.access(exe_path, os.X_OK)

    def test_macos_executable_path_detection(self, mocker):
        """Test executable path detection on macOS.

        Validates: Requirements 5.1, 5.4
        """
        from cli_tool.commands.upgrade.core.platform import get_executable_path

        # Mock sys.frozen to simulate PyInstaller bundle
        mocker.patch("sys.frozen", True, create=True)

        # Mock sys.executable to return macOS path
        mock_exe_path = Path("/Applications/Devo.app/Contents/MacOS/devo/devo")
        mocker.patch("sys.executable", str(mock_exe_path))

        # Mock platform.system to return Darwin
        mocker.patch("platform.system", return_value="Darwin")

        # Get executable path
        exe_path = get_executable_path()

        # Should return parent directory (onedir mode)
        assert exe_path == mock_exe_path.parent

    def test_macos_path_with_spaces(self, temp_config_dir):
        """Test handling paths with spaces on macOS.

        Validates: Requirements 5.1, 5.3
        """
        # Create path with spaces
        path_with_spaces = temp_config_dir / "Library" / "Application Support" / "Devo CLI" / "config.json"
        path_with_spaces.parent.mkdir(parents=True, exist_ok=True)

        # Write and read
        path_with_spaces.write_text('{"test": "value"}')
        content = path_with_spaces.read_text()

        assert content == '{"test": "value"}'
        assert path_with_spaces.exists()


@pytest.mark.platform
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
class TestMacOSPlatformDetection:
    """Test platform detection on macOS."""

    def test_detect_macos_platform(self, mocker):
        """Test platform detection returns Darwin.

        Validates: Requirements 5.1, 5.4
        """
        from cli_tool.commands.upgrade.core.platform import detect_platform

        # Mock platform.system and platform.machine
        mocker.patch("platform.system", return_value="Darwin")
        mocker.patch("platform.machine", return_value="x86_64")

        # Detect platform
        result = detect_platform()

        # Should return darwin, amd64
        assert result == ("darwin", "amd64")

    def test_detect_macos_arm64(self, mocker):
        """Test platform detection for macOS ARM64 (Apple Silicon).

        Validates: Requirements 5.1, 5.4
        """
        from cli_tool.commands.upgrade.core.platform import detect_platform

        # Mock platform.system and platform.machine
        mocker.patch("platform.system", return_value="Darwin")
        mocker.patch("platform.machine", return_value="arm64")

        # Detect platform
        result = detect_platform()

        # Should return darwin, arm64
        assert result == ("darwin", "arm64")

    def test_detect_macos_aarch64_alias(self, mocker):
        """Test platform detection for macOS with aarch64 machine type.

        Validates: Requirements 5.1, 5.4
        """
        from cli_tool.commands.upgrade.core.platform import detect_platform

        # Mock platform.system and platform.machine (aarch64 is alias for arm64)
        mocker.patch("platform.system", return_value="Darwin")
        mocker.patch("platform.machine", return_value="aarch64")

        # Detect platform
        result = detect_platform()

        # Should return darwin, arm64
        assert result == ("darwin", "arm64")


@pytest.mark.platform
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
class TestMacOSBinaryReplacement:
    """Test binary replacement workflow on macOS."""

    def test_macos_direct_replacement(self, temp_config_dir, mocker):
        """Test that macOS can replace binary directly while running.

        Validates: Requirements 5.4, 5.5
        """
        from cli_tool.commands.upgrade.core.installer import replace_binary

        # Create test tarball
        tarball_path = temp_config_dir / "devo-darwin-amd64.tar.gz"
        target_path = temp_config_dir / "devo"
        target_path.mkdir()

        # Create existing installation
        (target_path / "devo").write_bytes(b"\xcf\xfa\xed\xfe" + b"\x00" * 50)

        # Create new version tarball
        with tarfile.open(tarball_path, "w:gz") as tf:
            import io

            devo_content = b"\xcf\xfa\xed\xfe" + b"\x00" * 100
            devo_info = tarfile.TarInfo(name="devo/devo")
            devo_info.size = len(devo_content)
            devo_info.mode = 0o755
            tf.addfile(devo_info, io.BytesIO(devo_content))

        # Mock platform.system
        mocker.patch("platform.system", return_value="Darwin")

        # Run replacement
        result = replace_binary(tarball_path, target_path, archive_type="tar.gz")

        # Should succeed
        assert result is True

        # Verify backup exists
        backup_path = target_path.parent / f"{target_path.name}.backup"
        assert backup_path.exists()

    def test_macos_backup_creation(self, temp_config_dir, mocker):
        """Test that backup is created before replacement.

        Validates: Requirements 5.5
        """
        from cli_tool.commands.upgrade.core.installer import replace_binary

        # Create test setup
        tarball_path = temp_config_dir / "devo-darwin-amd64.tar.gz"
        target_path = temp_config_dir / "devo"
        target_path.mkdir()

        # Create existing installation with multiple files
        (target_path / "devo").write_bytes(b"\xcf\xfa\xed\xfe" + b"\x00" * 50)
        internal_dir = target_path / "_internal"
        internal_dir.mkdir()
        (internal_dir / "base_library.zip").write_bytes(b"old library")

        # Create new version tarball
        with tarfile.open(tarball_path, "w:gz") as tf:
            import io

            devo_content = b"\xcf\xfa\xed\xfe" + b"\x00" * 100
            devo_info = tarfile.TarInfo(name="devo/devo")
            devo_info.size = len(devo_content)
            devo_info.mode = 0o755
            tf.addfile(devo_info, io.BytesIO(devo_content))

        # Mock platform.system
        mocker.patch("platform.system", return_value="Darwin")

        # Run replacement
        result = replace_binary(tarball_path, target_path, archive_type="tar.gz")

        # Should succeed
        assert result is True

        # Verify backup contains old files
        backup_path = target_path.parent / f"{target_path.name}.backup"
        assert backup_path.exists()
        assert (backup_path / "devo").exists()
        assert (backup_path / "_internal" / "base_library.zip").exists()
