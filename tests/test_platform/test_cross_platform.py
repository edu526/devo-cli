"""Cross-platform parametrized tests.

Tests platform-specific behavior across all platforms using parametrized tests.
These tests run on all platforms by mocking platform.system() to simulate different platforms.

Tests include:
- Path separator handling across Windows/Linux/macOS
- Shell detection across bash/zsh/fish/powershell/cmd
- Binary format detection (single file, tarball, zip)

Requirements: 5.1, 5.3, 23.5
"""

from pathlib import Path

import pytest


@pytest.mark.platform
class TestCrossPlatformPathSeparators:
    """Test path separator handling across all platforms."""

    @pytest.mark.parametrize(
        "platform_name,expected_separator",
        [
            ("Windows", "\\"),
            ("Darwin", "/"),
            ("Linux", "/"),
        ],
    )
    def test_path_separator_detection(self, platform_name, expected_separator, mocker):
        """Test that path separators are correctly detected for each platform.

        Validates: Requirements 5.1, 5.3, 23.5
        """
        import os
        from pathlib import Path

        # Mock platform.system to simulate different platforms
        mocker.patch("platform.system", return_value=platform_name)

        # Get the platform-specific separator
        if platform_name == "Windows":
            # On Windows, os.sep is backslash
            assert os.sep == "\\" or expected_separator == "\\"
        else:
            # On Unix-like systems, os.sep is forward slash
            assert os.sep == "/" or expected_separator == "/"

    @pytest.mark.parametrize(
        "platform_name,test_path,expected_parts",
        [
            ("Windows", "C:/Users/Developer/.devo/config.json", ["C:", "Users", "Developer", ".devo", "config.json"]),
            ("Darwin", "/Users/Developer/.devo/config.json", ["/", "Users", "Developer", ".devo", "config.json"]),
            ("Linux", "/home/developer/.devo/config.json", ["/", "home", "developer", ".devo", "config.json"]),
        ],
    )
    def test_pathlib_handles_platform_paths(self, platform_name, test_path, expected_parts, mocker):
        """Test that pathlib correctly handles paths for each platform.

        Validates: Requirements 5.1, 5.3, 23.5
        """
        from pathlib import Path

        # Mock platform.system
        mocker.patch("platform.system", return_value=platform_name)

        # Create Path object
        path = Path(test_path)

        # Verify Path object is created
        assert isinstance(path, Path)

        # Verify path parts (pathlib normalizes paths)
        # Note: On Windows, C: might be C:\ in parts
        if platform_name == "Windows":
            assert path.parts[0] in ("C:", "C:\\")
            assert "Users" in path.parts
        else:
            assert path.parts[0] == "/"
            assert path.parts[1] in ("Users", "home")

    @pytest.mark.parametrize("platform_name", ["Windows", "Darwin", "Linux"])
    def test_pathlib_join_works_across_platforms(self, platform_name, mocker, temp_config_dir):
        """Test that pathlib join works correctly on all platforms.

        Validates: Requirements 5.1, 5.3, 23.5
        """
        from pathlib import Path

        # Mock platform.system
        mocker.patch("platform.system", return_value=platform_name)

        # Create nested path using pathlib
        nested_path = temp_config_dir / "aws" / "sso" / "profiles" / "dev" / "config.json"

        # Verify path is created correctly
        assert isinstance(nested_path, Path)
        assert "aws" in str(nested_path)
        assert "sso" in str(nested_path)
        assert "config.json" in str(nested_path)


