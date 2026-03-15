"""macOS platform-specific tests.

Tests macOS-specific functionality including:
- Mach-O binary verification
- Tarball extraction (.tar.gz)
- Tarball format handling
- Permission preservation in tarballs

Requirements: 5.1, 5.4, 5.5
"""

import tarfile

import pytest


@pytest.mark.platform
class TestMacOSBinaryFormat:
    """Test macOS-specific binary format and handling."""

    def test_macos_tarball_verification(self, temp_config_dir):
        """Test tarball verification on macOS (Mach-O header).

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
            tf.extractall(extract_path, filter="data")

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
            tf.extractall(extract_path, filter="data")

        # Verify permissions
        exe_path = extract_path / "devo" / "devo"
        assert exe_path.exists()
        # Check that file is executable
        import os

        assert os.access(exe_path, os.X_OK)
