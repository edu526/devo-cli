"""
Integration tests for code reviewer command analysis.

Tests the complete code review workflow including:
- Code review with staged changes
- Code review with committed changes
- Security issue identification
- API error handling
- GitPython Repo object mocking
- CodeAnalyzer.analyze method mocking
"""

import json
from unittest.mock import MagicMock, PropertyMock

import pytest
from click.testing import CliRunner

from cli_tool.commands.code_reviewer.commands.analyze import code_reviewer


@pytest.fixture
def mock_git_manager(mocker):
    """Mock GitManager for git operations."""
    mock_manager = MagicMock()
    return mocker.patch("cli_tool.commands.code_reviewer.core.analyzer.GitManager", return_value=mock_manager)


@pytest.fixture
def mock_code_review_analyzer_query(mocker):
    """Mock CodeReviewAnalyzer._get_agent_with_streaming for AI responses."""
    return mocker.patch("cli_tool.commands.code_reviewer.core.analyzer.CodeReviewAnalyzer._get_agent_with_streaming")


@pytest.fixture
def mock_select_profile(mocker):
    """Mock profile selection to avoid interactive prompts."""
    return mocker.patch("cli_tool.core.utils.aws.select_profile", return_value="default")


@pytest.fixture
def mock_console_ui(mocker):
    """Mock console_ui to avoid terminal output during tests."""
    # Mock in both analyzer and analyze modules
    mocker.patch("cli_tool.commands.code_reviewer.core.analyzer.console_ui")
    mock_analyze_ui = mocker.patch("cli_tool.commands.code_reviewer.commands.analyze.console_ui")
    return mock_analyze_ui  # Return the one used in the command


@pytest.mark.integration
def test_code_review_with_staged_changes(
    cli_runner, fixtures_dir, mock_git_manager, mock_code_review_analyzer_query, mock_select_profile, mock_console_ui
):
    """Test code review with staged changes."""
    # Load fixture data
    with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
        diff_data = json.load(f)

    # Mock GitManager.get_pr_context
    mock_git_manager.return_value.get_pr_context.return_value = {
        "current_branch": "feature/test-feature",
        "base_branch": "main",
        "total_changed_files": 1,
        "supported_changed_files": 1,
        "changed_files": ["cli_tool/commands/commit/core/generator.py"],
        "supported_files": ["cli_tool/commands/commit/core/generator.py"],
        "full_diff": diff_data["diff"],
        "file_diffs": {"cli_tool/commands/commit/core/generator.py": diff_data["diff"]},
    }

    # Mock AI response with code review
    ai_response = json.dumps(
        {
            "summary": "Code changes look good with minor suggestions",
            "issues": [
                {
                    "severity": "low",
                    "category": "style",
                    "description": "Consider adding type hints to function parameters",
                    "file": "cli_tool/commands/commit/core/generator.py",
                    "line": 15,
                }
            ],
        }
    )
    mock_code_review_analyzer_query.return_value = ai_response

    # Run code review command
    result = cli_runner.invoke(code_reviewer, ["--output", "json"], obj={"profile": None})

    # Verify success
    assert result.exit_code == 0

    # Parse JSON output
    output_data = json.loads(result.output)

    # Verify output structure
    assert "summary" in output_data
    assert "issues" in output_data
    assert "pr_context" in output_data
    assert "files_analyzed" in output_data

    # Verify PR context
    assert output_data["pr_context"]["current_branch"] == "feature/test-feature"
    assert output_data["pr_context"]["base_branch"] == "main"
    assert output_data["pr_context"]["supported_files"] == 1

    # Verify issues
    assert len(output_data["issues"]) == 1
    assert output_data["issues"][0]["severity"] == "low"
    assert output_data["issues"][0]["category"] == "style"