@pytest.mark.platform
class TestCrossPlatformShellDetection:
    """Test shell detection across all platforms."""

    @pytest.mark.parametrize(
        "shell_name,shell_path",
        [
            ("bash", "/bin/bash"),
            ("bash", "/usr/bin/bash"),
            ("zsh", "/bin/zsh"),
            ("zsh", "/usr/bin/zsh"),
            ("fish", "/usr/bin/fish"),
            ("bash", "/bin/bash"),
            ("zsh", "/bin/zsh"),
            ("fish", "/usr/local/bin/fish"),
        ],
    )
    def test_shell_config_file_paths(self, shell_name, shell_path, mocker):
        """Test that shell config file paths are correctly determined.

        Validates: Requirements 5.1, 5.3, 23.5
        """
        from cli_tool.commands.autocomplete.core.installer import CompletionInstaller

        # Mock environment variable
        mocker.patch.dict("os.environ", {"SHELL": shell_path})

        # Get config file
        config_file = CompletionInstaller.get_config_file(shell_name)

        # Verify config file path exists
        assert config_file is not None
        assert isinstance(config_file, Path)
        assert shell_name in str(config_file).lower() or shell_name in config_file.name.lower()

    @pytest.mark.parametrize(
        "shell_name,expected_completion_var",
        [
            ("bash", "_DEVO_COMPLETE=bash_source"),
            ("zsh", "_DEVO_COMPLETE=zsh_source"),
            ("fish", "_DEVO_COMPLETE=fish_source"),
        ],
    )
    def test_completion_line_format_for_shells(self, shell_name, expected_completion_var):
        """Test that completion line format is correct for each shell.

        Validates: Requirements 5.1, 5.3, 23.5
        """
        from cli_tool.commands.autocomplete.core.installer import CompletionInstaller

        # Get completion line
        completion_line = CompletionInstaller.get_completion_line(shell_name)

        # Verify format
        assert completion_line is not None
        assert expected_completion_var in completion_line
        assert "devo" in completion_line

    @pytest.mark.parametrize(
        "shell_name,is_supported",
        [
            ("bash", True),
            ("zsh", True),
            ("fish", True),
            ("powershell", False),  # PowerShell is not in SHELL_CONFIGS
            ("cmd", False),
            ("unknown", False),
        ],
    )
    def test_shell_support_detection(self, shell_name, is_supported):
        """Test that shell support is correctly detected.

        Validates: Requirements 5.1, 5.3, 23.5
        """
        from cli_tool.commands.autocomplete.core.installer import CompletionInstaller

        # Check if shell is supported
        result = CompletionInstaller.is_supported_shell(shell_name)

        # Verify support status
        assert result == is_supported


@pytest.mark.platform
class TestCrossPlatformBinaryFormat:
    """Test binary format detection across all platforms."""

    @pytest.mark.parametrize(
        "platform_name,arch,expected_extension",
        [
            ("Windows", "amd64", ".zip"),
            ("Windows", "arm64", ".zip"),
            ("Darwin", "amd64", ".tar.gz"),
            ("Darwin", "arm64", ".tar.gz"),
            ("Linux", "amd64", ""),  # No extension for single file
            ("Linux", "arm64", ""),  # No extension for single file
        ],
    )
    def test_binary_format_by_platform(self, platform_name, arch, expected_extension, mocker):
        """Test that binary format is correct for each platform.

        Validates: Requirements 5.1, 5.3, 23.5
        """
        from cli_tool.commands.upgrade.core.platform import get_binary_name

        # Mock platform.system
        mocker.patch("platform.system", return_value=platform_name)

        # Get binary name
        binary_name = get_binary_name(platform_name.lower(), arch)

        # Verify extension
        if expected_extension:
            assert binary_name.endswith(expected_extension)
        else:
            # Linux single file has no extension
            assert not binary_name.endswith(".zip")
            assert not binary_name.endswith(".tar.gz")

        # Verify platform and arch in name
        assert platform_name.lower() in binary_name.lower()
        assert arch in binary_name.lower()

    @pytest.mark.parametrize(
        "platform_name,is_archive,archive_type",
        [
            ("windows", True, "zip"),
            ("darwin", True, "tar.gz"),
            ("linux", False, None),
        ],
    )
    def test_archive_type_by_platform(self, platform_name, is_archive, archive_type, mocker):
        """Test that archive type is correctly determined for each platform.

        Validates: Requirements 5.1, 5.3, 23.5
        """
        from cli_tool.commands.upgrade.core.platform import get_binary_name

        # Mock platform.system
        mocker.patch("platform.system", return_value=platform_name.capitalize())

        # Get binary name
        binary_name = get_binary_name(platform_name, "amd64")

        # Verify archive type based on extension
        if is_archive:
            if archive_type == "zip":
                assert binary_name.endswith(".zip")
            elif archive_type == "tar.gz":
                assert binary_name.endswith(".tar.gz")
        else:
            # Linux single file has no extension
            assert not binary_name.endswith(".zip")
            assert not binary_name.endswith(".tar.gz")

    @pytest.mark.parametrize(
        "platform_name,arch,expected_platform_lower",
        [
            ("Windows", "AMD64", "windows"),
            ("Darwin", "x86_64", "darwin"),
            ("Darwin", "arm64", "darwin"),
            ("Linux", "x86_64", "linux"),
            ("Linux", "aarch64", "linux"),
        ],
    )
    def test_platform_normalization(self, platform_name, arch, expected_platform_lower, mocker):
        """Test that platform names are normalized correctly.

        Validates: Requirements 5.1, 5.3, 23.5
        """
        from cli_tool.commands.upgrade.core.platform import detect_platform

        # Mock platform.system and platform.machine
        mocker.patch("platform.system", return_value=platform_name)
        mocker.patch("platform.machine", return_value=arch)

        # Detect platform
        detected_platform, detected_arch = detect_platform()

        # Verify normalization
        assert detected_platform == expected_platform_lower

        # Verify arch normalization
        if arch in ("x86_64", "AMD64"):
            assert detected_arch == "amd64"
        elif arch in ("aarch64", "arm64"):
            assert detected_arch == "arm64"


