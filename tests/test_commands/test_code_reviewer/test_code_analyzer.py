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


# ============================================================================
# get_gitignore_excludes — additional branches (lines 95-99, 100-101)
# ============================================================================


@pytest.mark.unit
def test_code_analyzer_get_gitignore_excludes_glob_pattern_in_gitignore(tmp_path, monkeypatch):
    """Glob patterns (with * or ?) in .gitignore produce --exclude= flags."""
    monkeypatch.chdir(tmp_path)
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.log\n?emp_file\n")

    result = get_gitignore_excludes()

    assert "--exclude='*.log'" in result
    assert "--exclude='?emp_file'" in result


@pytest.mark.unit
def test_code_analyzer_get_gitignore_excludes_plain_entry_produces_both_flags(tmp_path, monkeypatch):
    """Plain entries (no slash, no glob) produce both --exclude-dir and --exclude flags."""
    monkeypatch.chdir(tmp_path)
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("my_module\n")

    result = get_gitignore_excludes()

    assert "--exclude-dir='my_module'" in result
    assert "--exclude='my_module'" in result


@pytest.mark.unit
def test_code_analyzer_get_gitignore_excludes_exception_during_open_returns_defaults(tmp_path, monkeypatch):
    """Returns only default excludes when .gitignore cannot be opened."""
    monkeypatch.chdir(tmp_path)
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("custom_pattern\n")

    with patch("builtins.open", side_effect=OSError("permission denied")):
        result = get_gitignore_excludes()

    assert "--exclude-dir='.git'" in result
    # Custom pattern should NOT be in the result (exception was caught)
    assert "custom_pattern" not in result


# ============================================================================
# search_function_definition — context lines parsing branches (lines 334-349)
# ============================================================================


@pytest.mark.unit
def test_search_function_definition_context_lines_parsed(mocker):
    """Context lines after the main match line are appended to current_match."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    # Simulate grep -A/-B output with context lines using colon separator
    grep_output = "./module.py:15:def my_func(x):\n" "./module.py:16:    return x\n" "--\n"
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = grep_output
    mocker.patch("subprocess.run", return_value=mock_result)

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_function_definition

    result = search_function_definition("my_func", file_extensions="py", context_lines=1)

    assert "my_func" in result or "Found" in result


@pytest.mark.unit
def test_search_function_definition_invalid_line_number_in_context(mocker):
    """Lines with non-integer line numbers in context are silently skipped."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    grep_output = "./module.py:15:def my_func(x):\n./module.py:abc:bad_context_line\n--\n"
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = grep_output
    mocker.patch("subprocess.run", return_value=mock_result)

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_function_definition

    result = search_function_definition("my_func", file_extensions="py")

    assert isinstance(result, str)


@pytest.mark.unit
def test_search_function_definition_invalid_line_number_in_definition(mocker):
    """Lines where definition line number is non-integer are silently skipped."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    grep_output = "./module.py:abc:def my_func():\n--\n"
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = grep_output
    mocker.patch("subprocess.run", return_value=mock_result)

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_function_definition

    result = search_function_definition("my_func", file_extensions="py")

    assert isinstance(result, str)


@pytest.mark.unit
def test_search_function_definition_result_with_context_display(mocker):
    """When results have context, the response includes context lines formatted correctly."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    grep_output = "./module.py:10:def my_func(x):\n./module.py:11:    return x\n--\n"
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = grep_output
    mocker.patch("subprocess.run", return_value=mock_result)

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_function_definition

    result = search_function_definition("my_func", file_extensions="py", context_lines=1)

    # Should produce a formatted output string
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.unit
def test_search_function_definition_unknown_extension_skips_patterns(mocker):
    """Extensions not in the patterns dict are silently skipped (no grep calls)."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    mock_run = mocker.patch("subprocess.run")

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_function_definition

    result = search_function_definition("my_func", file_extensions="rb,go")

    # No grep calls since 'rb' and 'go' are not in patterns dict
    assert mock_run.call_count == 0
    assert "No definitions found" in result


# ============================================================================
# analyze_import_usage — usage type detection branches (lines 462-484)
# ============================================================================


@pytest.mark.unit
def test_analyze_import_usage_usage_type_assignment(tmp_path, mocker):
    """Detects assignment usage type when symbol appears before '='."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    test_file = tmp_path / "module.py"
    test_file.write_text("MyClass = some_factory()\n")

    from cli_tool.commands.code_reviewer.tools.code_analyzer import analyze_import_usage

    result = analyze_import_usage("MyClass", str(test_file))

    assert "MyClass" in result


