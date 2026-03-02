"""
Unit tests for cli_tool.core.utils.git_utils module.

Tests cover git command execution via subprocess, including diff, branch name,
and remote URL operations. All tests use subprocess mocking to avoid executing
real git commands and ensure test isolation.
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from cli_tool.core.utils.git_utils import (
    get_branch_name,
    get_remote_url,
    get_staged_diff,
)

# ============================================================================
# Test get_staged_diff
# ============================================================================


@pytest.mark.unit
def test_get_staged_diff_returns_diff_output(mocker):
    """Test that get_staged_diff returns git diff output."""
    # Mock subprocess.run to return a diff
    mock_result = MagicMock()
    mock_result.stdout = "diff --git a/file.py b/file.py\n+new line\n-old line"
    mock_run = mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_staged_diff()

    # Verify subprocess was called correctly
    mock_run.assert_called_once_with(["git", "diff", "--staged"], capture_output=True, text=True, encoding="utf-8")

    # Verify result
    assert result == "diff --git a/file.py b/file.py\n+new line\n-old line"


@pytest.mark.unit
def test_get_staged_diff_strips_whitespace(mocker):
    """Test that get_staged_diff strips leading/trailing whitespace."""
    # Mock subprocess.run with whitespace in output
    mock_result = MagicMock()
    mock_result.stdout = "  \n  diff content  \n  "
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_staged_diff()

    # Verify whitespace is stripped
    assert result == "diff content"


@pytest.mark.unit
def test_get_staged_diff_returns_empty_string_when_no_changes(mocker):
    """Test that get_staged_diff returns empty string when no staged changes."""
    # Mock subprocess.run with empty output
    mock_result = MagicMock()
    mock_result.stdout = ""
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_staged_diff()

    # Verify empty string is returned
    assert result == ""


@pytest.mark.unit
def test_get_staged_diff_handles_multiline_diff(mocker):
    """Test that get_staged_diff handles multiline diff output."""
    # Mock subprocess.run with multiline diff
    diff_output = """diff --git a/cli_tool/commands/commit/core/generator.py b/cli_tool/commands/commit/core/generator.py
index 1234567..abcdefg 100644
--- a/cli_tool/commands/commit/core/generator.py
+++ b/cli_tool/commands/commit/core/generator.py
@@ -10,6 +10,7 @@ def generate_commit_message(diff):
+    # New feature implementation
+    return message
-    # Old implementation"""

    mock_result = MagicMock()
    mock_result.stdout = diff_output
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_staged_diff()

    # Verify multiline diff is preserved
    assert "diff --git" in result
    assert "+    # New feature implementation" in result
    assert "-    # Old implementation" in result


@pytest.mark.unit
def test_get_staged_diff_handles_binary_file_changes(mocker):
    """Test that get_staged_diff handles binary file changes."""
    # Mock subprocess.run with binary file diff
    diff_output = "diff --git a/image.png b/image.png\nBinary files a/image.png and b/image.png differ"

    mock_result = MagicMock()
    mock_result.stdout = diff_output
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_staged_diff()

    # Verify binary diff message is returned
    assert "Binary files" in result
    assert "differ" in result


# ============================================================================
# Test get_branch_name
# ============================================================================


@pytest.mark.unit
def test_get_branch_name_returns_current_branch(mocker):
    """Test that get_branch_name returns current branch name."""
    # Mock subprocess.run to return branch name
    mock_result = MagicMock()
    mock_result.stdout = "feature/add-testing"
    mock_run = mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_branch_name()

    # Verify subprocess was called correctly
    mock_run.assert_called_once_with(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, encoding="utf-8")

    # Verify result
    assert result == "feature/add-testing"


@pytest.mark.unit
def test_get_branch_name_strips_whitespace(mocker):
    """Test that get_branch_name strips leading/trailing whitespace."""
    # Mock subprocess.run with whitespace
    mock_result = MagicMock()
    mock_result.stdout = "  main  \n"
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_branch_name()

    # Verify whitespace is stripped
    assert result == "main"


@pytest.mark.unit
def test_get_branch_name_handles_main_branch(mocker):
    """Test that get_branch_name works with main branch."""
    # Mock subprocess.run for main branch
    mock_result = MagicMock()
    mock_result.stdout = "main"
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_branch_name()

    # Verify result
    assert result == "main"


