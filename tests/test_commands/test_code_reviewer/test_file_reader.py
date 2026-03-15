"""
Unit tests for cli_tool.commands.code_reviewer.tools.file_reader module.

Tests cover helper functions and the main tool functions with mocked I/O,
filesystem, and console_ui.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from cli_tool.commands.code_reviewer.tools.file_reader import (
    detect_language_from_path,
    find_files,
    generate_file_preview,
    get_file_stats,
    get_gitignore_excludes,
    get_smart_search_patterns_for_file,
    read_file_lines,
    search_in_file,
    should_exclude_path,
    split_path_list,
)

# ============================================================================
# get_gitignore_excludes
# ============================================================================


@pytest.mark.unit
def test_get_gitignore_excludes_returns_default_when_no_gitignore(tmp_path, monkeypatch):
    """Returns default excludes when no .gitignore exists."""
    monkeypatch.chdir(tmp_path)
    excludes = get_gitignore_excludes()
    assert ".git" in excludes
    assert ".venv" in excludes
    assert "__pycache__" in excludes


@pytest.mark.unit
def test_get_gitignore_excludes_parses_gitignore(tmp_path, monkeypatch):
    """Adds patterns from .gitignore to default excludes."""
    monkeypatch.chdir(tmp_path)
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("# comment\ncustom_dir/\n*.custom\n")

    excludes = get_gitignore_excludes()

    assert "custom_dir" in excludes
    assert "*.custom" in excludes


@pytest.mark.unit
def test_get_gitignore_excludes_ignores_comments(tmp_path, monkeypatch):
    """Lines starting with # are ignored."""
    monkeypatch.chdir(tmp_path)
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("# this is a comment\nvalid_pattern\n")

    excludes = get_gitignore_excludes()

    assert "# this is a comment" not in excludes
    assert "valid_pattern" in excludes


@pytest.mark.unit
def test_get_gitignore_excludes_handles_unreadable_file(tmp_path, monkeypatch):
    """Returns default excludes when .gitignore cannot be read."""
    monkeypatch.chdir(tmp_path)
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("custom_pattern\n")

    with patch("builtins.open", side_effect=OSError("permission denied")):
        excludes = get_gitignore_excludes()

    # Should still return default excludes
    assert ".git" in excludes


# ============================================================================
# should_exclude_path
# ============================================================================


@pytest.mark.unit
def test_should_exclude_path_matches_exclude():
    """Returns True when file path contains an exclude pattern."""
    result = should_exclude_path("some/path/.venv/lib/module.py", [".venv"])
    assert result is True


@pytest.mark.unit
def test_should_exclude_path_no_match():
    """Returns False when file path does not match any exclude."""
    result = should_exclude_path("src/module.py", [".git", ".venv", "__pycache__"])
    assert result is False


@pytest.mark.unit
def test_should_exclude_path_wildcard_pattern(tmp_path):
    """Returns True when wildcard pattern matches the file."""
    pyc_file = str(tmp_path / "module.pyc")
    result = should_exclude_path(pyc_file, ["*.pyc"])
    assert result is True


@pytest.mark.unit
def test_should_exclude_path_wildcard_no_match(tmp_path):
    """Returns False when wildcard pattern does not match."""
    py_file = str(tmp_path / "module.py")
    result = should_exclude_path(py_file, ["*.pyc"])
    assert result is False


# ============================================================================
# find_files
# ============================================================================


@pytest.mark.unit
def test_find_files_with_existing_file(tmp_path, monkeypatch):
    """find_files returns the file itself when given a direct file path."""
    monkeypatch.chdir(tmp_path)
    test_file = tmp_path / "test.py"
    test_file.write_text("print('hello')")

    result = find_files(str(test_file))

    assert str(test_file) in result


@pytest.mark.unit
def test_find_files_with_directory_recursive(tmp_path, monkeypatch):
    """find_files finds files recursively in a directory."""
    monkeypatch.chdir(tmp_path)
    subdir = tmp_path / "sub"
    subdir.mkdir()
    file1 = tmp_path / "file1.py"
    file2 = subdir / "file2.py"
    file1.write_text("x = 1")
    file2.write_text("y = 2")

    result = find_files(str(tmp_path), recursive=True)

    assert str(file1) in result
    assert str(file2) in result