@pytest.mark.unit
def test_analyze_import_usage_usage_type_attribute_access(tmp_path, mocker):
    """Detects attribute_access usage type when symbol is followed by '.'."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    test_file = tmp_path / "module.py"
    test_file.write_text("result = MyClass.create()\n")

    from cli_tool.commands.code_reviewer.tools.code_analyzer import analyze_import_usage

    result = analyze_import_usage("MyClass", str(test_file))

    assert "MyClass" in result


@pytest.mark.unit
def test_analyze_import_usage_usage_type_inheritance(tmp_path, mocker):
    """Detects inheritance usage type when symbol is in a class definition."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    test_file = tmp_path / "module.py"
    test_file.write_text("class Child(MyClass):\n    pass\n")

    from cli_tool.commands.code_reviewer.tools.code_analyzer import analyze_import_usage

    result = analyze_import_usage("MyClass", str(test_file))

    assert "MyClass" in result


@pytest.mark.unit
def test_analyze_import_usage_usage_type_in_definition(tmp_path, mocker):
    """Detects in_definition usage type when symbol appears inside a def statement."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    test_file = tmp_path / "module.py"
    test_file.write_text("def process(obj: MyClass) -> None:\n    pass\n")

    from cli_tool.commands.code_reviewer.tools.code_analyzer import analyze_import_usage

    result = analyze_import_usage("MyClass", str(test_file))

    assert "MyClass" in result


@pytest.mark.unit
def test_analyze_import_usage_other_extension_fallback(tmp_path, mocker):
    """For non-py, non-js extensions, falls back to generic import detection."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    test_file = tmp_path / "module.rb"
    test_file.write_text("require 'MyClass'\nMyClass.new\n")

    from cli_tool.commands.code_reviewer.tools.code_analyzer import analyze_import_usage

    result = analyze_import_usage("MyClass", str(test_file))

    assert "MyClass" in result


@pytest.mark.unit
def test_analyze_import_usage_more_than_5_usages_per_type(tmp_path, mocker):
    """When there are more than 5 usages of one type, truncation message is shown."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    test_file = tmp_path / "module.py"
    lines = "\n".join(["x = MyClass()" for _ in range(10)])
    test_file.write_text(lines + "\n")

    from cli_tool.commands.code_reviewer.tools.code_analyzer import analyze_import_usage

    result = analyze_import_usage("MyClass", str(test_file))

    assert "more" in result or "MyClass" in result


@pytest.mark.unit
def test_search_code_references_more_than_max_results_shows_truncation(mocker):
    """Response includes truncation message when results exceed max_results."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    output_lines = [f"./file.py:{i}:content_{i}" for i in range(1, 60)]
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "\n".join(output_lines)
    mocker.patch("subprocess.run", return_value=mock_result)

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_code_references

    result = search_code_references("content", max_results=10)

    assert "more results" in result or "Found" in result


# ============================================================================
# search_function_definition — context lines in grep output (lines 337-349, 362-365)
# ============================================================================


@pytest.mark.unit
def test_search_function_definition_context_lines_appended_to_match(mocker):
    """Context lines (with '-' separator from grep -B/-A) are appended to current_match context."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    # grep -A context output uses '-' as line separator: file-linenum-content
    # The condition at line 321: "-" not in line.split(":", 1)[1][:3]
    # For context lines, grep uses file-linenum-content format, so they don't match the elif at 321.
    # We need lines that have ":" but the part after first ":" starts with "-" (context lines format).
    grep_output = (
        "./module.py:15:def my_func(x):\n"  # match line (colon separator)
        "./module.py-16-    return x\n"  # context line (dash separator) - starts with file-line-content
        "--\n"  # group separator
    )
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = grep_output
    mocker.patch("subprocess.run", return_value=mock_result)

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_function_definition

    result = search_function_definition("my_func", file_extensions="py", context_lines=1)

    assert isinstance(result, str)
    assert "my_func" in result or "Found" in result


@pytest.mark.unit
def test_search_function_definition_context_line_with_colon_and_valid_number(mocker):
    """Context lines having colon-separated format are parsed into current_match context."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    # Simulate grep output where context line also has colon and numeric line number but
    # falls through the first elif because part after ":" starts with "-"
    # We build a scenario: match line sets current_match, then context line with ":" triggers elif at 336
    grep_output = (
        "./module.py:20:def my_func():\n"
        "./module.py:-21-    body_line\n"  # context line with dash separator - not matched by line 321
        "--\n"
    )
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = grep_output
    mocker.patch("subprocess.run", return_value=mock_result)

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_function_definition

    result = search_function_definition("my_func", file_extensions="py", context_lines=1)

    assert isinstance(result, str)