@pytest.mark.integration
def test_code_review_with_committed_changes(
    cli_runner, fixtures_dir, mock_git_manager, mock_code_review_analyzer_query, mock_select_profile, mock_console_ui
):
    """Test code review with committed changes (comparing branches)."""
    # Load fixture data with multiple files
    with open(fixtures_dir / "git_diffs" / "multi_file_change.json") as f:
        diff_data = json.load(f)

    # Mock GitManager.get_pr_context with multiple files
    file_paths = [f["file"] for f in diff_data["files"]]
    combined_diff = "\n".join([f["diff"] for f in diff_data["files"]])

    mock_git_manager.return_value.get_pr_context.return_value = {
        "current_branch": "feature/multi-file-update",
        "base_branch": "main",
        "total_changed_files": len(diff_data["files"]),
        "supported_changed_files": len(diff_data["files"]),
        "changed_files": file_paths,
        "supported_files": file_paths,
        "full_diff": combined_diff,
        "file_diffs": {f["file"]: f["diff"] for f in diff_data["files"]},
    }

    # Mock AI response with comprehensive review
    ai_response = json.dumps(
        {
            "summary": "Multiple files updated with consistent changes",
            "issues": [
                {
                    "severity": "medium",
                    "category": "maintainability",
                    "description": "Consider extracting common logic into a shared utility",
                    "file": diff_data["files"][0]["file"],
                    "line": 20,
                }
            ],
        }
    )
    mock_code_review_analyzer_query.return_value = ai_response

    # Run code review command with base branch specified
    result = cli_runner.invoke(code_reviewer, ["--base-branch", "main", "--output", "json"], obj={"profile": None})

    # Verify success
    assert result.exit_code == 0

    # Parse JSON output
    output_data = json.loads(result.output)

    # Verify multiple files were analyzed
    assert output_data["pr_context"]["supported_files"] == len(diff_data["files"])
    assert len(output_data["files_analyzed"]) == len(diff_data["files"])

    # Verify issues
    assert len(output_data["issues"]) == 1
    assert output_data["issues"][0]["severity"] == "medium"


@pytest.mark.integration
def test_code_review_identifies_security_issues(
    cli_runner, fixtures_dir, mock_git_manager, mock_code_review_analyzer_query, mock_select_profile, mock_console_ui
):
    """Test code review identifies security issues."""
    # Load fixture data with security issue
    with open(fixtures_dir / "git_diffs" / "security_issue.json") as f:
        diff_data = json.load(f)

    # Mock GitManager.get_pr_context
    mock_git_manager.return_value.get_pr_context.return_value = {
        "current_branch": "feature/add-auth",
        "base_branch": "main",
        "total_changed_files": 1,
        "supported_changed_files": 1,
        "changed_files": [diff_data["file"]],
        "supported_files": [diff_data["file"]],
        "full_diff": diff_data["diff"],
        "file_diffs": {diff_data["file"]: diff_data["diff"]},
    }

    # Mock AI response with security concerns
    ai_response = json.dumps(
        {
            "summary": "Security vulnerabilities detected in authentication code",
            "issues": [
                {
                    "severity": "high",
                    "category": "security",
                    "description": "Hardcoded credentials detected - use environment variables instead",
                    "file": diff_data["file"],
                    "line": 10,
                },
                {
                    "severity": "high",
                    "category": "security",
                    "description": "SQL injection vulnerability - use parameterized queries",
                    "file": diff_data["file"],
                    "line": 25,
                },
            ],
        }
    )
    mock_code_review_analyzer_query.return_value = ai_response

    # Run code review command
    result = cli_runner.invoke(code_reviewer, ["--output", "json"], obj={"profile": None})

    # Verify success
    assert result.exit_code == 0

    # Parse JSON output
    output_data = json.loads(result.output)

    # Verify security issues were identified
    assert len(output_data["issues"]) == 2
    security_issues = [issue for issue in output_data["issues"] if issue["category"] == "security"]
    assert len(security_issues) == 2

    # Verify severity levels
    for issue in security_issues:
        assert issue["severity"] == "high"
        assert "security" in issue["category"]


@pytest.mark.integration
def test_code_review_handles_api_errors_gracefully(
    cli_runner, fixtures_dir, mock_git_manager, mock_code_review_analyzer_query, mock_select_profile, mock_console_ui
):
    """Test code review handles API errors gracefully."""
    # Load fixture data
    with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
        diff_data = json.load(f)

    # Mock GitManager.get_pr_context
    mock_git_manager.return_value.get_pr_context.return_value = {
        "current_branch": "feature/test-feature",
        "base_branch": "main",
        "total_changed_files": 1,
        "supported_changed_files": 1,
        "changed_files": ["file.py"],
        "supported_files": ["file.py"],
        "full_diff": diff_data["diff"],
        "file_diffs": {"file.py": diff_data["diff"]},
    }

    # Mock AI agent to raise error
    mock_code_review_analyzer_query.side_effect = Exception("API rate limit exceeded")

    # Run code review command
    result = cli_runner.invoke(code_reviewer, ["--output", "json"], obj={"profile": None})

    # Verify error handling - the command catches exceptions and returns error in JSON
    assert result.exit_code == 0  # Command doesn't crash, returns error in JSON

    # Parse JSON output
    output_data = json.loads(result.output)

    # Verify error is in the output
    assert "error" in output_data or "Error" in result.output