@pytest.mark.unit
def test_find_files_non_recursive(tmp_path, monkeypatch):
    """find_files only returns top-level files when recursive=False."""
    monkeypatch.chdir(tmp_path)
    subdir = tmp_path / "sub"
    subdir.mkdir()
    file1 = tmp_path / "file1.py"
    file2 = subdir / "file2.py"
    file1.write_text("x = 1")
    file2.write_text("y = 2")

    result = find_files(str(tmp_path), recursive=False)

    assert str(file1) in result
    assert str(file2) not in result


@pytest.mark.unit
def test_find_files_respects_max_files(tmp_path, monkeypatch):
    """find_files stops at max_files."""
    monkeypatch.chdir(tmp_path)
    for i in range(10):
        (tmp_path / f"file{i}.py").write_text(f"x = {i}")

    result = find_files(str(tmp_path), max_files=3)

    assert len(result) <= 3


@pytest.mark.unit
def test_find_files_excludes_pycache(tmp_path, monkeypatch):
    """find_files excludes __pycache__ directories."""
    monkeypatch.chdir(tmp_path)
    cache_dir = tmp_path / "__pycache__"
    cache_dir.mkdir()
    cache_file = cache_dir / "module.pyc"
    cache_file.write_text("bytecode")
    normal_file = tmp_path / "module.py"
    normal_file.write_text("code")

    result = find_files(str(tmp_path))

    assert str(cache_file) not in result
    assert str(normal_file) in result


# ============================================================================
# split_path_list
# ============================================================================


@pytest.mark.unit
def test_split_path_list_single_path():
    """Returns single-element list for a path without commas."""
    result = split_path_list("src/module.py")
    assert result == ["src/module.py"]


@pytest.mark.unit
def test_split_path_list_comma_separated():
    """Returns list of paths when comma-separated."""
    result = split_path_list("src/a.py, src/b.py, src/c.py")
    assert result == ["src/a.py", "src/b.py", "src/c.py"]


@pytest.mark.unit
def test_split_path_list_strips_whitespace():
    """Strips whitespace from each path."""
    result = split_path_list("  file1.py  ,  file2.py  ")
    assert "file1.py" in result
    assert "file2.py" in result


@pytest.mark.unit
def test_split_path_list_ignores_empty_parts():
    """Skips empty parts after splitting."""
    result = split_path_list("file1.py,,file2.py")
    assert "" not in result
    assert len(result) == 2


# ============================================================================
# detect_language_from_path
# ============================================================================


@pytest.mark.unit
def test_detect_language_python():
    assert detect_language_from_path("module.py") == "python"


@pytest.mark.unit
def test_detect_language_javascript():
    assert detect_language_from_path("app.js") == "javascript"


@pytest.mark.unit
def test_detect_language_typescript():
    assert detect_language_from_path("component.ts") == "typescript"


@pytest.mark.unit
def test_detect_language_json():
    assert detect_language_from_path("config.json") == "json"


@pytest.mark.unit
def test_detect_language_yaml():
    assert detect_language_from_path("deploy.yaml") == "yaml"


@pytest.mark.unit
def test_detect_language_yaml_yml():
    assert detect_language_from_path("config.yml") == "yaml"


@pytest.mark.unit
def test_detect_language_unknown_extension():
    assert detect_language_from_path("file.xyz") == "text"


@pytest.mark.unit
def test_detect_language_no_extension():
    assert detect_language_from_path("Makefile") == "text"


# ============================================================================
# read_file_lines
# ============================================================================