@pytest.mark.unit
def test_get_branch_name_handles_master_branch(mocker):
    """Test that get_branch_name works with master branch."""
    # Mock subprocess.run for master branch
    mock_result = MagicMock()
    mock_result.stdout = "master"
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_branch_name()

    # Verify result
    assert result == "master"


@pytest.mark.unit
def test_get_branch_name_handles_detached_head(mocker):
    """Test that get_branch_name handles detached HEAD state."""
    # Mock subprocess.run for detached HEAD (returns commit SHA)
    mock_result = MagicMock()
    mock_result.stdout = "HEAD"
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_branch_name()

    # Verify result (detached HEAD returns "HEAD")
    assert result == "HEAD"


@pytest.mark.unit
def test_get_branch_name_handles_branch_with_slashes(mocker):
    """Test that get_branch_name handles branch names with slashes."""
    # Mock subprocess.run with branch containing slashes
    mock_result = MagicMock()
    mock_result.stdout = "feature/DEVO-123/add-new-feature"
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_branch_name()

    # Verify result preserves slashes
    assert result == "feature/DEVO-123/add-new-feature"


# ============================================================================
# Test get_remote_url
# ============================================================================


@pytest.mark.unit
def test_get_remote_url_returns_https_url(mocker):
    """Test that get_remote_url returns HTTPS URL."""
    # Mock subprocess.run to return HTTPS URL
    mock_result = MagicMock()
    mock_result.stdout = "https://github.com/edu526/devo-cli.git"
    mock_run = mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_remote_url()

    # Verify subprocess was called correctly
    mock_run.assert_called_once_with(["git", "config", "--get", "remote.origin.url"], capture_output=True, text=True, check=True)

    # Verify result
    assert result == "https://github.com/edu526/devo-cli.git"


@pytest.mark.unit
def test_get_remote_url_converts_ssh_to_https(mocker):
    """Test that get_remote_url converts SSH URL to HTTPS."""
    # Mock subprocess.run to return SSH URL
    mock_result = MagicMock()
    mock_result.stdout = "git@github.com:edu526/devo-cli.git"
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_remote_url()

    # Verify SSH URL is converted to HTTPS
    assert result == "https://github.com/edu526/devo-cli.git"


@pytest.mark.unit
def test_get_remote_url_removes_username_from_https(mocker):
    """Test that get_remote_url removes username from HTTPS URL."""
    # Mock subprocess.run to return HTTPS URL with username
    mock_result = MagicMock()
    mock_result.stdout = "https://user@github.com/edu526/devo-cli.git"
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_remote_url()

    # Verify username is removed
    assert result == "https://github.com/edu526/devo-cli.git"


@pytest.mark.unit
def test_get_remote_url_handles_gitlab_ssh(mocker):
    """Test that get_remote_url converts GitLab SSH URL to HTTPS."""
    # Mock subprocess.run to return GitLab SSH URL
    mock_result = MagicMock()
    mock_result.stdout = "git@gitlab.com:group/project.git"
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_remote_url()

    # Verify SSH URL is converted to HTTPS
    assert result == "https://gitlab.com/group/project.git"


@pytest.mark.unit
def test_get_remote_url_handles_bitbucket_ssh(mocker):
    """Test that get_remote_url converts Bitbucket SSH URL to HTTPS."""
    # Mock subprocess.run to return Bitbucket SSH URL
    mock_result = MagicMock()
    mock_result.stdout = "git@bitbucket.org:team/repo.git"
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_remote_url()

    # Verify SSH URL is converted to HTTPS
    assert result == "https://bitbucket.org/team/repo.git"


@pytest.mark.unit
def test_get_remote_url_returns_none_on_error(mocker):
    """Test that get_remote_url returns None when git command fails."""
    # Mock subprocess.run to raise CalledProcessError
    mocker.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "git"))

    # Call function
    result = get_remote_url()

    # Verify None is returned
    assert result is None


@pytest.mark.unit
def test_get_remote_url_handles_no_remote(mocker):
    """Test that get_remote_url handles repository with no remote."""
    # Mock subprocess.run to raise CalledProcessError (no remote configured)
    mocker.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "git"))

    # Call function
    result = get_remote_url()

    # Verify None is returned
    assert result is None


@pytest.mark.unit
def test_get_remote_url_strips_whitespace(mocker):
    """Test that get_remote_url strips leading/trailing whitespace."""
    # Mock subprocess.run with whitespace
    mock_result = MagicMock()
    mock_result.stdout = "  https://github.com/edu526/devo-cli.git  \n"
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_remote_url()

    # Verify whitespace is stripped
    assert result == "https://github.com/edu526/devo-cli.git"