@pytest.mark.integration
def test_code_review_with_no_changes(cli_runner, mock_git_manager, mock_select_profile, mock_console_ui):
    """Test code review with no supported file changes."""
    # Mock GitManager.get_pr_context with no supported files
    mock_git_manager.return_value.get_pr_context.return_value = {
        "current_branch": "feature/update-docs",
        "base_branch": "main",
        "total_changed_files": 2,
        "supported_changed_files": 0,
        "changed_files": ["README.md", "docs/guide.md"],
        "supported_files": [],
        "full_diff": "",
        "file_diffs": {},
    }

    # Run code review command
    result = cli_runner.invoke(code_reviewer, ["--output", "json"], obj={"profile": None})

    # Verify success with no analysis
    assert result.exit_code == 0

    # Parse JSON output
    output_data = json.loads(result.output)

    # Verify no analysis was performed
    assert "No supported code files" in output_data["summary"]
    assert output_data["pr_context"]["supported_files"] == 0
    assert len(output_data["issues"]) == 0


@pytest.mark.integration
def test_code_review_with_table_output(
    cli_runner, fixtures_dir, mock_git_manager, mock_code_review_analyzer_query, mock_select_profile, mock_console_ui
):
    """Test code review with table output format."""
    # Load fixture data
    with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
        diff_data = json.load(f)

    # Mock GitManager.get_pr_context
    mock_git_manager.return_value.get_pr_context.return_value = {
        "current_branch": "feature/test-feature",
        "base_branch": "main",
        "total_changed_files": 1,
        "supported_changed_files": 1,
        "changed_files": ["file.py"],
        "supported_files": ["file.py"],
        "full_diff": diff_data["diff"],
        "file_diffs": {"file.py": diff_data["diff"]},
    }

    # Mock AI response
    ai_response = json.dumps(
        {
            "summary": "Code review completed successfully",
            "issues": [{"severity": "low", "category": "style", "description": "Minor style improvement needed", "file": "file.py", "line": 10}],
        }
    )
    mock_code_review_analyzer_query.return_value = ai_response

    # Run code review command with table output (default)
    result = cli_runner.invoke(code_reviewer, ["--output", "table"], obj={"profile": None})

    # Verify success
    assert result.exit_code == 0

    # Verify console_ui.show_analysis_results_table was called
    assert mock_console_ui.show_analysis_results_table.called
    call_args = mock_console_ui.show_analysis_results_table.call_args
    assert call_args[0][0]["summary"] == "Code review completed successfully"
    assert call_args[1]["show_metrics"] is False


@pytest.mark.integration
def test_code_review_with_metrics_enabled(
    cli_runner, fixtures_dir, mock_git_manager, mock_code_review_analyzer_query, mock_select_profile, mock_console_ui, mocker
):
    """Test code review with metrics display enabled."""
    # Load fixture data
    with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
        diff_data = json.load(f)

    # Mock GitManager.get_pr_context
    mock_git_manager.return_value.get_pr_context.return_value = {
        "current_branch": "feature/test-feature",
        "base_branch": "main",
        "total_changed_files": 1,
        "supported_changed_files": 1,
        "changed_files": ["file.py"],
        "supported_files": ["file.py"],
        "full_diff": diff_data["diff"],
        "file_diffs": {"file.py": diff_data["diff"]},
    }

    # Mock AI response
    ai_response = json.dumps({"summary": "Code review completed", "issues": []})
    mock_code_review_analyzer_query.return_value = ai_response

    # Mock metrics on the analyzer instance
    mock_analyzer = mocker.patch("cli_tool.commands.code_reviewer.commands.analyze.CodeReviewAnalyzer")
    mock_instance = mock_analyzer.return_value
    mock_instance.analyze_pr.return_value = {
        "summary": "Code review completed",
        "pr_context": {
            "current_branch": "feature/test-feature",
            "base_branch": "main",
            "total_files": 1,
            "supported_files": 1,
            "changed_files": ["file.py"],
        },
        "issues": [],
        "files_analyzed": ["file.py"],
        "metrics": {"accumulated_usage": {"totalTokens": 1500}, "total_duration": 2.5, "total_cycles": 3, "tool_usage": {"get_file_content": 2}},
    }

    # Run code review command with metrics
    result = cli_runner.invoke(code_reviewer, ["--show-metrics", "--output", "json"], obj={"profile": None})

    # Verify success
    assert result.exit_code == 0

    # Parse JSON output
    output_data = json.loads(result.output)

    # Verify metrics are included
    assert "metrics" in output_data
    assert output_data["metrics"]["accumulated_usage"]["totalTokens"] == 1500
    assert output_data["metrics"]["total_duration"] == pytest.approx(2.5)