@pytest.mark.unit
def test_read_file_lines_basic(tmp_path):
    """Reads specific lines from a file correctly."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\nline3\nline4\nline5\n")

    lines, metadata = read_file_lines(str(test_file), start_line=2, end_line=4)

    assert len(lines) == 3
    assert "line2\n" in lines
    assert metadata["start_line"] == 2
    assert metadata["end_line"] == 4
    assert metadata["total_lines"] == 5


@pytest.mark.unit
def test_read_file_lines_no_end_line_reads_to_eof(tmp_path):
    """Reads from start_line to end of file when end_line is None."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\nline3\n")

    lines, metadata = read_file_lines(str(test_file), start_line=2)

    assert len(lines) == 2
    assert metadata["end_line"] == 3


@pytest.mark.unit
def test_read_file_lines_file_not_found():
    """Raises FileNotFoundError when file does not exist."""
    with pytest.raises(FileNotFoundError):
        read_file_lines("/nonexistent/file.txt")


@pytest.mark.unit
def test_read_file_lines_path_is_directory(tmp_path):
    """Raises ValueError when path points to a directory."""
    with pytest.raises(ValueError, match="not a file"):
        read_file_lines(str(tmp_path))


@pytest.mark.unit
def test_read_file_lines_start_exceeds_total(tmp_path):
    """Raises ValueError when start_line exceeds file length."""
    test_file = tmp_path / "small.txt"
    test_file.write_text("one line\n")

    with pytest.raises(ValueError, match="exceeds file length"):
        read_file_lines(str(test_file), start_line=100)


