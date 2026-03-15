"""
Unit tests for cli_tool.commands.code_reviewer.core.git_utils module.

Tests cover GitManager methods using mocked GitPython Repo objects.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cli_tool.commands.code_reviewer.core.git_utils import GitManager

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_repo():
    """Return a MagicMock simulating a git.Repo object."""
    repo = MagicMock()
    repo.active_branch.name = "feature/my-feature"
    return repo


@pytest.fixture
def git_manager(mock_repo):
    """Return a GitManager with a mocked Repo."""
    with patch("git.Repo", return_value=mock_repo):
        manager = GitManager("/fake/repo")
    manager.repo = mock_repo
    return manager


# ============================================================================
# __init__
# ============================================================================


@pytest.mark.unit
def test_git_manager_init_success(mock_repo):
    """GitManager initialises when given a valid repository path."""
    with patch("git.Repo", return_value=mock_repo):
        manager = GitManager("/valid/repo")
    assert manager.repo is mock_repo


@pytest.mark.unit
def test_git_manager_init_invalid_repo():
    """Raises InvalidGitRepositoryError when path is not a git repo."""
    from git import InvalidGitRepositoryError

    with patch("git.Repo", side_effect=InvalidGitRepositoryError("/bad")):
        with pytest.raises(InvalidGitRepositoryError):
            GitManager("/bad/path")


@pytest.mark.unit
def test_git_manager_uses_cwd_by_default(mock_repo):
    """Uses os.getcwd() when repo_path is not provided."""
    with patch("git.Repo", return_value=mock_repo):
        with patch("os.getcwd", return_value="/cwd"):
            manager = GitManager()
    assert manager.repo_path == "/cwd"


# ============================================================================
# get_current_branch
# ============================================================================


@pytest.mark.unit
def test_get_current_branch_returns_branch_name(git_manager, mock_repo):
    """Returns the name of the active branch."""
    mock_repo.active_branch.name = "feature/new-feature"
    result = git_manager.get_current_branch()
    assert result == "feature/new-feature"


# ============================================================================
# get_base_branch
# ============================================================================


@pytest.mark.unit
def test_get_base_branch_returns_default_when_exists(git_manager, mock_repo):
    """Returns the default_base when it exists in the repo refs."""
    ref = MagicMock()
    ref.name = "main"
    mock_repo.refs = [ref]

    result = git_manager.get_base_branch(default_base="main")

    assert result == "main"


@pytest.mark.unit
def test_get_base_branch_falls_back_to_master(git_manager, mock_repo):
    """Falls back to 'master' when 'main' is not found."""
    main_ref = MagicMock()
    main_ref.name = "master"
    mock_repo.refs = [main_ref]

    result = git_manager.get_base_branch(default_base="main")

    assert result == "master"


@pytest.mark.unit
def test_get_base_branch_returns_develop_when_no_main_master(git_manager, mock_repo):
    """Falls back to 'develop' when neither main nor master exists."""
    dev_ref = MagicMock()
    dev_ref.name = "develop"
    mock_repo.refs = [dev_ref]

    result = git_manager.get_base_branch(default_base="main")

    assert result == "develop"


@pytest.mark.unit
def test_get_base_branch_returns_first_branch_as_last_resort(git_manager, mock_repo):
    """Returns the first non-origin branch when no common base is found."""
    custom_ref = MagicMock()
    custom_ref.name = "custom-branch"
    mock_repo.refs = [custom_ref]

    result = git_manager.get_base_branch(default_base="main")

    assert result == "custom-branch"


@pytest.mark.unit
def test_get_base_branch_raises_when_no_refs(git_manager, mock_repo):
    """Raises ValueError when no suitable base branch is found."""
    mock_repo.refs = []

    with pytest.raises(ValueError, match="No suitable base branch found"):
        git_manager.get_base_branch(default_base="main")


# ============================================================================
# get_changed_files
# ============================================================================


@pytest.mark.unit
def test_get_changed_files_returns_list(git_manager, mock_repo):
    """Returns list of changed files."""
    merge_base = MagicMock()
    mock_repo.merge_base.return_value = [merge_base]
    mock_repo.git.diff.return_value = "file1.py\nfile2.py\nfile3.py"

    with patch.object(git_manager, "get_base_branch", return_value="main"):
        result = git_manager.get_changed_files("main")

    assert "file1.py" in result
    assert "file2.py" in result
    assert "file3.py" in result


@pytest.mark.unit
def test_get_changed_files_empty_diff(git_manager, mock_repo):
    """Returns empty list when no files were changed."""
    merge_base = MagicMock()
    mock_repo.merge_base.return_value = [merge_base]
    mock_repo.git.diff.return_value = ""

    with patch.object(git_manager, "get_base_branch", return_value="main"):
        result = git_manager.get_changed_files("main")

    assert result == []


@pytest.mark.unit
def test_get_changed_files_handles_no_merge_base(git_manager, mock_repo):
    """Falls back to base_branch string when IndexError occurs on merge_base."""
    mock_repo.merge_base.return_value = []
    mock_repo.git.diff.return_value = "some_file.py"

    with patch.object(git_manager, "get_base_branch", return_value="main"):
        result = git_manager.get_changed_files("main")

    assert isinstance(result, list)


@pytest.mark.unit
def test_get_changed_files_auto_detects_base_branch(git_manager, mock_repo):
    """Calls get_base_branch when base_branch=None."""
    merge_base = MagicMock()
    mock_repo.merge_base.return_value = [merge_base]
    mock_repo.git.diff.return_value = "file.py"

    with patch.object(git_manager, "get_base_branch", return_value="main") as mock_get_base:
        git_manager.get_changed_files(base_branch=None)

    mock_get_base.assert_called_once()


# ============================================================================
# get_file_diff
# ============================================================================


@pytest.mark.unit
def test_get_file_diff_returns_diff_string(git_manager, mock_repo):
    """Returns the diff string for a changed file."""
    merge_base = MagicMock()
    mock_repo.merge_base.return_value = [merge_base]
    diff_content = "diff --git a/file.py b/file.py\n+new line"
    mock_repo.git.diff.return_value = diff_content

    with patch.object(git_manager, "get_base_branch", return_value="main"):
        result = git_manager.get_file_diff("file.py", "main")

    assert result == diff_content


@pytest.mark.unit
def test_get_file_diff_empty_diff_file_exists_in_base(git_manager, mock_repo):
    """Returns 'No changes' when diff is empty and file exists in base."""
    merge_base = MagicMock()
    mock_repo.merge_base.return_value = [merge_base]
    mock_repo.git.diff.return_value = ""
    mock_repo.git.show.return_value = "existing content"

    with patch.object(git_manager, "get_base_branch", return_value="main"):
        result = git_manager.get_file_diff("unchanged.py", "main")

    assert "No changes" in result


@pytest.mark.unit
def test_get_file_diff_new_file_not_in_base(git_manager, mock_repo):
    """Returns synthetic diff when file is new (not in base branch)."""
    merge_base = MagicMock()
    mock_repo.merge_base.return_value = [merge_base]
    mock_repo.git.diff.return_value = ""
    # First show raises (file not in base), second show returns file content
    mock_repo.git.show.side_effect = [Exception("not found in base"), "line1\nline2\n"]

    with patch.object(git_manager, "get_base_branch", return_value="main"):
        result = git_manager.get_file_diff("new_file.py", "main")

    assert "+line1" in result or "new file" in result.lower()


@pytest.mark.unit
def test_get_file_diff_error_returns_error_string(git_manager, mock_repo):
    """Returns error string when git diff raises an exception."""
    merge_base = MagicMock()
    mock_repo.merge_base.return_value = [merge_base]
    mock_repo.git.diff.side_effect = Exception("git error")

    with patch.object(git_manager, "get_base_branch", return_value="main"):
        result = git_manager.get_file_diff("file.py", "main")

    assert "Error getting diff" in result


# ============================================================================
# get_full_diff
# ============================================================================


@pytest.mark.unit
def test_get_full_diff_returns_complete_diff(git_manager, mock_repo):
    """Returns the full diff between current branch and base."""
    merge_base = MagicMock()
    mock_repo.merge_base.return_value = [merge_base]
    full_diff = "diff --git a/a.py b/a.py\n+change"
    mock_repo.git.diff.return_value = full_diff

    with patch.object(git_manager, "get_base_branch", return_value="main"):
        result = git_manager.get_full_diff("main")

    assert result == full_diff


# ============================================================================
# is_file_supported
# ============================================================================


@pytest.mark.unit
def test_is_file_supported_python_file(git_manager):
    """Python files are supported."""
    assert git_manager.is_file_supported("module.py") is True


@pytest.mark.unit
def test_is_file_supported_javascript_file(git_manager):
    """JavaScript files are supported."""
    assert git_manager.is_file_supported("app.js") is True


@pytest.mark.unit
def test_is_file_supported_markdown_file(git_manager):
    """Markdown files are supported (text-based)."""
    assert git_manager.is_file_supported("README.md") is True


@pytest.mark.unit
def test_is_file_supported_binary_file_png(git_manager):
    """PNG files are NOT supported."""
    assert git_manager.is_file_supported("image.png") is False


@pytest.mark.unit
def test_is_file_supported_binary_file_exe(git_manager):
    """EXE files are NOT supported."""
    assert git_manager.is_file_supported("program.exe") is False


@pytest.mark.unit
def test_is_file_supported_binary_file_pdf(git_manager):
    """PDF files are NOT supported."""
    assert git_manager.is_file_supported("document.pdf") is False


@pytest.mark.unit
def test_is_file_supported_zip_file(git_manager):
    """ZIP files are NOT supported."""
    assert git_manager.is_file_supported("archive.zip") is False


@pytest.mark.unit
def test_is_file_supported_no_extension(git_manager):
    """Files without extension are supported (treated as text)."""
    assert git_manager.is_file_supported("Makefile") is True


# ============================================================================
# filter_supported_files
# ============================================================================


@pytest.mark.unit
def test_filter_supported_files_removes_binary(git_manager):
    """Filters out binary file types from the list."""
    files = ["module.py", "image.png", "app.js", "archive.zip"]
    result = git_manager.filter_supported_files(files)
    assert "module.py" in result
    assert "app.js" in result
    assert "image.png" not in result
    assert "archive.zip" not in result


@pytest.mark.unit
def test_filter_supported_files_empty_list(git_manager):
    """Returns empty list when input is empty."""
    result = git_manager.filter_supported_files([])
    assert result == []


@pytest.mark.unit
def test_filter_supported_files_all_supported(git_manager):
    """Returns all files when all are text-based."""
    files = ["a.py", "b.js", "c.ts", "d.yaml"]
    result = git_manager.filter_supported_files(files)
    assert result == files


# ============================================================================
# get_pr_context
# ============================================================================


@pytest.mark.unit
def test_get_pr_context_returns_dict_structure(git_manager, mock_repo):
    """Returns a dictionary with the expected PR context keys."""
    merge_base = MagicMock()
    mock_repo.merge_base.return_value = [merge_base]
    mock_repo.git.diff.side_effect = ["file.py", "diff content", "diff content"]

    with patch.object(git_manager, "get_base_branch", return_value="main"):
        with patch.object(git_manager, "get_changed_files", return_value=["file.py"]):
            with patch.object(git_manager, "get_full_diff", return_value="full diff"):
                with patch.object(git_manager, "get_file_diff", return_value="file diff"):
                    result = git_manager.get_pr_context("main")

    assert "current_branch" in result
    assert "base_branch" in result
    assert "total_changed_files" in result
    assert "supported_changed_files" in result
    assert "changed_files" in result
    assert "supported_files" in result
    assert "full_diff" in result
    assert "file_diffs" in result


@pytest.mark.unit
def test_get_pr_context_excludes_error_diffs(git_manager, mock_repo):
    """Excludes files whose diffs start with 'Error getting diff'."""
    with patch.object(git_manager, "get_base_branch", return_value="main"):
        with patch.object(git_manager, "get_current_branch", return_value="feature/x"):
            with patch.object(git_manager, "get_changed_files", return_value=["good.py", "bad.py"]):
                with patch.object(git_manager, "get_full_diff", return_value=""):
                    with patch.object(
                        git_manager,
                        "get_file_diff",
                        side_effect=["good diff", "Error getting diff for bad.py: git error"],
                    ):
                        result = git_manager.get_pr_context("main")

    assert "good.py" in result["supported_files"]
    assert "bad.py" not in result["supported_files"]


# ============================================================================
# get_file_diff — auto-detect base_branch and IndexError branches (lines 97, 103-104, 130-131)
# ============================================================================


@pytest.mark.unit
def test_get_file_diff_auto_detects_base_branch(git_manager, mock_repo):
    """Calls get_base_branch when base_branch=None in get_file_diff."""
    merge_base = MagicMock()
    mock_repo.merge_base.return_value = [merge_base]
    mock_repo.git.diff.return_value = "diff content"

    with patch.object(git_manager, "get_base_branch", return_value="main") as mock_get_base:
        git_manager.get_file_diff("file.py", base_branch=None)

    mock_get_base.assert_called_once()


@pytest.mark.unit
def test_get_file_diff_handles_no_merge_base(git_manager, mock_repo):
    """Falls back to base_branch string when IndexError occurs on merge_base in get_file_diff."""
    mock_repo.merge_base.return_value = []
    mock_repo.git.diff.return_value = "diff content"

    with patch.object(git_manager, "get_base_branch", return_value="main"):
        result = git_manager.get_file_diff("file.py", base_branch="main")

    assert isinstance(result, str)


@pytest.mark.unit
def test_get_file_diff_new_file_both_show_calls_fail(git_manager, mock_repo):
    """Returns error string when both show() calls fail for a new file."""
    merge_base = MagicMock()
    mock_repo.merge_base.return_value = [merge_base]
    mock_repo.git.diff.return_value = ""
    # Both show calls raise exceptions
    mock_repo.git.show.side_effect = [Exception("not in base"), Exception("cannot read new file")]

    with patch.object(git_manager, "get_base_branch", return_value="main"):
        result = git_manager.get_file_diff("new_file.py", "main")

    assert "Error: Could not read new file" in result


# ============================================================================
# get_full_diff — auto-detect base_branch and IndexError branches (lines 149, 155-156)
# ============================================================================


@pytest.mark.unit
def test_get_full_diff_auto_detects_base_branch(git_manager, mock_repo):
    """Calls get_base_branch when base_branch=None in get_full_diff."""
    merge_base = MagicMock()
    mock_repo.merge_base.return_value = [merge_base]
    mock_repo.git.diff.return_value = "full diff"

    with patch.object(git_manager, "get_base_branch", return_value="main") as mock_get_base:
        result = git_manager.get_full_diff(base_branch=None)

    mock_get_base.assert_called_once()
    assert result == "full diff"


@pytest.mark.unit
def test_get_full_diff_handles_no_merge_base(git_manager, mock_repo):
    """Falls back to base_branch string when IndexError on merge_base in get_full_diff."""
    mock_repo.merge_base.return_value = []
    mock_repo.git.diff.return_value = "full diff fallback"

    with patch.object(git_manager, "get_base_branch", return_value="main"):
        result = git_manager.get_full_diff(base_branch="main")

    assert result == "full diff fallback"


# ============================================================================
# get_pr_context — auto-detect base_branch (line 238)
# ============================================================================


@pytest.mark.unit
def test_get_pr_context_auto_detects_base_branch(git_manager, mock_repo):
    """Calls get_base_branch when base_branch=None in get_pr_context."""
    with patch.object(git_manager, "get_base_branch", return_value="main") as mock_get_base:
        with patch.object(git_manager, "get_current_branch", return_value="feature/x"):
            with patch.object(git_manager, "get_changed_files", return_value=[]):
                with patch.object(git_manager, "get_full_diff", return_value=""):
                    git_manager.get_pr_context(base_branch=None)

    mock_get_base.assert_called_once()


# ============================================================================
# is_file_supported — additional binary extensions
# ============================================================================


@pytest.mark.unit
def test_is_file_supported_dll_file(git_manager):
    """DLL files are NOT supported."""
    assert git_manager.is_file_supported("library.dll") is False


@pytest.mark.unit
def test_is_file_supported_so_file(git_manager):
    """Shared object files are NOT supported."""
    assert git_manager.is_file_supported("lib.so") is False


@pytest.mark.unit
def test_is_file_supported_mp3_file(git_manager):
    """MP3 files are NOT supported."""
    assert git_manager.is_file_supported("audio.mp3") is False


@pytest.mark.unit
def test_is_file_supported_yaml_file(git_manager):
    """YAML config files are supported (text-based)."""
    assert git_manager.is_file_supported("config.yaml") is True


@pytest.mark.unit
def test_is_file_supported_sql_file(git_manager):
    """SQL files are supported (text-based)."""
    assert git_manager.is_file_supported("schema.sql") is True


# ============================================================================
# get_base_branch — dev fallback and origin/ exclusion
# ============================================================================


@pytest.mark.unit
def test_get_base_branch_falls_back_to_dev(git_manager, mock_repo):
    """Falls back to 'dev' when neither main, master, nor develop exists."""
    dev_ref = MagicMock()
    dev_ref.name = "dev"
    mock_repo.refs = [dev_ref]

    result = git_manager.get_base_branch(default_base="main")

    assert result == "dev"


@pytest.mark.unit
def test_get_base_branch_excludes_origin_refs(git_manager, mock_repo):
    """Branches starting with 'origin/' are excluded from the first-branch fallback."""
    origin_ref = MagicMock()
    origin_ref.name = "origin/main"
    local_ref = MagicMock()
    local_ref.name = "feature/local"
    mock_repo.refs = [origin_ref, local_ref]

    result = git_manager.get_base_branch(default_base="nonexistent")

    # origin/main excluded, feature/local returned
    assert result == "feature/local"