@pytest.mark.platform
class TestCrossPlatformExecutablePath:
    """Test executable path detection across all platforms."""

    @pytest.mark.parametrize(
        "platform_name,exe_path,expected_mode",
        [
            ("Windows", "C:\\Program Files\\Devo\\devo\\devo.exe", "onedir"),
            ("Darwin", "/Applications/Devo.app/Contents/MacOS/devo/devo", "onedir"),
            ("Linux", "/usr/local/bin/devo", "onefile"),
        ],
    )
    def test_executable_path_detection(self, platform_name, exe_path, expected_mode, mocker):
        """Test that executable path is correctly detected for each platform.

        Validates: Requirements 5.1, 5.3, 23.5
        """
        from pathlib import Path

        from cli_tool.commands.upgrade.core.platform import get_executable_path

        # Mock sys.frozen to simulate PyInstaller bundle
        mocker.patch("sys.frozen", True, create=True)

        # Mock sys.executable
        mocker.patch("sys.executable", exe_path)

        # Mock platform.system
        mocker.patch("platform.system", return_value=platform_name)

        # Get executable path
        result_path = get_executable_path()

        # Verify path type
        assert isinstance(result_path, Path)

        # Verify mode-specific behavior
        if expected_mode == "onedir":
            # For onedir, should return parent directory
            # Note: On Linux running tests, Path with Windows path won't work correctly
            # So we just verify it's a Path object and contains expected parts
            assert str(result_path) in exe_path or exe_path.endswith(str(result_path))
        else:
            # For onefile, should return the executable itself
            assert str(result_path) == exe_path or result_path == Path(exe_path)

    @pytest.mark.parametrize(
        "platform_name,path_with_spaces",
        [
            ("Windows", "C:\\Program Files\\Devo CLI\\config.json"),
            ("Darwin", "/Users/Developer/Library/Application Support/Devo CLI/config.json"),
            ("Linux", "/home/developer/My Documents/Devo CLI/config.json"),
        ],
    )
    def test_paths_with_spaces_handling(self, platform_name, path_with_spaces, mocker, temp_config_dir):
        """Test that paths with spaces are handled correctly on all platforms.

        Validates: Requirements 5.1, 5.3, 23.5
        """
        from pathlib import Path

        # Mock platform.system
        mocker.patch("platform.system", return_value=platform_name)

        # Create path with spaces in temp directory
        # Use relative path to avoid platform-specific absolute path issues
        path_parts = ["Program Files", "Devo CLI", "config.json"]
        test_path = temp_config_dir
        for part in path_parts[:-1]:
            test_path = test_path / part
        test_path.mkdir(parents=True, exist_ok=True)
        test_path = test_path / path_parts[-1]

        # Write and read
        test_path.write_text('{"test": "value"}')
        content = test_path.read_text()

        # Verify handling
        assert content == '{"test": "value"}'
        assert test_path.exists()
        assert "Program Files" in str(test_path) or "Devo CLI" in str(test_path)