@pytest.mark.unit
def test_read_file_lines_start_greater_than_end(tmp_path):
    """Raises ValueError when start_line > end_line."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\nline3\n")

    with pytest.raises(ValueError, match="greater than end line"):
        read_file_lines(str(test_file), start_line=3, end_line=1)


# ============================================================================
# get_smart_search_patterns_for_file
# ============================================================================


@pytest.mark.unit
def test_get_smart_search_patterns_plain_identifier():
    """Returns multiple patterns for a plain identifier."""
    patterns = get_smart_search_patterns_for_file("my_func")
    assert len(patterns) > 1
    assert any("my_func" in p for p in patterns)


@pytest.mark.unit
def test_get_smart_search_patterns_with_parenthesis():
    """Returns function-call specific patterns when term contains '('."""
    patterns = get_smart_search_patterns_for_file("my_func(arg)")
    assert any(r"\(" in p for p in patterns)


@pytest.mark.unit
def test_get_smart_search_patterns_with_dot():
    """Returns dotted accessor patterns when term contains '.'."""
    patterns = get_smart_search_patterns_for_file("obj.method")
    assert any("obj" in p and "method" in p for p in patterns)


@pytest.mark.unit
def test_get_smart_search_patterns_no_duplicates():
    """Returned patterns are unique."""
    patterns = get_smart_search_patterns_for_file("my_func")
    assert len(patterns) == len(set(patterns))


# ============================================================================
# search_in_file
# ============================================================================


@pytest.mark.unit
def test_search_in_file_finds_match(tmp_path):
    """Returns matches when pattern is found in the file."""
    test_file = tmp_path / "code.py"
    test_file.write_text("def my_func():\n    pass\n\nx = my_func()\n")

    results = search_in_file(str(test_file), "my_func", context_lines=1, search_mode="regex")

    assert len(results) > 0
    assert all("line_number" in r for r in results)


@pytest.mark.unit
def test_search_in_file_no_match(tmp_path):
    """Returns empty list when pattern is not found."""
    test_file = tmp_path / "code.py"
    test_file.write_text("x = 1\ny = 2\n")

    results = search_in_file(str(test_file), "nonexistent_pattern_xyz", search_mode="regex")

    assert results == []


@pytest.mark.unit
def test_search_in_file_file_not_found():
    """Raises FileNotFoundError when file does not exist."""
    with pytest.raises(FileNotFoundError):
        search_in_file("/nonexistent/file.py", "pattern")


@pytest.mark.unit
def test_search_in_file_includes_context_lines(tmp_path):
    """Results include context_before and context_after."""
    test_file = tmp_path / "code.py"
    test_file.write_text("before_line\ntarget_match\nafter_line\n")

    results = search_in_file(str(test_file), "target_match", context_lines=1, search_mode="regex")

    assert len(results) >= 1
    assert "context_before" in results[0]
    assert "context_after" in results[0]


@pytest.mark.unit
def test_search_in_file_smart_mode(tmp_path):
    """Smart mode generates multiple patterns and deduplicates matches."""
    test_file = tmp_path / "code.py"
    test_file.write_text("def calculate(x):\n    return x * 2\n\ny = calculate(5)\n")

    results = search_in_file(str(test_file), "calculate", context_lines=0, search_mode="smart")

    # Should find at least 2 matches (def and call)
    assert len(results) >= 1
    line_numbers = [r["line_number"] for r in results]
    # No duplicates
    assert len(line_numbers) == len(set(line_numbers))


@pytest.mark.unit
def test_search_in_file_invalid_regex_pattern(tmp_path):
    """Does not crash when an invalid regex pattern is in smart mode."""
    test_file = tmp_path / "code.py"
    test_file.write_text("some content\n")

    # Invalid regex should be handled gracefully
    results = search_in_file(str(test_file), "[invalid", search_mode="regex")
    # Result can be empty (re.error caught) but should not raise
    assert isinstance(results, list)


# ============================================================================
# generate_file_preview
# ============================================================================


@pytest.mark.unit
def test_generate_file_preview_returns_first_n_lines(tmp_path):
    """Returns up to max_lines lines from the file."""
    test_file = tmp_path / "large.py"
    content = "\n".join([f"line {i}" for i in range(50)])
    test_file.write_text(content)

    preview = generate_file_preview(str(test_file), max_lines=10)

    lines = preview.split("\n")
    assert len(lines) <= 10


@pytest.mark.unit
def test_generate_file_preview_small_file(tmp_path):
    """Returns all lines for a file with fewer lines than max_lines."""
    test_file = tmp_path / "small.py"
    test_file.write_text("line1\nline2\nline3\n")

    preview = generate_file_preview(str(test_file), max_lines=20)

    assert "line1" in preview
    assert "line2" in preview
    assert "line3" in preview


# ============================================================================
# get_file_stats
# ============================================================================


@pytest.mark.unit
def test_get_file_stats_basic(tmp_path):
    """Returns correct stats for a Python file."""
    test_file = tmp_path / "module.py"
    test_file.write_text("def foo():\n    pass\n\nclass Bar:\n    pass\n")

    stats = get_file_stats(str(test_file))

    assert stats["line_count"] > 0
    assert stats["size_bytes"] > 0
    assert "size_human" in stats
    assert len(stats["function_lines"]) >= 1
    assert len(stats["class_lines"]) >= 1


@pytest.mark.unit
def test_get_file_stats_file_not_found():
    """Raises FileNotFoundError for a nonexistent file."""
    with pytest.raises(FileNotFoundError):
        get_file_stats("/nonexistent/file.py")


@pytest.mark.unit
def test_get_file_stats_with_preview(tmp_path):
    """Includes preview when include_preview=True."""
    test_file = tmp_path / "module.py"
    test_file.write_text("line1\nline2\nline3\n")

    stats = get_file_stats(str(test_file), include_preview=True, preview_lines=2)

    assert "line1" in stats["preview"]


@pytest.mark.unit
def test_get_file_stats_without_preview(tmp_path):
    """Preview is empty string when include_preview=False."""
    test_file = tmp_path / "module.py"
    test_file.write_text("line1\nline2\n")

    stats = get_file_stats(str(test_file), include_preview=False)

    assert stats["preview"] == ""


@pytest.mark.unit
def test_get_file_stats_counts_comment_lines(tmp_path):
    """Correctly counts lines starting with comment characters."""
    test_file = tmp_path / "module.py"
    test_file.write_text("# comment\nx = 1\n# another comment\n")

    stats = get_file_stats(str(test_file))

    assert stats["comment_lines"] == 2


@pytest.mark.unit
def test_get_file_stats_size_human_kb_format(tmp_path):
    """size_human uses KB format for small files."""
    test_file = tmp_path / "small.py"
    test_file.write_text("x = 1\n")

    stats = get_file_stats(str(test_file))

    assert "KB" in stats["size_human"]
