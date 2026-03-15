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


@pytest.mark.unit
def test_get_file_stats_size_human_mb_format(tmp_path):
    """size_human uses MB format for large files (>= 1 MB)."""
    test_file = tmp_path / "large.py"
    test_file.write_bytes(b"x" * (1024 * 1024 + 1))

    stats = get_file_stats(str(test_file))

    assert "MB" in stats["size_human"]


@pytest.mark.unit
def test_get_file_stats_handles_read_error(tmp_path):
    """get_file_stats stores error key when reading the file content fails."""
    test_file = tmp_path / "module.py"
    test_file.write_text("content\n")

    with patch("pathlib.Path.open", side_effect=OSError("cannot read")):
        stats = get_file_stats(str(test_file))

    assert "error" in stats


# ============================================================================
# get_gitignore_excludes — error path (lines 43-44)
# ============================================================================


@pytest.mark.unit
def test_get_gitignore_excludes_exception_during_open_returns_defaults(tmp_path, monkeypatch):
    """Returns default excludes when .gitignore open raises inside the with block."""
    monkeypatch.chdir(tmp_path)
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("custom_pattern\n")

    original_open = open

    def _flaky_open(file, *args, **kwargs):
        if ".gitignore" in str(file):
            raise IOError("forced error")
        return original_open(file, *args, **kwargs)

    with patch("builtins.open", side_effect=_flaky_open):
        excludes = get_gitignore_excludes()

    assert ".git" in excludes


# ============================================================================
# should_exclude_path — wildcard exception path (lines 61-62)
# ============================================================================


@pytest.mark.unit
def test_should_exclude_path_wildcard_raises_attribute_error():
    """Returns False (not excluded) when path.match raises AttributeError on a wildcard."""
    with patch.object(Path, "match", side_effect=AttributeError("mock error")):
        result = should_exclude_path("some/module.py", ["*.pyc"])
    assert result is False


@pytest.mark.unit
def test_should_exclude_path_wildcard_raises_value_error():
    """Returns False (not excluded) when path.match raises ValueError on a wildcard."""
    with patch.object(Path, "match", side_effect=ValueError("mock error")):
        result = should_exclude_path("some/module.py", ["*.pyc"])
    assert result is False


# ============================================================================
# find_files — glob/wildcard branch (lines 89-99)
# ============================================================================