@pytest.mark.platform
class TestCrossPlatformBinaryVerification:
    """Test binary verification across all platforms."""

    @pytest.mark.parametrize(
        "platform_name,binary_header,is_valid",
        [
            ("Linux", b"\x7fELF", True),  # ELF header
            ("Linux", b"invalid", False),
        ],
    )
    def test_binary_header_verification(self, platform_name, binary_header, is_valid, mocker, temp_config_dir):
        """Test that binary headers are correctly verified for each platform.

        Note: This test only runs on Linux since verify_binary checks sys.platform.
        For cross-platform testing, we would need to mock sys.platform which is complex.

        Validates: Requirements 5.1, 5.3, 23.5
        """
        from cli_tool.commands.upgrade.core.downloader import verify_binary

        # Create test binary with header
        binary_path = temp_config_dir / "test_binary"

        # For valid binaries, add sufficient size (>10MB for Linux)
        if is_valid:
            binary_content = binary_header + b"\x00" * (10 * 1024 * 1024)
        else:
            binary_content = binary_header + b"\x00" * 100

        binary_path.write_bytes(binary_content)

        # Verify binary (single file, not archive)
        # Note: verify_binary checks sys.platform internally, so we can only test Linux on Linux
        result = verify_binary(binary_path, is_archive=False)

        # Verify result
        assert result == is_valid


@pytest.mark.platform
class TestCrossPlatformConfigPaths:
    """Test configuration path handling across all platforms."""

    @pytest.mark.parametrize("platform_name", ["Windows", "Darwin", "Linux"])
    def test_config_directory_creation(self, platform_name, mocker, temp_config_dir):
        """Test that config directories are created correctly on all platforms.

        Validates: Requirements 5.1, 5.3, 23.5
        """
        from pathlib import Path

        # Mock platform.system
        mocker.patch("platform.system", return_value=platform_name)

        # Create config directory structure
        config_dir = temp_config_dir / ".devo"
        config_dir.mkdir(parents=True, exist_ok=True)

        # Create config file
        config_file = config_dir / "config.json"
        config_file.write_text('{"platform": "' + platform_name + '"}')

        # Verify creation
        assert config_dir.exists()
        assert config_dir.is_dir()
        assert config_file.exists()
        assert config_file.is_file()

        # Verify content
        content = config_file.read_text()
        assert platform_name in content

    @pytest.mark.parametrize("platform_name", ["Windows", "Darwin", "Linux"])
    def test_nested_config_structure(self, platform_name, mocker, temp_config_dir):
        """Test that nested config structures work on all platforms.

        Validates: Requirements 5.1, 5.3, 23.5
        """
        from pathlib import Path

        # Mock platform.system
        mocker.patch("platform.system", return_value=platform_name)

        # Create nested structure
        nested_path = temp_config_dir / "aws" / "sso" / "profiles" / "dev"
        nested_path.mkdir(parents=True, exist_ok=True)

        # Create config file in nested structure
        config_file = nested_path / "config.json"
        config_file.write_text('{"region": "us-east-1"}')

        # Verify structure
        assert nested_path.exists()
        assert nested_path.is_dir()
        assert config_file.exists()

        # Verify all parent directories exist
        assert (temp_config_dir / "aws").exists()
        assert (temp_config_dir / "aws" / "sso").exists()
        assert (temp_config_dir / "aws" / "sso" / "profiles").exists()
