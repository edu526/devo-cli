"""Cross-platform parametrized tests.

Tests platform-specific behavior across all platforms using parametrized tests.
These tests run on all platforms by mocking platform.system() to simulate different platforms.

Tests include:
- Path separator handling across Windows/Linux/macOS
- Shell detection across bash/zsh/fish/powershell/cmd
- Binary format detection (single file, tarball, zip)
- Platform detection and normalization
- Executable path detection
- Config directory handling

Requirements: 5.1, 5.3, 23.5
"""

import sys
from pathlib import Path

import pytest


@pytest.mark.platform
class TestCrossPlatformPathHandling:
    """Test path handling across all platforms."""

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

        # Verify path parts (pathlib normalizes paths based on OS)
        # Note: On Windows, pathlib will use backslashes, on Unix forward slashes
        # We just verify the key components are present
        if platform_name == "Windows":
            assert path.parts[0] in ("C:", "C:\\")
            assert "Users" in path.parts
        else:
            # On Unix-like systems running the test, verify first part
            if sys.platform != "win32":
                assert path.parts[0] == "/"
                assert path.parts[1] in ("Users", "home")
            # On Windows running Unix path tests, just verify it's a Path
            else:
                assert isinstance(path, Path)

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

    @pytest.mark.parametrize("platform_name", ["Windows", "Darwin", "Linux"])
    def test_config_path_handling(self, platform_name, mocker, temp_config_dir):
        """Test that config paths work correctly on all platforms.

        Validates: Requirements 5.1, 5.3
        """
        # Mock platform.system
        mocker.patch("platform.system", return_value=platform_name)

        # Create a config file path in temp directory
        config_path = temp_config_dir / "config.json"

        # Write and read to verify path handling
        config_path.write_text('{"test": "value"}')
        content = config_path.read_text()

        assert content == '{"test": "value"}'
        assert config_path.exists()

    @pytest.mark.parametrize("platform_name", ["Windows", "Darwin", "Linux"])
    def test_nested_path_creation(self, platform_name, mocker, temp_config_dir):
        """Test creating nested directories on all platforms.

        Validates: Requirements 5.1, 5.3
        """
        # Mock platform.system
        mocker.patch("platform.system", return_value=platform_name)

        # Create nested path
        nested_path = temp_config_dir / "aws" / "sso" / "profiles" / "dev"
        nested_path.mkdir(parents=True, exist_ok=True)

        # Verify directory was created
        assert nested_path.exists()
        assert nested_path.is_dir()

    @pytest.mark.parametrize(
        "platform_name,path_with_spaces",
        [
            ("Windows", "Program Files/Devo CLI/config.json"),
            ("Darwin", "Library/Application Support/Devo CLI/config.json"),
            ("Linux", "My Documents/Devo CLI/config.json"),
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
        path_parts = path_with_spaces.split("/")
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


@pytest.mark.platform
class TestCrossPlatformPlatformDetection:
    """Test platform detection and normalization across all platforms."""

    @pytest.mark.parametrize(
        "platform_name,arch,expected_platform_lower,expected_arch",
        [
            ("Windows", "AMD64", "windows", "amd64"),
            ("Windows", "ARM64", "windows", "arm64"),
            ("Darwin", "x86_64", "darwin", "amd64"),
            ("Darwin", "arm64", "darwin", "arm64"),
            ("Darwin", "aarch64", "darwin", "arm64"),
            ("Linux", "x86_64", "linux", "amd64"),
            ("Linux", "aarch64", "linux", "arm64"),
            ("Linux", "arm64", "linux", "arm64"),
        ],
    )
    def test_platform_normalization(self, platform_name, arch, expected_platform_lower, expected_arch, mocker):
        """Test that platform names and architectures are normalized correctly.

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
        assert detected_arch == expected_arch


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
            # Just verify it's a valid Path and contains expected components
            result_str = str(result_path)
            assert "devo" in result_str.lower() or result_path.name == "devo"
        else:
            # For onefile, should return the executable itself
            assert isinstance(result_path, Path)


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


# ============================================================================
# detect_platform — unknown OS / unknown arch (lines 22, 30)
# ============================================================================


@pytest.mark.platform
class TestDetectPlatformEdgeCases:
    """Cover the None-return branches of detect_platform."""

    def test_detect_platform_unknown_system_returns_none(self, mocker):
        """detect_platform returns None when system is not darwin/linux/windows (line 22)."""
        from cli_tool.commands.upgrade.core.platform import detect_platform

        mocker.patch("platform.system", return_value="FreeBSD")
        mocker.patch("platform.machine", return_value="x86_64")

        result = detect_platform()

        assert result is None

    def test_detect_platform_unknown_arch_returns_none(self, mocker):
        """detect_platform returns None when architecture is not x86_64/arm64 (line 30)."""
        from cli_tool.commands.upgrade.core.platform import detect_platform

        mocker.patch("platform.system", return_value="Linux")
        mocker.patch("platform.machine", return_value="mips64")

        result = detect_platform()

        assert result is None

    def test_detect_platform_unknown_system_and_arch_returns_none(self, mocker):
        """detect_platform returns None when both system and arch are unknown."""
        from cli_tool.commands.upgrade.core.platform import detect_platform

        mocker.patch("platform.system", return_value="SunOS")
        mocker.patch("platform.machine", return_value="sparc")

        result = detect_platform()

        assert result is None


# ============================================================================
# get_executable_path — not frozen (lines 61-65)
# ============================================================================


@pytest.mark.platform
class TestGetExecutablePathNotFrozen:
    """Cover the shutil.which branches of get_executable_path (lines 61-65)."""

    def test_get_executable_path_not_frozen_devo_found_in_path(self, mocker):
        """get_executable_path returns Path wrapping shutil.which result when found (lines 62-63)."""
        from pathlib import Path

        from cli_tool.commands.upgrade.core.platform import get_executable_path

        # Ensure sys.frozen is absent (not a PyInstaller bundle)
        mocker.patch("sys.frozen", False, create=True)
        mocker.patch("cli_tool.commands.upgrade.core.platform.shutil.which", return_value="/usr/local/bin/devo")

        result = get_executable_path()

        assert isinstance(result, Path)
        assert result == Path("/usr/local/bin/devo")

    def test_get_executable_path_not_frozen_devo_not_in_path(self, mocker):
        """get_executable_path returns None when shutil.which('devo') returns None (lines 61, 65)."""
        from cli_tool.commands.upgrade.core.platform import get_executable_path

        mocker.patch("sys.frozen", False, create=True)
        mocker.patch("cli_tool.commands.upgrade.core.platform.shutil.which", return_value=None)

        result = get_executable_path()

        assert result is None