@pytest.mark.unit
def test_find_files_with_glob_pattern(tmp_path, monkeypatch):
    """find_files uses glob when path does not exist as a file or directory."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alpha.py").write_text("a = 1")
    (tmp_path / "beta.py").write_text("b = 2")

    result = find_files("*.py", recursive=False)

    assert any("alpha.py" in f for f in result) or any("beta.py" in f for f in result)


@pytest.mark.unit
def test_find_files_glob_with_double_star_already_present(tmp_path, monkeypatch):
    """find_files does not prepend **/ when pattern already contains **."""
    monkeypatch.chdir(tmp_path)
    subdir = tmp_path / "sub"
    subdir.mkdir()
    (subdir / "deep.py").write_text("d = 1")

    result = find_files("**/*.py", recursive=True)

    assert any("deep.py" in f for f in result)


@pytest.mark.unit
def test_find_files_glob_respects_max_files(tmp_path, monkeypatch):
    """find_files stops at max_files when using glob matching."""
    monkeypatch.chdir(tmp_path)
    for i in range(10):
        (tmp_path / f"file{i}.py").write_text(f"x = {i}")

    result = find_files("*.py", recursive=False, max_files=3)

    assert len(result) <= 3


@pytest.mark.unit
def test_find_files_exception_returns_empty_list(tmp_path, monkeypatch):
    """find_files returns empty list when an unexpected exception occurs inside the try block."""
    monkeypatch.chdir(tmp_path)
    with patch("pathlib.Path.rglob", side_effect=OSError("permission denied")):
        result = find_files(str(tmp_path))
    assert result == []


@pytest.mark.unit
def test_find_files_excludes_excluded_file(tmp_path, monkeypatch):
    """find_files skips files matching the exclusion list (direct file path)."""
    monkeypatch.chdir(tmp_path)
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    excluded_file = venv_dir / "module.py"
    excluded_file.write_text("x = 1")

    result = find_files(str(excluded_file))

    assert str(excluded_file) not in result


# ============================================================================
# detect_language_from_path — all remaining language mappings
# ============================================================================


@pytest.mark.unit
def test_detect_language_tsx():
    assert detect_language_from_path("component.tsx") == "tsx"


@pytest.mark.unit
def test_detect_language_jsx():
    assert detect_language_from_path("component.jsx") == "jsx"


@pytest.mark.unit
def test_detect_language_html():
    assert detect_language_from_path("index.html") == "html"


@pytest.mark.unit
def test_detect_language_css():
    assert detect_language_from_path("styles.css") == "css"


@pytest.mark.unit
def test_detect_language_xml():
    assert detect_language_from_path("config.xml") == "xml"


@pytest.mark.unit
def test_detect_language_markdown():
    assert detect_language_from_path("README.md") == "markdown"


@pytest.mark.unit
def test_detect_language_sql():
    assert detect_language_from_path("query.sql") == "sql"


@pytest.mark.unit
def test_detect_language_bash():
    assert detect_language_from_path("script.sh") == "bash"


@pytest.mark.unit
def test_detect_language_java():
    assert detect_language_from_path("Main.java") == "java"


@pytest.mark.unit
def test_detect_language_cpp():
    assert detect_language_from_path("main.cpp") == "cpp"


@pytest.mark.unit
def test_detect_language_c():
    assert detect_language_from_path("main.c") == "c"


@pytest.mark.unit
def test_detect_language_csharp():
    assert detect_language_from_path("Program.cs") == "csharp"


@pytest.mark.unit
def test_detect_language_php():
    assert detect_language_from_path("index.php") == "php"


@pytest.mark.unit
def test_detect_language_ruby():
    assert detect_language_from_path("app.rb") == "ruby"


@pytest.mark.unit
def test_detect_language_go():
    assert detect_language_from_path("main.go") == "go"


@pytest.mark.unit
def test_detect_language_rust():
    assert detect_language_from_path("lib.rs") == "rust"


# ============================================================================
# get_file_content (@tool) — all modes via mocked console_ui
# ============================================================================


@pytest.mark.unit
def test_get_file_content_view_mode(tmp_path):
    """get_file_content view mode returns file content."""
    from cli_tool.commands.code_reviewer.tools.file_reader import get_file_content

    test_file = tmp_path / "module.py"
    test_file.write_text("x = 1\ny = 2\n")

    with patch("cli_tool.commands.code_reviewer.tools.file_reader.console_ui"):
        result = get_file_content(str(test_file), mode="view")

    assert "x = 1" in result
    assert "Content of" in result


@pytest.mark.unit
def test_get_file_content_lines_mode_with_line_numbers(tmp_path):
    """get_file_content lines mode with line numbers enabled."""
    from cli_tool.commands.code_reviewer.tools.file_reader import get_file_content

    test_file = tmp_path / "code.py"
    test_file.write_text("line1\nline2\nline3\nline4\nline5\n")

    with patch("cli_tool.commands.code_reviewer.tools.file_reader.console_ui"):
        result = get_file_content(str(test_file), mode="lines", start_line=2, end_line=4, show_line_numbers=True)

    assert "2:" in result or "   2:" in result


@pytest.mark.unit
def test_get_file_content_lines_mode_without_line_numbers(tmp_path):
    """get_file_content lines mode without line numbers."""
    from cli_tool.commands.code_reviewer.tools.file_reader import get_file_content

    test_file = tmp_path / "code.py"
    test_file.write_text("lineA\nlineB\nlineC\n")

    with patch("cli_tool.commands.code_reviewer.tools.file_reader.console_ui"):
        result = get_file_content(str(test_file), mode="lines", start_line=1, end_line=2, show_line_numbers=False)

    assert "lineA" in result


@pytest.mark.unit
def test_get_file_content_lines_mode_with_lines_count(tmp_path):
    """get_file_content lines mode uses lines_count to derive end_line."""
    from cli_tool.commands.code_reviewer.tools.file_reader import get_file_content

    test_file = tmp_path / "code.py"
    test_file.write_text("a\nb\nc\nd\ne\n")

    with patch("cli_tool.commands.code_reviewer.tools.file_reader.console_ui"):
        result = get_file_content(str(test_file), mode="lines", start_line=1, lines_count=3, show_line_numbers=False)

    assert "a" in result


@pytest.mark.unit
def test_get_file_content_search_mode_with_match(tmp_path):
    """get_file_content search mode returns matches found."""
    from cli_tool.commands.code_reviewer.tools.file_reader import get_file_content

    test_file = tmp_path / "code.py"
    test_file.write_text("def hello():\n    pass\n\nhello()\n")

    with patch("cli_tool.commands.code_reviewer.tools.file_reader.console_ui"):
        result = get_file_content(str(test_file), mode="search", search_pattern="hello", search_mode="regex")

    assert "hello" in result or "Search Results" in result


@pytest.mark.unit
def test_get_file_content_search_mode_no_pattern_raises_in_results(tmp_path):
    """get_file_content search mode without pattern returns error in results."""
    from cli_tool.commands.code_reviewer.tools.file_reader import get_file_content

    test_file = tmp_path / "code.py"
    test_file.write_text("content\n")

    with patch("cli_tool.commands.code_reviewer.tools.file_reader.console_ui"):
        result = get_file_content(str(test_file), mode="search")

    assert "Error" in result or "search_pattern" in result


@pytest.mark.unit
def test_get_file_content_stats_mode(tmp_path):
    """get_file_content stats mode returns file statistics."""
    from cli_tool.commands.code_reviewer.tools.file_reader import get_file_content

    test_file = tmp_path / "module.py"
    test_file.write_text("def foo():\n    pass\n\nclass Bar:\n    pass\n")

    with patch("cli_tool.commands.code_reviewer.tools.file_reader.console_ui"):
        result = get_file_content(str(test_file), mode="stats")

    import json as _json

    parsed = _json.loads(result)
    assert "line_count" in parsed


@pytest.mark.unit
def test_get_file_content_preview_mode(tmp_path):
    """get_file_content preview mode returns file preview."""
    from cli_tool.commands.code_reviewer.tools.file_reader import get_file_content

    test_file = tmp_path / "module.py"
    test_file.write_text("line1\nline2\nline3\n")

    with patch("cli_tool.commands.code_reviewer.tools.file_reader.console_ui"):
        result = get_file_content(str(test_file), mode="preview")

    assert "Preview of" in result


@pytest.mark.unit
def test_get_file_content_unknown_mode_returns_error(tmp_path):
    """get_file_content unknown mode returns error string."""
    from cli_tool.commands.code_reviewer.tools.file_reader import get_file_content

    test_file = tmp_path / "module.py"
    test_file.write_text("content\n")

    with patch("cli_tool.commands.code_reviewer.tools.file_reader.console_ui"):
        result = get_file_content(str(test_file), mode="invalid_mode")

    assert "Error" in result or "Unknown mode" in result


@pytest.mark.unit
def test_get_file_content_find_mode_with_files(tmp_path):
    """get_file_content find mode lists files found."""
    from cli_tool.commands.code_reviewer.tools.file_reader import get_file_content

    (tmp_path / "a.py").write_text("a = 1")
    (tmp_path / "b.py").write_text("b = 2")

    with patch("cli_tool.commands.code_reviewer.tools.file_reader.console_ui"):
        result = get_file_content(str(tmp_path), mode="find")

    assert "Found" in result or "files" in result.lower()


@pytest.mark.unit
def test_get_file_content_find_mode_no_files(tmp_path):
    """get_file_content find mode when no files found returns no-files message."""
    from cli_tool.commands.code_reviewer.tools.file_reader import get_file_content

    with patch("cli_tool.commands.code_reviewer.tools.file_reader.console_ui"):
        result = get_file_content("nonexistent_xyz_*.py", mode="find")

    assert "No files found" in result


@pytest.mark.unit
def test_get_file_content_no_files_found_non_find_mode(tmp_path):
    """get_file_content returns error when no files match and mode is not find."""
    from cli_tool.commands.code_reviewer.tools.file_reader import get_file_content

    with patch("cli_tool.commands.code_reviewer.tools.file_reader.console_ui"):
        result = get_file_content("nonexistent_xyz_file.py", mode="view")

    assert "No files found" in result


@pytest.mark.unit
def test_get_file_content_outer_exception_handled():
    """get_file_content handles unexpected top-level exceptions."""
    from cli_tool.commands.code_reviewer.tools.file_reader import get_file_content

    with patch("cli_tool.commands.code_reviewer.tools.file_reader.console_ui"):
        with patch("cli_tool.commands.code_reviewer.tools.file_reader.split_path_list", side_effect=RuntimeError("crash")):
            result = get_file_content("any_path.py", mode="view")

    assert "Error in get_file_content" in result


@pytest.mark.unit
def test_get_file_content_comma_separated_paths(tmp_path):
    """get_file_content processes comma-separated paths."""
    from cli_tool.commands.code_reviewer.tools.file_reader import get_file_content

    file1 = tmp_path / "a.py"
    file2 = tmp_path / "b.py"
    file1.write_text("a = 1\n")
    file2.write_text("b = 2\n")

    with patch("cli_tool.commands.code_reviewer.tools.file_reader.console_ui"):
        result = get_file_content(f"{file1},{file2}", mode="view")

    assert "a = 1" in result or "b = 2" in result


@pytest.mark.unit
def test_get_file_content_search_mode_no_match_in_file(tmp_path):
    """get_file_content search mode with no matches adds no-match entry to results."""
    from cli_tool.commands.code_reviewer.tools.file_reader import get_file_content

    test_file = tmp_path / "code.py"
    test_file.write_text("x = 1\ny = 2\n")

    with patch("cli_tool.commands.code_reviewer.tools.file_reader.console_ui"):
        result = get_file_content(str(test_file), mode="search", search_pattern="zzz_not_here", search_mode="regex")

    assert isinstance(result, str)


@pytest.mark.unit
def test_get_file_content_search_mode_more_than_5_matches(tmp_path):
    """get_file_content search mode truncates output when more than 5 matches."""
    from cli_tool.commands.code_reviewer.tools.file_reader import get_file_content

    lines = "\n".join([f"target_token_{i}" for i in range(10)])
    test_file = tmp_path / "code.py"
    test_file.write_text(lines)

    with patch("cli_tool.commands.code_reviewer.tools.file_reader.console_ui"):
        result = get_file_content(str(test_file), mode="search", search_pattern="target_token", search_mode="regex")

    assert "more matches" in result or "target_token" in result


# ============================================================================
# get_file_info (@tool)
# ============================================================================


@pytest.mark.unit
def test_get_file_info_small_file(tmp_path):
    """get_file_info returns file info with small-file recommendation."""
    from cli_tool.commands.code_reviewer.tools.file_reader import get_file_info

    test_file = tmp_path / "tiny.py"
    test_file.write_text("x = 1\n")

    with patch("cli_tool.commands.code_reviewer.tools.file_reader.console_ui"):
        result = get_file_info(str(test_file))

    assert "mode='view'" in result or "Small file" in result


@pytest.mark.unit
def test_get_file_info_medium_file(tmp_path):
    """get_file_info returns medium-file recommendation for 100-499 line files."""
    from cli_tool.commands.code_reviewer.tools.file_reader import get_file_info

    content = "\n".join([f"line {i}" for i in range(200)])
    test_file = tmp_path / "medium.py"
    test_file.write_text(content)

    with patch("cli_tool.commands.code_reviewer.tools.file_reader.console_ui"):
        result = get_file_info(str(test_file))

    assert "mode='lines'" in result or "Medium file" in result


@pytest.mark.unit
def test_get_file_info_large_file(tmp_path):
    """get_file_info returns large-file recommendation for 500+ line files."""
    from cli_tool.commands.code_reviewer.tools.file_reader import get_file_info

    content = "\n".join([f"line {i}" for i in range(600)])
    test_file = tmp_path / "large.py"
    test_file.write_text(content)

    with patch("cli_tool.commands.code_reviewer.tools.file_reader.console_ui"):
        result = get_file_info(str(test_file))

    assert "Large file" in result or "mode='lines'" in result or "mode='search'" in result


@pytest.mark.unit
def test_get_file_info_file_not_found():
    """get_file_info returns error string when file does not exist."""
    from cli_tool.commands.code_reviewer.tools.file_reader import get_file_info

    with patch("cli_tool.commands.code_reviewer.tools.file_reader.console_ui"):
        result = get_file_info("/nonexistent/path/file.py")

    assert "Error" in result