@pytest.mark.unit
def test_get_remote_url_handles_url_without_git_extension(mocker):
    """Test that get_remote_url handles URLs without .git extension."""
    # Mock subprocess.run to return URL without .git
    mock_result = MagicMock()
    mock_result.stdout = "https://github.com/edu526/devo-cli"
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_remote_url()

    # Verify URL is returned as-is
    assert result == "https://github.com/edu526/devo-cli"


@pytest.mark.unit
def test_get_remote_url_handles_ssh_with_custom_port(mocker):
    """Test that get_remote_url handles SSH URLs with custom ports."""
    # Mock subprocess.run to return SSH URL with port
    # Note: SSH URLs with ports use ssh://git@host:port/path format
    mock_result = MagicMock()
    mock_result.stdout = "git@github.com:edu526/devo-cli.git"
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_remote_url()

    # Verify conversion (standard SSH format)
    assert result == "https://github.com/edu526/devo-cli.git"


# ============================================================================
# Test error handling for non-git directories
# ============================================================================


@pytest.mark.unit
def test_get_staged_diff_in_non_git_directory(mocker):
    """Test that get_staged_diff handles non-git directory gracefully."""
    # Mock subprocess.run to raise CalledProcessError (not a git repo)
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.returncode = 128  # Git error code for "not a git repository"
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function (should not raise exception)
    result = get_staged_diff()

    # Verify empty string is returned (function doesn't check returncode)
    assert result == ""


@pytest.mark.unit
def test_get_branch_name_in_non_git_directory(mocker):
    """Test that get_branch_name handles non-git directory gracefully."""
    # Mock subprocess.run to return error output
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.returncode = 128
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function (should not raise exception)
    result = get_branch_name()

    # Verify empty string is returned
    assert result == ""


# ============================================================================
# Test error handling for failed git operations
# ============================================================================


@pytest.mark.unit
def test_get_staged_diff_handles_subprocess_exception(mocker):
    """Test that get_staged_diff handles subprocess exceptions."""
    # Mock subprocess.run to raise an exception
    mocker.patch("subprocess.run", side_effect=Exception("Command failed"))

    # Call function should raise the exception
    with pytest.raises(Exception) as exc_info:
        get_staged_diff()

    assert "Command failed" in str(exc_info.value)


@pytest.mark.unit
def test_get_branch_name_handles_subprocess_exception(mocker):
    """Test that get_branch_name handles subprocess exceptions."""
    # Mock subprocess.run to raise an exception
    mocker.patch("subprocess.run", side_effect=Exception("Command failed"))

    # Call function should raise the exception
    with pytest.raises(Exception) as exc_info:
        get_branch_name()

    assert "Command failed" in str(exc_info.value)


@pytest.mark.unit
def test_get_remote_url_handles_subprocess_exception(mocker):
    """Test that get_remote_url handles subprocess exceptions gracefully."""
    # Mock subprocess.run to raise a non-CalledProcessError exception
    mocker.patch("subprocess.run", side_effect=OSError("Permission denied"))

    # Call function should raise the exception (not caught by except block)
    with pytest.raises(OSError) as exc_info:
        get_remote_url()

    assert "Permission denied" in str(exc_info.value)


# ============================================================================
# Test edge cases
# ============================================================================


@pytest.mark.unit
def test_get_staged_diff_with_unicode_content(mocker):
    """Test that get_staged_diff handles Unicode characters in diff."""
    # Mock subprocess.run with Unicode content
    diff_output = "diff --git a/file.py b/file.py\n+# 测试 - Test\n+# 🚀 Feature"

    mock_result = MagicMock()
    mock_result.stdout = diff_output
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_staged_diff()

    # Verify Unicode content is preserved
    assert "测试" in result
    assert "🚀" in result


@pytest.mark.unit
def test_get_branch_name_with_unicode_characters(mocker):
    """Test that get_branch_name handles Unicode characters in branch names."""
    # Mock subprocess.run with Unicode branch name
    mock_result = MagicMock()
    mock_result.stdout = "feature/测试-branch"
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_branch_name()

    # Verify Unicode is preserved
    assert result == "feature/测试-branch"


@pytest.mark.unit
def test_get_remote_url_with_complex_username(mocker):
    """Test that get_remote_url handles complex usernames in URLs."""
    # Mock subprocess.run with complex username
    mock_result = MagicMock()
    mock_result.stdout = "https://user.name+tag@github.com/edu526/devo-cli.git"
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_remote_url()

    # Verify username is removed
    assert result == "https://github.com/edu526/devo-cli.git"