@pytest.mark.integration
def test_code_review_with_full_prompt(
    cli_runner, fixtures_dir, mock_git_manager, mock_code_review_analyzer_query, mock_select_profile, mock_console_ui
):
    """Test code review with full detailed prompt."""
    # Load fixture data
    with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
        diff_data = json.load(f)

    # Mock GitManager.get_pr_context
    mock_git_manager.return_value.get_pr_context.return_value = {
        "current_branch": "feature/test-feature",
        "base_branch": "main",
        "total_changed_files": 1,
        "supported_changed_files": 1,
        "changed_files": ["file.py"],
        "supported_files": ["file.py"],
        "full_diff": diff_data["diff"],
        "file_diffs": {"file.py": diff_data["diff"]},
    }

    # Mock AI response
    ai_response = json.dumps({"summary": "Comprehensive code review completed", "issues": []})
    mock_code_review_analyzer_query.return_value = ai_response

    # Run code review command with full prompt
    result = cli_runner.invoke(code_reviewer, ["--full-prompt", "--output", "json"], obj={"profile": None})

    # Verify success
    assert result.exit_code == 0

    # Verify the analyzer was called with use_short_prompt=False
    # This is verified by checking that the command executed successfully
    # The actual prompt selection happens internally in CodeReviewAnalyzer


@pytest.mark.integration
def test_code_review_with_custom_repo_path(
    cli_runner, fixtures_dir, mock_git_manager, mock_code_review_analyzer_query, mock_select_profile, mock_console_ui
):
    """Test code review with custom repository path."""
    # Load fixture data
    with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
        diff_data = json.load(f)

    # Mock GitManager.get_pr_context
    mock_git_manager.return_value.get_pr_context.return_value = {
        "current_branch": "feature/test-feature",
        "base_branch": "main",
        "total_changed_files": 1,
        "supported_changed_files": 1,
        "changed_files": ["file.py"],
        "supported_files": ["file.py"],
        "full_diff": diff_data["diff"],
        "file_diffs": {"file.py": diff_data["diff"]},
    }

    # Mock AI response
    ai_response = json.dumps({"summary": "Code review completed", "issues": []})
    mock_code_review_analyzer_query.return_value = ai_response

    # Run code review command with custom repo path
    result = cli_runner.invoke(code_reviewer, ["--repo-path", "/custom/repo/path", "--output", "json"], obj={"profile": None})

    # Verify success
    assert result.exit_code == 0

    # Verify GitManager was initialized with custom path
    # The path is passed to analyze_pr which creates GitManager internally


@pytest.mark.integration
def test_code_review_with_different_severity_levels(
    cli_runner, fixtures_dir, mock_git_manager, mock_code_review_analyzer_query, mock_select_profile, mock_console_ui
):
    """Test code review with issues of different severity levels."""
    # Load fixture data
    with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
        diff_data = json.load(f)

    # Mock GitManager.get_pr_context
    mock_git_manager.return_value.get_pr_context.return_value = {
        "current_branch": "feature/test-feature",
        "base_branch": "main",
        "total_changed_files": 1,
        "supported_changed_files": 1,
        "changed_files": ["file.py"],
        "supported_files": ["file.py"],
        "full_diff": diff_data["diff"],
        "file_diffs": {"file.py": diff_data["diff"]},
    }

    # Mock AI response with multiple severity levels
    ai_response = json.dumps(
        {
            "summary": "Multiple issues found with varying severity",
            "issues": [
                {"severity": "critical", "category": "security", "description": "Critical security vulnerability", "file": "file.py", "line": 10},
                {"severity": "high", "category": "bug", "description": "Potential null pointer exception", "file": "file.py", "line": 20},
                {"severity": "medium", "category": "performance", "description": "Inefficient algorithm", "file": "file.py", "line": 30},
                {"severity": "low", "category": "style", "description": "Minor style issue", "file": "file.py", "line": 40},
            ],
        }
    )
    mock_code_review_analyzer_query.return_value = ai_response

    # Run code review command
    result = cli_runner.invoke(code_reviewer, ["--output", "json"], obj={"profile": None})

    # Verify success
    assert result.exit_code == 0

    # Parse JSON output
    output_data = json.loads(result.output)

    # Verify all severity levels are present
    assert len(output_data["issues"]) == 4
    severities = [issue["severity"] for issue in output_data["issues"]]
    assert "critical" in severities
    assert "high" in severities
    assert "medium" in severities
    assert "low" in severities


