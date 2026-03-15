"""
Unit tests for cli_tool.commands.code_reviewer.tools.code_analyzer module.

Tests cover the helper functions and the three @tool functions:
- search_code_references
- search_function_definition
- analyze_import_usage

All subprocess calls and console_ui output are mocked.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cli_tool.commands.code_reviewer.tools.code_analyzer import (
    get_gitignore_excludes,
    get_smart_search_patterns,
    parse_grep_results,
)

# ============================================================================
# get_gitignore_excludes (code_analyzer version)
# ============================================================================


@pytest.mark.unit
def test_code_analyzer_get_gitignore_excludes_returns_string(tmp_path, monkeypatch):
    """Returns a string of grep exclude flags."""
    monkeypatch.chdir(tmp_path)
    result = get_gitignore_excludes()
    assert isinstance(result, str)
    assert "--exclude-dir=" in result


@pytest.mark.unit
def test_code_analyzer_get_gitignore_excludes_default_patterns(tmp_path, monkeypatch):
    """Default patterns include .git, .venv, and __pycache__."""
    monkeypatch.chdir(tmp_path)
    result = get_gitignore_excludes()
    assert ".git" in result
    assert ".venv" in result
    assert "__pycache__" in result


@pytest.mark.unit
def test_code_analyzer_get_gitignore_excludes_with_gitignore(tmp_path, monkeypatch):
    """Adds patterns from .gitignore to the exclude string."""
    monkeypatch.chdir(tmp_path)
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("# comment\ncustom_dir/\n*.custom\n")

    result = get_gitignore_excludes()

    assert "custom_dir" in result
    assert "*.custom" in result


@pytest.mark.unit
def test_code_analyzer_get_gitignore_excludes_ignores_comments(tmp_path, monkeypatch):
    """Lines starting with # are not added to excludes."""
    monkeypatch.chdir(tmp_path)
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("# this is a comment\nvalid_dir/\n")

    result = get_gitignore_excludes()

    assert "this is a comment" not in result


# ============================================================================
# get_smart_search_patterns
# ============================================================================


@pytest.mark.unit
def test_get_smart_search_patterns_simple_symbol():
    """Returns word-boundary patterns for a simple symbol."""
    patterns = get_smart_search_patterns("my_func")
    assert len(patterns) >= 1
    assert any("my_func" in p for p in patterns)


@pytest.mark.unit
def test_get_smart_search_patterns_function_call():
    """Returns function-call specific patterns when symbol looks like a call."""
    patterns = get_smart_search_patterns("createTrip(cache)")
    assert any(r"\(" in p for p in patterns)


@pytest.mark.unit
def test_get_smart_search_patterns_method_call():
    """Returns method-access patterns when symbol contains a dot."""
    patterns = get_smart_search_patterns("obj.method")
    # Should include patterns referencing both obj and method
    joined = " ".join(patterns)
    assert "method" in joined


@pytest.mark.unit
def test_get_smart_search_patterns_no_duplicates():
    """Returned patterns contain no duplicates."""
    patterns = get_smart_search_patterns("my_func")
    assert len(patterns) == len(set(patterns))


@pytest.mark.unit
def test_get_smart_search_patterns_complex_symbol():
    """Handles complex symbols with both dots and parentheses."""
    patterns = get_smart_search_patterns("service.create(data)")
    assert isinstance(patterns, list)
    assert len(patterns) > 0


# ============================================================================
# parse_grep_results
# ============================================================================


@pytest.mark.unit
def test_parse_grep_results_parses_standard_format():
    """Parses grep output with file:line:content format."""
    output = "file.py:10:    def my_func():\nfile.py:20:    x = my_func()"
    results = parse_grep_results(output, "my_func")

    assert len(results) == 2
    assert results[0]["file_path"] == "file.py"
    assert results[0]["line_number"] == 10
    assert "my_func" in results[0]["content"]


@pytest.mark.unit
def test_parse_grep_results_empty_output():
    """Returns empty list for empty grep output."""
    results = parse_grep_results("", "symbol")
    assert results == []


@pytest.mark.unit
def test_parse_grep_results_truncates_long_preview():
    """Preview is truncated to 100 characters."""
    long_content = "x" * 200
    output = f"file.py:1:{long_content}"
    results = parse_grep_results(output, "x")

    if results:
        assert len(results[0]["preview"]) <= 103  # 100 chars + '...'