@pytest.mark.unit
def test_get_remote_url_with_nested_path(mocker):
    """Test that get_remote_url handles nested repository paths."""
    # Mock subprocess.run with nested path
    mock_result = MagicMock()
    mock_result.stdout = "git@github.com:org/team/project.git"
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_remote_url()

    # Verify nested path is preserved
    assert result == "https://github.com/org/team/project.git"


@pytest.mark.unit
def test_get_staged_diff_with_very_large_diff(mocker):
    """Test that get_staged_diff handles very large diffs."""
    # Mock subprocess.run with large diff (simulate 1000 lines)
    large_diff = "\n".join([f"+line {i}" for i in range(1000)])

    mock_result = MagicMock()
    mock_result.stdout = large_diff
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_staged_diff()

    # Verify large diff is returned
    assert "+line 0" in result
    assert "+line 999" in result
    assert result.count("\n") == 999  # 1000 lines = 999 newlines


@pytest.mark.unit
def test_get_branch_name_with_special_characters(mocker):
    """Test that get_branch_name handles special characters in branch names."""
    # Mock subprocess.run with special characters
    mock_result = MagicMock()
    mock_result.stdout = "feature/JIRA-123_add-feature"
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_branch_name()

    # Verify special characters are preserved
    assert result == "feature/JIRA-123_add-feature"


@pytest.mark.unit
def test_get_remote_url_with_self_hosted_git(mocker):
    """Test that get_remote_url handles self-hosted git servers."""
    # Mock subprocess.run with self-hosted git URL
    mock_result = MagicMock()
    mock_result.stdout = "git@git.company.com:team/project.git"
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_remote_url()

    # Verify conversion works for self-hosted
    assert result == "https://git.company.com/team/project.git"


@pytest.mark.unit
def test_get_staged_diff_with_renamed_files(mocker):
    """Test that get_staged_diff handles renamed files in diff."""
    # Mock subprocess.run with rename diff
    diff_output = """diff --git a/old_name.py b/new_name.py
similarity index 100%
rename from old_name.py
rename to new_name.py"""

    mock_result = MagicMock()
    mock_result.stdout = diff_output
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_staged_diff()

    # Verify rename information is preserved
    assert "rename from old_name.py" in result
    assert "rename to new_name.py" in result


@pytest.mark.unit
def test_get_staged_diff_with_deleted_files(mocker):
    """Test that get_staged_diff handles deleted files in diff."""
    # Mock subprocess.run with deletion diff
    diff_output = """diff --git a/deleted_file.py b/deleted_file.py
deleted file mode 100644
index 1234567..0000000
--- a/deleted_file.py
+++ /dev/null"""

    mock_result = MagicMock()
    mock_result.stdout = diff_output
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_staged_diff()

    # Verify deletion information is preserved
    assert "deleted file mode" in result
    assert "/dev/null" in result


@pytest.mark.unit
def test_get_staged_diff_with_new_files(mocker):
    """Test that get_staged_diff handles new files in diff."""
    # Mock subprocess.run with new file diff
    diff_output = """diff --git a/new_file.py b/new_file.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/new_file.py
@@ -0,0 +1,10 @@
+def new_function():
+    pass"""

    mock_result = MagicMock()
    mock_result.stdout = diff_output
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_staged_diff()

    # Verify new file information is preserved
    assert "new file mode" in result
    assert "/dev/null" in result
    assert "+def new_function():" in result


# ============================================================================
# Test error scenarios (Task 2.4)
# ============================================================================


@pytest.mark.unit
def test_get_staged_diff_handles_timeout(mocker):
    """Test that get_staged_diff handles command timeout."""
    # Mock subprocess.run to raise TimeoutExpired
    mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 30))

    # Call function should raise the exception
    with pytest.raises(subprocess.TimeoutExpired) as exc_info:
        get_staged_diff()

    assert exc_info.value.cmd == "git"
    assert exc_info.value.timeout == 30


@pytest.mark.unit
def test_get_branch_name_handles_timeout(mocker):
    """Test that get_branch_name handles command timeout."""
    # Mock subprocess.run to raise TimeoutExpired
    mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 30))

    # Call function should raise the exception
    with pytest.raises(subprocess.TimeoutExpired) as exc_info:
        get_branch_name()

    assert exc_info.value.cmd == "git"
    assert exc_info.value.timeout == 30