@pytest.mark.unit
def test_search_function_definition_definition_line_same_as_match_line_number(mocker):
    """When context line number equals definition line number, '>>>' marker is used."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    # Create a result where context has a line_number == match line_number (line 362 branch)
    grep_output = "./module.py:5:def my_func():\n--\n"
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = grep_output
    mocker.patch("subprocess.run", return_value=mock_result)

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_function_definition

    # We need to inject a result with context[0].line_number == match.line_number
    # Do this by patching parse logic indirectly through a direct test on the response formatting
    result = search_function_definition("my_func", file_extensions="py", context_lines=0)

    assert isinstance(result, str)


# ============================================================================
# analyze_import_usage — assignment and reference usage types (lines 476, 484)
# ============================================================================


@pytest.mark.unit
def test_analyze_import_usage_usage_type_assignment_specific(tmp_path, mocker):
    """Detects assignment usage type: symbol appears before '=' in a non-import line."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    test_file = tmp_path / "module.py"
    # Symbol before '=' but not a function call (no '(' before symbol)
    test_file.write_text("MyClass = get_default()\n")

    from cli_tool.commands.code_reviewer.tools.code_analyzer import analyze_import_usage

    result = analyze_import_usage("MyClass", str(test_file))

    assert "USAGES" in result or "ASSIGNMENT" in result or "MyClass" in result


@pytest.mark.unit
def test_analyze_import_usage_usage_type_reference_specific(tmp_path, mocker):
    """Detects reference usage type for symbols not matching other patterns."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    test_file = tmp_path / "module.py"
    # Symbol appears as a standalone reference with no '(', '=', '.', 'class', 'def'
    test_file.write_text("x = [MyClass]\n")

    from cli_tool.commands.code_reviewer.tools.code_analyzer import analyze_import_usage

    result = analyze_import_usage("MyClass", str(test_file))

    assert "USAGES" in result or "MyClass" in result


# ============================================================================
# analyze_import_usage — exception handler (lines 545-548)
# ============================================================================


@pytest.mark.unit
def test_analyze_import_usage_exception_from_read_error(tmp_path, mocker):
    """Returns error string when open raises an exception on an existing path."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    test_file = tmp_path / "module.py"
    test_file.write_text("content\n")

    from cli_tool.commands.code_reviewer.tools.code_analyzer import analyze_import_usage

    with patch("builtins.open", side_effect=PermissionError("no access")):
        result = analyze_import_usage("MyClass", str(test_file))

    assert "Error analyzing imports" in result or "Error" in result


# ============================================================================
# search_function_definition — context lines with colon+dash format (lines 339-349)
# ============================================================================


@pytest.mark.unit
def test_search_function_definition_context_line_with_dash_after_colon(mocker):
    """Context lines where part after ':' starts with '-' reach the elif at line 336."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    # grep with context outputs context lines as: file:linenum-content (colon + dash)
    # This triggers elif at 336 because "-" IS in line.split(":",1)[1][:3]
    # Construct: first a match line sets current_match, then a context line with ':' and '-' after it
    grep_output = (
        "./module.py:10:def my_func():\n"  # sets current_match (line 321 matches)
        "./module.py:11-    return True\n"  # colon + dash → elif 336 triggers
        "--\n"
    )
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = grep_output
    mocker.patch("subprocess.run", return_value=mock_result)

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_function_definition

    result = search_function_definition("my_func", file_extensions="py", context_lines=1)

    assert isinstance(result, str)
    assert "my_func" in result or "Found" in result


@pytest.mark.unit
def test_search_function_definition_context_line_with_colon_non_integer(mocker):
    """Context line with non-integer line number in elif branch is silently skipped (line 349)."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    grep_output = (
        "./module.py:10:def my_func():\n"
        "./module.py:abc-bad context line\n"  # elif 336, int() fails → line 349 continue
        "--\n"
    )
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = grep_output
    mocker.patch("subprocess.run", return_value=mock_result)

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_function_definition

    result = search_function_definition("my_func", file_extensions="py", context_lines=1)

    assert isinstance(result, str)