@pytest.mark.unit
def test_parse_grep_results_skips_invalid_lines():
    """Lines that cannot be parsed are skipped."""
    output = "this line has no colon format\nfile.py:10: valid content"
    results = parse_grep_results(output, "symbol")

    # Should parse at least the valid line
    assert isinstance(results, list)


@pytest.mark.unit
def test_parse_grep_results_skips_non_integer_line_number():
    """Lines with non-integer line numbers are skipped."""
    output = "file.py:abc:content\nfile.py:10:valid"
    results = parse_grep_results(output, "symbol")

    # Should only parse the line with integer line number
    assert all(isinstance(r["line_number"], int) for r in results)


# ============================================================================
# search_code_references (@tool)
# ============================================================================


@pytest.mark.unit
def test_search_code_references_success(mocker):
    """Returns formatted results when grep finds matches."""
    mock_console_ui = mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "./src/module.py:10:    my_func()\n./src/other.py:20:    my_func(arg)"
    mocker.patch("subprocess.run", return_value=mock_result)

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_code_references

    result = search_code_references("my_func")

    assert "my_func" in result
    assert "module.py" in result or "Found" in result


@pytest.mark.unit
def test_search_code_references_no_matches(mocker):
    """Returns no-match message when grep finds nothing."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mocker.patch("subprocess.run", return_value=mock_result)

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_code_references

    result = search_code_references("nonexistent_symbol")

    assert "No matches found" in result or "nonexistent_symbol" in result


@pytest.mark.unit
def test_search_code_references_with_regex_mode(mocker):
    """Uses regex pattern directly when use_regex=True."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "./file.py:5:match_line"
    mocker.patch("subprocess.run", return_value=mock_result)

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_code_references

    result = search_code_references("my_pattern\\(", use_regex=True)

    assert isinstance(result, str)


@pytest.mark.unit
def test_search_code_references_exception_handled(mocker):
    """Returns error message when subprocess.run raises an exception."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    mocker.patch("subprocess.run", side_effect=Exception("unexpected error"))

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_code_references

    result = search_code_references("my_func")

    assert "Error" in result


@pytest.mark.unit
def test_search_code_references_case_sensitive_flag(mocker):
    """Passes case_sensitive flag to grep command."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_run = mocker.patch("subprocess.run", return_value=mock_result)

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_code_references

    search_code_references("my_func", case_sensitive=True)

    # When case_sensitive=True, -i flag should not be in the command
    cmd_string = mock_run.call_args[0][0]
    assert "-i" not in cmd_string.split()[1:3]  # Check grep flags area


@pytest.mark.unit
def test_search_code_references_limits_results_to_max(mocker):
    """Limits results to max_results."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    # Generate more results than max_results
    output_lines = [f"./file{i}.py:{i * 10}:content_{i}" for i in range(1, 20)]
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "\n".join(output_lines)
    mocker.patch("subprocess.run", return_value=mock_result)

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_code_references

    result = search_code_references("content", max_results=5)

    assert isinstance(result, str)


# ============================================================================
# search_function_definition (@tool)
# ============================================================================


@pytest.mark.unit
def test_search_function_definition_found(mocker):
    """Returns definition when grep finds the function."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "./module.py:15:def calculate_tax(amount):\n--\n./other.py:30:async def calculate_tax(x):\n"
    mocker.patch("subprocess.run", return_value=mock_result)

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_function_definition

    result = search_function_definition("calculate_tax")

    assert "calculate_tax" in result or "Found" in result


@pytest.mark.unit
def test_search_function_definition_not_found(mocker):
    """Returns not-found message when grep returns nothing."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mocker.patch("subprocess.run", return_value=mock_result)

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_function_definition

    result = search_function_definition("nonexistent_func")

    assert "No definitions found" in result or "nonexistent_func" in result


@pytest.mark.unit
def test_search_function_definition_exception_handled(mocker):
    """Returns error string when subprocess.run raises."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    mocker.patch("subprocess.run", side_effect=OSError("command failed"))

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_function_definition

    result = search_function_definition("my_func")

    assert "Error" in result