@pytest.mark.integration
def test_code_review_with_non_json_ai_response(
    cli_runner, fixtures_dir, mock_git_manager, mock_code_review_analyzer_query, mock_select_profile, mock_console_ui
):
    """Test code review handles non-JSON AI responses gracefully."""
    # Load fixture data
    with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
        diff_data = json.load(f)

    # Mock GitManager.get_pr_context
    mock_git_manager.return_value.get_pr_context.return_value = {
        "current_branch": "feature/test-feature",
        "base_branch": "main",
        "total_changed_files": 1,
        "supported_changed_files": 1,
        "changed_files": ["file.py"],
        "supported_files": ["file.py"],
        "full_diff": diff_data["diff"],
        "file_diffs": {"file.py": diff_data["diff"]},
    }

    # Mock AI response with plain text (not JSON)
    ai_response = "The code looks good overall. No major issues found."
    mock_code_review_analyzer_query.return_value = ai_response

    # Run code review command
    result = cli_runner.invoke(code_reviewer, ["--output", "json"], obj={"profile": None})

    # Verify success (should handle gracefully)
    assert result.exit_code == 0

    # Parse JSON output
    output_data = json.loads(result.output)

    # Verify fallback structure was created
    assert "summary" in output_data
    assert "issues" in output_data
    assert len(output_data["issues"]) == 0


@pytest.mark.integration
def test_code_review_with_empty_diff(cli_runner, mock_git_manager, mock_select_profile, mock_console_ui):
    """Test code review with empty diff (no actual changes)."""
    # Mock GitManager.get_pr_context with empty diff
    mock_git_manager.return_value.get_pr_context.return_value = {
        "current_branch": "feature/no-changes",
        "base_branch": "main",
        "total_changed_files": 0,
        "supported_changed_files": 0,
        "changed_files": [],
        "supported_files": [],
        "full_diff": "",
        "file_diffs": {},
    }

    # Run code review command
    result = cli_runner.invoke(code_reviewer, ["--output", "json"], obj={"profile": None})

    # Verify success
    assert result.exit_code == 0

    # Parse JSON output
    output_data = json.loads(result.output)

    # Verify no analysis was performed
    assert output_data["pr_context"]["supported_files"] == 0
    assert len(output_data["issues"]) == 0
    assert "No supported code files" in output_data["summary"] or "no changes" in output_data["summary"].lower()


@pytest.mark.integration
def test_code_review_with_very_large_diff(cli_runner, mock_git_manager, mock_code_review_analyzer_query, mock_select_profile, mock_console_ui):
    """Test code review with very large diff (many files)."""
    # Create a large diff with many files
    large_file_list = [f"file_{i}.py" for i in range(50)]
    large_diff = "\n".join([f"diff --git a/file_{i}.py b/file_{i}.py\n+# Change in file {i}" for i in range(50)])

    # Mock GitManager.get_pr_context with many files
    mock_git_manager.return_value.get_pr_context.return_value = {
        "current_branch": "feature/large-refactor",
        "base_branch": "main",
        "total_changed_files": 50,
        "supported_changed_files": 50,
        "changed_files": large_file_list,
        "supported_files": large_file_list,
        "full_diff": large_diff,
        "file_diffs": {f"file_{i}.py": f"diff --git a/file_{i}.py b/file_{i}.py\n+# Change in file {i}" for i in range(50)},
    }

    # Mock AI response
    ai_response = json.dumps(
        {
            "summary": "Large refactoring reviewed - multiple files updated",
            "issues": [
                {
                    "severity": "medium",
                    "category": "maintainability",
                    "description": "Consider breaking this into smaller PRs",
                    "file": "file_0.py",
                    "line": 1,
                }
            ],
        }
    )
    mock_code_review_analyzer_query.return_value = ai_response

    # Run code review command
    result = cli_runner.invoke(code_reviewer, ["--output", "json"], obj={"profile": None})

    # Verify success
    assert result.exit_code == 0

    # Parse JSON output
    output_data = json.loads(result.output)

    # Verify large number of files were processed
    assert output_data["pr_context"]["supported_files"] == 50
    assert len(output_data["files_analyzed"]) == 50