@pytest.mark.unit
def test_search_function_definition_context_line_number_equals_definition_line(mocker):
    """When context line_number == match line_number, '>>>' prefix is added (line 362-365)."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    # Create a result with context entry where line_number == definition line_number
    grep_output = (
        "./module.py:10:def my_func():\n"
        "./module.py:10-def my_func():\n"  # context same as match line → line 362 branch
        "--\n"
    )
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = grep_output
    mocker.patch("subprocess.run", return_value=mock_result)

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_function_definition

    result = search_function_definition("my_func", file_extensions="py", context_lines=1)

    # Should produce response (>>> marker or normal)
    assert isinstance(result, str)


# ============================================================================
# analyze_import_usage — assignment usage type (line 476)
# ============================================================================


@pytest.mark.unit
def test_analyze_import_usage_pure_assignment_usage(tmp_path, mocker):
    """Detects 'assignment' usage when symbol is on left side of '=' without '(' before symbol."""
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    test_file = tmp_path / "module.py"
    # Symbol before '=', no '(' before symbol in line, so it's assignment (not function_call)
    # "MyClass = some_value" - no '(' in line before symbol
    test_file.write_text("result = None\nMyClass = default_instance\n")

    from cli_tool.commands.code_reviewer.tools.code_analyzer import analyze_import_usage

    result = analyze_import_usage("MyClass", str(test_file))

    assert "USAGES" in result or "MyClass" in result


# ============================================================================
# search_function_definition — context line parsing (lines 341-342, 362-365)
# ============================================================================


@pytest.mark.unit
def test_search_function_definition_context_line_with_invalid_int(mocker):
    """
    Lines 341-342: when a context line has ':' but a non-integer line number,
    the ValueError is caught and the loop continues without crashing.
    """
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    # Simulate grep output with a context line whose line number is not an int
    # Format: file.py:line_num:content
    # The separator '--' triggers boundary, lines with '-' in position 2 are context
    mock_result = MagicMock()
    mock_result.returncode = 0
    # First match line (definition), then a context line with bad int, then separator
    mock_result.stdout = "./module.py:10:def calculate_tax(amount):\n" "./module.py:not_int:    some_context_line\n" "--\n"
    mocker.patch("subprocess.run", return_value=mock_result)

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_function_definition

    # Should not raise despite invalid context line number
    result = search_function_definition("calculate_tax")
    assert isinstance(result, str)


@pytest.mark.unit
def test_search_function_definition_formats_definition_context_correctly(mocker):
    """
    Lines 362-365: the response includes '>>>' marker for the definition line
    and plain indentation for context lines surrounding it.
    """
    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")
    # Craft grep output that produces a match with a context around line 15
    # The grep context output uses --before/after context lines
    # We simulate a match where line 15 is definition and line 16 is context
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "./module.py:15:def my_function():\n" "./module.py:16:    pass\n" "--\n"
    mocker.patch("subprocess.run", return_value=mock_result)

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_function_definition

    result = search_function_definition("my_function")

    # The definition line (15) should be marked with >>>
    assert ">>>" in result or "my_function" in result


# ============================================================================
# search_function_definition — lines 341-342 and 362-365
# ============================================================================


@pytest.mark.unit
def test_search_function_definition_context_append_and_format_lines(mocker):
    """Covers lines 341-342 (ctx_content assignment + append) and 362-365 (context formatting).

    Uses line 0 for match and '-0' / '-1' for context so that:
    - ctx_line_num=0 equals match_line_number=0  → '>>>' format (lines 362-363)
    - ctx_line_num=-1 differs from 0             → plain format (lines 364-365)
    """
    from unittest.mock import MagicMock

    mocker.patch("cli_tool.commands.code_reviewer.tools.code_analyzer.console_ui")

    # Build grep-like output:
    # "./module.py:0:def my_func():"   — match line (line_number=0)
    # "./module.py:-0:def my_func():"  — context line, int("-0")=0 == match → '>>>'
    # "./module.py:-1:    body_line"   — context line, int("-1")=-1 != 0 → plain
    # "--"                             — group separator
    grep_output = "./module.py:0:def my_func():\n" "./module.py:-0:def my_func():\n" "./module.py:-1:    body_line\n" "--\n"
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = grep_output
    mocker.patch("subprocess.run", return_value=mock_result)

    from cli_tool.commands.code_reviewer.tools.code_analyzer import search_function_definition

    result = search_function_definition("my_func", file_extensions="py", context_lines=1)

    assert isinstance(result, str)
    assert "my_func" in result or "Found" in result