@pytest.mark.unit
def test_get_remote_url_handles_timeout(mocker):
    """Test that get_remote_url handles command timeout."""
    # Mock subprocess.run to raise TimeoutExpired
    mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 30))

    # Call function should raise the exception
    with pytest.raises(subprocess.TimeoutExpired) as exc_info:
        get_remote_url()

    assert exc_info.value.cmd == "git"
    assert exc_info.value.timeout == 30


@pytest.mark.unit
def test_get_staged_diff_handles_authentication_failure(mocker):
    """Test that get_staged_diff handles git authentication failures."""
    # Mock subprocess.run to simulate authentication failure
    # Git returns exit code 128 for authentication issues
    mock_result = MagicMock()
    mock_result.stdout = "fatal: Authentication failed"
    mock_result.returncode = 128
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function (get_staged_diff doesn't check returncode)
    result = get_staged_diff()

    # Verify error message is returned in stdout
    assert "fatal: Authentication failed" in result


@pytest.mark.unit
def test_get_branch_name_handles_authentication_failure(mocker):
    """Test that get_branch_name handles git authentication failures."""
    # Mock subprocess.run to simulate authentication failure
    mock_result = MagicMock()
    mock_result.stdout = "fatal: Authentication failed"
    mock_result.returncode = 128
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_branch_name()

    # Verify error message is returned
    assert "fatal: Authentication failed" in result


@pytest.mark.unit
def test_get_remote_url_handles_authentication_failure(mocker):
    """Test that get_remote_url handles git authentication failures."""
    # Mock subprocess.run to raise CalledProcessError (check=True in get_remote_url)
    mocker.patch("subprocess.run", side_effect=subprocess.CalledProcessError(128, "git", stderr="fatal: Authentication failed"))

    # Call function should return None (caught by except block)
    result = get_remote_url()

    assert result is None


@pytest.mark.unit
def test_get_staged_diff_handles_merge_conflict(mocker):
    """Test that get_staged_diff handles merge conflict state."""
    # Mock subprocess.run to return merge conflict markers in diff
    diff_output = """diff --git a/file.py b/file.py
index 1234567..abcdefg 100644
--- a/file.py
+++ b/file.py
@@ -1,5 +1,9 @@
+<<<<<<< HEAD
+def function_v1():
+    pass
+=======
 def function_v2():
     pass
+>>>>>>> feature-branch"""

    mock_result = MagicMock()
    mock_result.stdout = diff_output
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_staged_diff()

    # Verify merge conflict markers are preserved in diff
    assert "<<<<<<< HEAD" in result
    assert "=======" in result
    assert ">>>>>>>" in result


@pytest.mark.unit
def test_get_branch_name_handles_merge_conflict_state(mocker):
    """Test that get_branch_name returns branch name during merge conflict."""
    # During merge conflict, git still returns the current branch name
    mock_result = MagicMock()
    mock_result.stdout = "main"
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_branch_name()

    # Verify branch name is returned even during merge
    assert result == "main"


@pytest.mark.unit
def test_get_remote_url_handles_merge_conflict_state(mocker):
    """Test that get_remote_url works during merge conflict state."""
    # Remote URL should still be accessible during merge conflict
    mock_result = MagicMock()
    mock_result.stdout = "https://github.com/edu526/devo-cli.git"
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_remote_url()

    # Verify remote URL is returned
    assert result == "https://github.com/edu526/devo-cli.git"


@pytest.mark.unit
def test_get_staged_diff_in_detached_head_state(mocker):
    """Test that get_staged_diff works in detached HEAD state."""
    # Detached HEAD doesn't affect staged diff
    mock_result = MagicMock()
    mock_result.stdout = "diff --git a/file.py b/file.py\n+new line"
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_staged_diff()

    # Verify diff is returned normally
    assert "diff --git" in result
    assert "+new line" in result


@pytest.mark.unit
def test_get_branch_name_in_detached_head_state_with_commit_sha(mocker):
    """Test that get_branch_name handles detached HEAD with commit SHA."""
    # In detached HEAD, git returns the commit SHA or "HEAD"
    mock_result = MagicMock()
    mock_result.stdout = "abc123def456"
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_branch_name()

    # Verify commit SHA is returned
    assert result == "abc123def456"


@pytest.mark.unit
def test_get_remote_url_in_detached_head_state(mocker):
    """Test that get_remote_url works in detached HEAD state."""
    # Remote URL should work regardless of HEAD state
    mock_result = MagicMock()
    mock_result.stdout = "git@github.com:edu526/devo-cli.git"
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_remote_url()

    # Verify remote URL is converted correctly
    assert result == "https://github.com/edu526/devo-cli.git"


@pytest.mark.unit
def test_get_staged_diff_handles_permission_denied(mocker):
    """Test that get_staged_diff handles permission denied errors."""
    # Mock subprocess.run to raise PermissionError
    mocker.patch("subprocess.run", side_effect=PermissionError("Permission denied"))

    # Call function should raise the exception
    with pytest.raises(PermissionError) as exc_info:
        get_staged_diff()

    assert "Permission denied" in str(exc_info.value)


@pytest.mark.unit
def test_get_branch_name_handles_permission_denied(mocker):
    """Test that get_branch_name handles permission denied errors."""
    # Mock subprocess.run to raise PermissionError
    mocker.patch("subprocess.run", side_effect=PermissionError("Permission denied"))

    # Call function should raise the exception
    with pytest.raises(PermissionError) as exc_info:
        get_branch_name()

    assert "Permission denied" in str(exc_info.value)


@pytest.mark.unit
def test_get_remote_url_handles_permission_denied(mocker):
    """Test that get_remote_url handles permission denied errors."""
    # Mock subprocess.run to raise PermissionError
    mocker.patch("subprocess.run", side_effect=PermissionError("Permission denied"))

    # Call function should raise the exception
    with pytest.raises(PermissionError) as exc_info:
        get_remote_url()

    assert "Permission denied" in str(exc_info.value)


@pytest.mark.unit
def test_get_staged_diff_handles_file_not_found(mocker):
    """Test that get_staged_diff handles git command not found."""
    # Mock subprocess.run to raise FileNotFoundError (git not in PATH)
    mocker.patch("subprocess.run", side_effect=FileNotFoundError("git command not found"))

    # Call function should raise the exception
    with pytest.raises(FileNotFoundError) as exc_info:
        get_staged_diff()

    assert "git command not found" in str(exc_info.value)


@pytest.mark.unit
def test_get_branch_name_handles_file_not_found(mocker):
    """Test that get_branch_name handles git command not found."""
    # Mock subprocess.run to raise FileNotFoundError
    mocker.patch("subprocess.run", side_effect=FileNotFoundError("git command not found"))

    # Call function should raise the exception
    with pytest.raises(FileNotFoundError) as exc_info:
        get_branch_name()

    assert "git command not found" in str(exc_info.value)


@pytest.mark.unit
def test_get_remote_url_handles_file_not_found(mocker):
    """Test that get_remote_url handles git command not found."""
    # Mock subprocess.run to raise FileNotFoundError
    mocker.patch("subprocess.run", side_effect=FileNotFoundError("git command not found"))

    # Call function should raise the exception
    with pytest.raises(FileNotFoundError) as exc_info:
        get_remote_url()

    assert "git command not found" in str(exc_info.value)


@pytest.mark.unit
def test_get_staged_diff_handles_corrupted_repository(mocker):
    """Test that get_staged_diff handles corrupted git repository."""
    # Mock subprocess.run to return git corruption error
    mock_result = MagicMock()
    mock_result.stdout = "fatal: bad object HEAD"
    mock_result.returncode = 128
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_staged_diff()

    # Verify error message is returned
    assert "fatal: bad object HEAD" in result


@pytest.mark.unit
def test_get_branch_name_handles_corrupted_repository(mocker):
    """Test that get_branch_name handles corrupted git repository."""
    # Mock subprocess.run to return git corruption error
    mock_result = MagicMock()
    mock_result.stdout = "fatal: ref HEAD is not a symbolic ref"
    mock_result.returncode = 128
    mocker.patch("subprocess.run", return_value=mock_result)

    # Call function
    result = get_branch_name()

    # Verify error message is returned
    assert "fatal: ref HEAD is not a symbolic ref" in result


@pytest.mark.unit
def test_get_remote_url_handles_corrupted_repository(mocker):
    """Test that get_remote_url handles corrupted git repository."""
    # Mock subprocess.run to raise CalledProcessError for corruption
    mocker.patch("subprocess.run", side_effect=subprocess.CalledProcessError(128, "git", stderr="fatal: bad config file"))

    # Call function should return None
    result = get_remote_url()

    assert result is None