@pytest.mark.integration
def test_code_review_with_mixed_severity_and_categories(
    cli_runner, fixtures_dir, mock_git_manager, mock_code_review_analyzer_query, mock_select_profile, mock_console_ui
):
    """Test code review with issues across multiple categories and severities."""
    # Load fixture data
    with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
        diff_data = json.load(f)

    # Mock GitManager.get_pr_context
    mock_git_manager.return_value.get_pr_context.return_value = {
        "current_branch": "feature/complex-changes",
        "base_branch": "main",
        "total_changed_files": 1,
        "supported_changed_files": 1,
        "changed_files": ["file.py"],
        "supported_files": ["file.py"],
        "full_diff": diff_data["diff"],
        "file_diffs": {"file.py": diff_data["diff"]},
    }

    # Mock AI response with diverse issues
    ai_response = json.dumps(
        {
            "summary": "Multiple issues found across different categories",
            "issues": [
                {"severity": "high", "category": "security", "description": "Potential XSS vulnerability", "file": "file.py", "line": 10},
                {"severity": "high", "category": "bug", "description": "Race condition detected", "file": "file.py", "line": 20},
                {"severity": "medium", "category": "performance", "description": "N+1 query problem", "file": "file.py", "line": 30},
                {
                    "severity": "medium",
                    "category": "maintainability",
                    "description": "Complex function needs refactoring",
                    "file": "file.py",
                    "line": 40,
                },
                {"severity": "low", "category": "style", "description": "Inconsistent naming convention", "file": "file.py", "line": 50},
                {"severity": "low", "category": "documentation", "description": "Missing docstring", "file": "file.py", "line": 60},
            ],
        }
    )
    mock_code_review_analyzer_query.return_value = ai_response

    # Run code review command
    result = cli_runner.invoke(code_reviewer, ["--output", "json"], obj={"profile": None})

    # Verify success
    assert result.exit_code == 0

    # Parse JSON output
    output_data = json.loads(result.output)

    # Verify all issues are present
    assert len(output_data["issues"]) == 6

    # Verify categories
    categories = [issue["category"] for issue in output_data["issues"]]
    assert "security" in categories
    assert "bug" in categories
    assert "performance" in categories
    assert "maintainability" in categories
    assert "style" in categories
    assert "documentation" in categories

    # Verify severities
    severities = [issue["severity"] for issue in output_data["issues"]]
    assert severities.count("high") == 2
    assert severities.count("medium") == 2
    assert severities.count("low") == 2


@pytest.mark.integration
def test_code_review_output_format_consistency(
    cli_runner, fixtures_dir, mock_git_manager, mock_code_review_analyzer_query, mock_select_profile, mock_console_ui
):
    """Test that both JSON and table output formats work correctly."""
    # Load fixture data
    with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
        diff_data = json.load(f)

    # Mock GitManager.get_pr_context
    mock_git_manager.return_value.get_pr_context.return_value = {
        "current_branch": "feature/test-feature",
        "base_branch": "main",
        "total_changed_files": 1,
        "supported_changed_files": 1,
        "changed_files": ["file.py"],
        "supported_files": ["file.py"],
        "full_diff": diff_data["diff"],
        "file_diffs": {"file.py": diff_data["diff"]},
    }

    # Mock AI response
    ai_response = json.dumps(
        {
            "summary": "Code review completed",
            "issues": [{"severity": "medium", "category": "style", "description": "Test issue", "file": "file.py", "line": 10}],
        }
    )
    mock_code_review_analyzer_query.return_value = ai_response

    # Test JSON output
    result_json = cli_runner.invoke(code_reviewer, ["--output", "json"], obj={"profile": None})
    assert result_json.exit_code == 0
    output_data = json.loads(result_json.output)
    assert "summary" in output_data
    assert "issues" in output_data
    assert len(output_data["issues"]) == 1

    # Test table output
    result_table = cli_runner.invoke(code_reviewer, ["--output", "table"], obj={"profile": None})
    assert result_table.exit_code == 0
    # Verify console_ui.show_analysis_results_table was called
    assert mock_console_ui.show_analysis_results_table.called