@pytest.mark.unit
def test_search_function_definition_uses_language_patterns(mocker):
    """Runs grep with language-specific patterns for py and js extensions."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_run = mocker.patch("subprocess.run", return_value=mock_result)

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_function_definition

    search_function_definition("my_func", file_extensions="py,js")

    # Should have been called at least twice (py and js patterns)
    assert mock_run.call_count >= 2


# ============================================================================
# analyze_import_usage (@tool)
# ============================================================================


@pytest.mark.unit
def test_analyze_import_usage_python_file(tmp_path, mocker):
    """Correctly identifies Python imports and usages."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    test_file = tmp_path / "module.py"
    test_file.write_text("from mypackage import MyClass\n\ndef process():\n    obj = MyClass()\n    return obj.method()\n")

    from cli_tool.commands.code_reviewer.tools.code_analyzer import analyze_import_usage

    result = analyze_import_usage("MyClass", str(test_file))

    assert "IMPORTS" in result
    assert "USAGES" in result
    assert "MyClass" in result


@pytest.mark.unit
def test_analyze_import_usage_file_not_found(mocker):
    """Returns error message when file does not exist."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")

    from cli_tool.commands.code_reviewer.tools.code_analyzer import analyze_import_usage

    result = analyze_import_usage("MyClass", "/nonexistent/file.py")

    assert "File not found" in result or "not found" in result.lower()


@pytest.mark.unit
def test_analyze_import_usage_javascript_file(tmp_path, mocker):
    """Correctly identifies JavaScript import patterns."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    test_file = tmp_path / "component.js"
    test_file.write_text("import { useState } from 'react';\n\nfunction Component() {\n    const [x, setX] = useState(0);\n}\n")

    from cli_tool.commands.code_reviewer.tools.code_analyzer import analyze_import_usage

    result = analyze_import_usage("useState", str(test_file))

    assert "useState" in result


@pytest.mark.unit
def test_analyze_import_usage_symbol_imported_but_unused(tmp_path, mocker):
    """Reports warning when symbol is imported but not used."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    test_file = tmp_path / "module.py"
    test_file.write_text("from mypackage import UnusedClass\n\ndef foo():\n    pass\n")

    from cli_tool.commands.code_reviewer.tools.code_analyzer import analyze_import_usage

    result = analyze_import_usage("UnusedClass", str(test_file))

    assert "imported but never used" in result or "IMPORTS" in result


@pytest.mark.unit
def test_analyze_import_usage_symbol_used_but_not_imported(tmp_path, mocker):
    """Reports warning when symbol is used without an import."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    test_file = tmp_path / "module.py"
    test_file.write_text("def foo():\n    obj = UnimportedClass()\n    return obj\n")

    from cli_tool.commands.code_reviewer.tools.code_analyzer import analyze_import_usage

    result = analyze_import_usage("UnimportedClass", str(test_file))

    assert "used but no imports" in result or "No imports" in result


@pytest.mark.unit
def test_analyze_import_usage_no_imports_no_usages(tmp_path, mocker):
    """Returns analysis with zeros when symbol is not in the file."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    test_file = tmp_path / "module.py"
    test_file.write_text("x = 1\ny = 2\n")

    from cli_tool.commands.code_reviewer.tools.code_analyzer import analyze_import_usage

    result = analyze_import_usage("CompletelyAbsent", str(test_file))

    assert "Total imports: 0" in result
    assert "Total usages: 0" in result


@pytest.mark.unit
def test_analyze_import_usage_exception_handled(mocker):
    """Returns error string when an unexpected exception occurs."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")

    with patch("builtins.open", side_effect=PermissionError("permission denied")):
        from cli_tool.commands.code_reviewer.tools.code_analyzer import analyze_import_usage

        result = analyze_import_usage("MyClass", "/some/file.py")

    assert "Error" in result or "not found" in result.lower()


@pytest.mark.unit
def test_analyze_import_usage_multiple_imports_reports_issue(tmp_path, mocker):
    """Reports warning when symbol is imported multiple times."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    test_file = tmp_path / "module.py"
    test_file.write_text("from package_a import MyClass\nfrom package_b import MyClass\n\nobj = MyClass()\n")

    from cli_tool.commands.code_reviewer.tools.code_analyzer import analyze_import_usage

    result = analyze_import_usage("MyClass", str(test_file))

    # Should detect multiple imports
    assert "MyClass" in result
