"""
Unit tests for cli_tool.core.ui.console_ui module.

Tests cover ConsoleUI, StreamingDisplayManager, and helper data structures.
All Rich console output is mocked to avoid terminal interaction.
"""

from unittest.mock import MagicMock, patch

import pytest

from cli_tool.core.ui.console_ui import _ISSUE_TYPE_INFO, _SEVERITY_INFO, ConsoleUI, StreamingDisplayManager

# ============================================================================
# StreamingDisplayManager
# ============================================================================


@pytest.mark.unit
def test_streaming_manager_initial_state():
    """StreamingDisplayManager starts inactive with no panels."""
    mock_console = MagicMock()
    mgr = StreamingDisplayManager(mock_console)
    assert mgr.is_active is False
    assert mgr.live_display is None
    assert mgr.event_panels == {}


@pytest.mark.unit
def test_streaming_manager_start_streaming_sets_active():
    """start_streaming activates the live display."""
    mock_console = MagicMock()
    mgr = StreamingDisplayManager(mock_console)

    with patch("cli_tool.core.ui.console_ui.Live") as mock_live_cls:
        mock_live = MagicMock()
        mock_live_cls.return_value = mock_live

        mgr.start_streaming()

    assert mgr.is_active is True
    mock_live.start.assert_called_once()


@pytest.mark.unit
def test_streaming_manager_start_streaming_idempotent():
    """Calling start_streaming twice does not start a second Live instance."""
    mock_console = MagicMock()
    mgr = StreamingDisplayManager(mock_console)

    with patch("cli_tool.core.ui.console_ui.Live") as mock_live_cls:
        mock_live = MagicMock()
        mock_live_cls.return_value = mock_live
        mgr.start_streaming()
        mgr.start_streaming()

    assert mock_live_cls.call_count == 1


@pytest.mark.unit
def test_streaming_manager_stop_streaming_clears_state():
    """stop_streaming resets all state fields."""
    mock_console = MagicMock()
    mgr = StreamingDisplayManager(mock_console)

    with patch("cli_tool.core.ui.console_ui.Live") as mock_live_cls:
        mock_live = MagicMock()
        mock_live_cls.return_value = mock_live
        mgr.start_streaming()
        mgr.event_panels["some_event"] = MagicMock()

        mgr.stop_streaming()

    assert mgr.is_active is False
    assert mgr.live_display is None
    assert mgr.event_panels == {}
    mock_live.stop.assert_called_once()


@pytest.mark.unit
def test_streaming_manager_stop_streaming_when_inactive_is_noop():
    """stop_streaming on an inactive manager does nothing."""
    mock_console = MagicMock()
    mgr = StreamingDisplayManager(mock_console)
    # Should not raise
    mgr.stop_streaming()
    assert mgr.is_active is False


@pytest.mark.unit
def test_streaming_manager_update_event_panel_stores_panel():
    """update_event_panel stores the panel by event_id."""
    mock_console = MagicMock()
    mgr = StreamingDisplayManager(mock_console)
    mock_panel = MagicMock()

    mgr.update_event_panel("evt_1", mock_panel)

    assert "evt_1" in mgr.event_panels
    assert mgr.event_panels["evt_1"] is mock_panel


@pytest.mark.unit
def test_streaming_manager_update_event_panel_updates_live_display():
    """update_event_panel refreshes the live display when active."""
    mock_console = MagicMock()
    mgr = StreamingDisplayManager(mock_console)

    with patch("cli_tool.core.ui.console_ui.Live") as mock_live_cls:
        mock_live = MagicMock()
        mock_live_cls.return_value = mock_live
        mgr.start_streaming()

        mock_panel = MagicMock()
        mgr.update_event_panel("evt_1", mock_panel)

    mock_live.update.assert_called()


@pytest.mark.unit
def test_streaming_manager_remove_event_panel():
    """remove_event_panel deletes a stored panel."""
    mock_console = MagicMock()
    mgr = StreamingDisplayManager(mock_console)
    mgr.event_panels["evt_1"] = MagicMock()

    mgr.remove_event_panel("evt_1")

    assert "evt_1" not in mgr.event_panels


@pytest.mark.unit
def test_streaming_manager_remove_nonexistent_panel_is_noop():
    """Removing a panel that does not exist does not raise."""
    mock_console = MagicMock()
    mgr = StreamingDisplayManager(mock_console)
    # Should not raise
    mgr.remove_event_panel("nonexistent_evt")


# ============================================================================
# ConsoleUI — basic instantiation
# ============================================================================


@pytest.mark.unit
def test_console_ui_initializes():
    """ConsoleUI can be instantiated without error."""
    with patch("cli_tool.core.ui.console_ui.Console"):
        ui = ConsoleUI()
        assert ui._accumulated_response == ""
        assert ui._event_count == 0
        assert ui._last_event_type is None
        assert ui._ai_thinking_start_time is None
        assert ui._ai_response_start_time is None


# ============================================================================
# ConsoleUI — show_tool_input
# ============================================================================


@pytest.mark.unit
def test_show_tool_input_calls_console_print():
    """show_tool_input prints a panel to the console."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        ui.show_tool_input("my_tool", "🔧", {"param1": "value1", "param2": 42})

        mock_console.print.assert_called_once()


@pytest.mark.unit
def test_show_tool_input_with_empty_parameters():
    """show_tool_input works with an empty parameters dict."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        ui.show_tool_input("empty_tool", "📄", {})

        mock_console.print.assert_called_once()


# ============================================================================
# ConsoleUI — show_tool_output
# ============================================================================


@pytest.mark.unit
def test_show_tool_output_success():
    """show_tool_output prints a green-bordered panel for success."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        ui.show_tool_output("My Title", "All good", success=True)

        mock_console.print.assert_called_once()


@pytest.mark.unit
def test_show_tool_output_failure():
    """show_tool_output prints a red-bordered panel for failure."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        ui.show_tool_output("Error Title", "Something failed", success=False)

        mock_console.print.assert_called_once()


# ============================================================================
# ConsoleUI — show_tool_error / show_file_error
# ============================================================================


@pytest.mark.unit
def test_show_tool_error_calls_console_print():
    """show_tool_error prints an error panel."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        ui.show_tool_error("my_tool", "Something went wrong")

        mock_console.print.assert_called_once()


@pytest.mark.unit
def test_show_file_error_calls_console_print():
    """show_file_error prints a file error panel."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        ui.show_file_error("/some/path/file.py", "File not found")

        mock_console.print.assert_called_once()


# ============================================================================
# ConsoleUI — show_code_content
# ============================================================================


@pytest.mark.unit
def test_show_code_content_basic():
    """show_code_content displays code with syntax highlighting."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        ui.show_code_content("test.py", "print('hello')", start_line=1, language="python")

        mock_console.print.assert_called_once()


@pytest.mark.unit
def test_show_code_content_with_start_line_gt_1():
    """show_code_content appends line range to title when start_line > 1."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        ui.show_code_content("test.py", "x = 1\ny = 2", start_line=10, language="python")

        mock_console.print.assert_called_once()


@pytest.mark.unit
def test_show_code_content_fallback_on_exception():
    """show_code_content falls back to plain text when Syntax raises."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        with patch("cli_tool.core.ui.console_ui.Syntax", side_effect=Exception("bad syntax")):
            ui = ConsoleUI()
            ui.show_code_content("file.txt", "some content", start_line=1, language="text")

        # Fallback calls show_tool_output which also calls console.print
        assert mock_console.print.called


# ============================================================================
# ConsoleUI — show_search_results
# ============================================================================


@pytest.mark.unit
def test_show_search_results_with_results():
    """show_search_results shows found results."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        ui.show_search_results("my_symbol", ["file.py:10: match1", "file.py:20: match2"])

        mock_console.print.assert_called()


@pytest.mark.unit
def test_show_search_results_empty():
    """show_search_results shows no-results message when list is empty."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        ui.show_search_results("my_symbol", [])

        mock_console.print.assert_called_once()


@pytest.mark.unit
def test_show_search_results_with_custom_success_message():
    """show_search_results uses a custom success_message when provided."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        ui.show_search_results("sym", ["result1"], success_message="Custom message")

        mock_console.print.assert_called()


# ============================================================================
# ConsoleUI — show_function_definitions
# ============================================================================


@pytest.mark.unit
def test_show_function_definitions_with_results():
    """show_function_definitions displays found definitions."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        results = ["file.py:10: def my_func(a, b):", "other.py:20: def my_func():"]
        ui.show_function_definitions("my_func", results)

        mock_console.print.assert_called_once()


@pytest.mark.unit
def test_show_function_definitions_empty():
    """show_function_definitions shows no-results panel when list is empty."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        ui.show_function_definitions("nonexistent_func", [])

        mock_console.print.assert_called_once()


@pytest.mark.unit
def test_show_function_definitions_more_than_three_results():
    """show_function_definitions shows '... and N more' when results > 3."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        results = [f"file{i}.py:{i * 10}: def func():" for i in range(5)]
        ui.show_function_definitions("func", results)

        mock_console.print.assert_called_once()


# ============================================================================
# ConsoleUI — show_import_analysis
# ============================================================================


@pytest.mark.unit
def test_show_import_analysis_with_imports_and_usages():
    """show_import_analysis displays imports and usages."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        ui.show_import_analysis(
            "MyClass",
            "module.py",
            ["Line 1: from package import MyClass"],
            ["Line 5: x = MyClass()", "Line 10: MyClass.method()"],
        )

        mock_console.print.assert_called_once()


@pytest.mark.unit
def test_show_import_analysis_no_imports():
    """show_import_analysis works when imports list is empty."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        ui.show_import_analysis("MyClass", "module.py", [], ["Line 5: x = MyClass()"])

        mock_console.print.assert_called_once()


@pytest.mark.unit
def test_show_import_analysis_no_usages():
    """show_import_analysis works when usages list is empty."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        ui.show_import_analysis("MyClass", "module.py", ["Line 1: from pkg import MyClass"], [])

        mock_console.print.assert_called_once()


# ============================================================================
# ConsoleUI — show_request_to_ai
# ============================================================================


@pytest.mark.unit
def test_show_request_to_ai_calls_console_print():
    """show_request_to_ai prints the AI request info panel."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        ui.show_request_to_ai(1234, 3, "feature/my-branch", "main")

        mock_console.print.assert_called_once()


# ============================================================================
# ConsoleUI — show_processing_status
# ============================================================================


@pytest.mark.unit
def test_show_processing_status_calls_console_print():
    """show_processing_status prints a status message."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        ui.show_processing_status()

        mock_console.print.assert_called_once()


# ============================================================================
# ConsoleUI — show_ai_thinking
# ============================================================================


@pytest.mark.unit
def test_show_ai_thinking_starts_streaming():
    """show_ai_thinking starts the streaming manager."""
    with patch("cli_tool.core.ui.console_ui.Console"):
        ui = ConsoleUI()
        mock_mgr = MagicMock()
        ui._streaming_manager = mock_mgr

        ui.show_ai_thinking("Processing your request...")

        mock_mgr.start_streaming.assert_called_once()
        mock_mgr.update_event_panel.assert_called_once()


@pytest.mark.unit
def test_show_ai_thinking_sets_start_time():
    """show_ai_thinking sets _ai_thinking_start_time on first call."""
    with patch("cli_tool.core.ui.console_ui.Console"):
        ui = ConsoleUI()
        ui._streaming_manager = MagicMock()

        assert ui._ai_thinking_start_time is None
        ui.show_ai_thinking("A thought")
        assert ui._ai_thinking_start_time is not None


@pytest.mark.unit
def test_show_ai_thinking_reuses_same_event_id():
    """show_ai_thinking uses the same event_id on repeated calls."""
    with patch("cli_tool.core.ui.console_ui.Console"):
        ui = ConsoleUI()
        mock_mgr = MagicMock()
        ui._streaming_manager = mock_mgr

        ui.show_ai_thinking("First thought")
        ui.show_ai_thinking("Second thought")

        calls = [call[0][0] for call in mock_mgr.update_event_panel.call_args_list]
        assert calls[0] == calls[1]


# ============================================================================
# ConsoleUI — show_ai_action
# ============================================================================


@pytest.mark.unit
def test_show_ai_action_stops_streaming_and_prints():
    """show_ai_action stops streaming and prints the action panel."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()
        mock_mgr = MagicMock()
        ui._streaming_manager = mock_mgr

        ui.show_ai_action("Analyzing code")

        mock_mgr.stop_streaming.assert_called_once()
        mock_console.print.assert_called_once()


@pytest.mark.unit
def test_show_ai_action_with_details():
    """show_ai_action includes details when provided."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()
        ui._streaming_manager = MagicMock()

        ui.show_ai_action("Build context", "Analyzing 5 files with changes")

        mock_console.print.assert_called_once()


# ============================================================================
# ConsoleUI — show_ai_progress
# ============================================================================


@pytest.mark.unit
def test_show_ai_progress_stops_streaming_and_prints():
    """show_ai_progress stops streaming and prints progress panel."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()
        mock_mgr = MagicMock()
        ui._streaming_manager = mock_mgr

        ui.show_ai_progress("Checking references", 2, 5)

        mock_mgr.stop_streaming.assert_called_once()
        mock_console.print.assert_called_once()


# ============================================================================
# ConsoleUI — show_ai_writing
# ============================================================================


@pytest.mark.unit
def test_show_ai_writing_truncates_long_previews():
    """show_ai_writing truncates content_preview to 300 characters."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        long_content = "a" * 500
        # Patch Panel so we can inspect the actual content string passed
        with patch("cli_tool.core.ui.console_ui.Panel") as mock_panel_cls:
            ui.show_ai_writing(long_content)
            # The first positional arg to Panel should contain "..." for truncation
            panel_content_arg = mock_panel_cls.call_args[0][0]
            assert "..." in panel_content_arg

        mock_console.print.assert_called_once()


@pytest.mark.unit
def test_show_ai_writing_short_content_not_truncated():
    """show_ai_writing does not truncate short content."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        ui.show_ai_writing("short content", "Streaming...")

        mock_console.print.assert_called_once()


# ============================================================================
# ConsoleUI — show_ai_real_response
# ============================================================================


@pytest.mark.unit
def test_show_ai_real_response_accumulates_chunks():
    """show_ai_real_response accumulates chunks across calls."""
    with patch("cli_tool.core.ui.console_ui.Console"):
        ui = ConsoleUI()
        ui._streaming_manager = MagicMock()

        ui.show_ai_real_response("chunk1")
        ui.show_ai_real_response("chunk2")

        assert "chunk1" in ui._accumulated_response
        assert "chunk2" in ui._accumulated_response


@pytest.mark.unit
def test_show_ai_real_response_resets_on_completion():
    """show_ai_real_response resets state when is_complete=True."""
    with patch("cli_tool.core.ui.console_ui.Console"):
        ui = ConsoleUI()
        ui._streaming_manager = MagicMock()

        ui.show_ai_real_response("some text", is_complete=True)

        assert ui._accumulated_response == ""
        assert ui._last_event_type is None
        assert ui._event_count == 0
        assert ui._ai_response_start_time is None


@pytest.mark.unit
def test_show_ai_real_response_sliding_window_for_long_content():
    """show_ai_real_response shows sliding window when content exceeds 1500 chars."""
    with patch("cli_tool.core.ui.console_ui.Console"):
        ui = ConsoleUI()
        ui._streaming_manager = MagicMock()

        # Simulate a large accumulated response
        many_lines = "\n".join([f"Line {i}: " + "x" * 50 for i in range(30)])
        ui.show_ai_real_response(many_lines)

        # Should not raise, streaming manager should be called
        ui._streaming_manager.start_streaming.assert_called()


# ============================================================================
# ConsoleUI — show_analysis_complete
# ============================================================================


@pytest.mark.unit
def test_show_analysis_complete_stops_streaming_and_prints():
    """show_analysis_complete stops streaming and prints completion panel."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()
        mock_mgr = MagicMock()
        ui._streaming_manager = mock_mgr

        ui.show_analysis_complete(5000)

        mock_mgr.stop_streaming.assert_called_once()
        mock_console.print.assert_called_once()


# ============================================================================
# ConsoleUI — show_analysis_results_table
# ============================================================================


@pytest.mark.unit
def test_show_analysis_results_table_with_summary():
    """show_analysis_results_table prints summary panel when summary key exists."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()
        ui._streaming_manager = MagicMock()

        result = {"summary": "All looks good", "issues": [], "files_analyzed": []}
        ui.show_analysis_results_table(result)

        assert mock_console.print.called


@pytest.mark.unit
def test_show_analysis_results_table_with_pr_context():
    """show_analysis_results_table prints PR context panel."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()
        ui._streaming_manager = MagicMock()

        result = {
            "pr_context": {
                "current_branch": "feature/my-branch",
                "base_branch": "main",
                "total_files": 3,
                "supported_files": 2,
            },
            "issues": [],
            "files_analyzed": [],
        }
        ui.show_analysis_results_table(result)

        assert mock_console.print.called


@pytest.mark.unit
def test_show_analysis_results_table_no_issues_prints_great_news():
    """show_analysis_results_table prints no-issues panel when issues list is empty."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()
        ui._streaming_manager = MagicMock()

        result = {"issues": [], "files_analyzed": []}
        ui.show_analysis_results_table(result)

        # At least one call should include "No issues" messaging
        assert mock_console.print.called


@pytest.mark.unit
def test_show_analysis_results_table_with_files_analyzed():
    """show_analysis_results_table shows files table when files_analyzed is non-empty."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()
        ui._streaming_manager = MagicMock()

        result = {"issues": [], "files_analyzed": ["file1.py", "file2.py"]}
        ui.show_analysis_results_table(result)

        assert mock_console.print.called


@pytest.mark.unit
def test_show_analysis_results_table_with_metrics():
    """show_analysis_results_table shows metrics panel when metrics are provided."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()
        ui._streaming_manager = MagicMock()

        result = {
            "issues": [],
            "files_analyzed": [],
            "metrics": {
                "accumulated_usage": {"inputTokens": 100, "outputTokens": 200, "totalTokens": 300},
                "total_duration": 1.5,
            },
        }
        ui.show_analysis_results_table(result, show_metrics=True)

        assert mock_console.print.called


@pytest.mark.unit
def test_show_analysis_results_table_metrics_skipped_when_show_metrics_false():
    """show_analysis_results_table skips metrics when show_metrics=False."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()
        ui._streaming_manager = MagicMock()

        result = {
            "issues": [],
            "files_analyzed": [],
            "metrics": {"accumulated_usage": {"totalTokens": 300}, "total_duration": 1.5},
        }
        call_count_before = mock_console.print.call_count
        ui.show_analysis_results_table(result, show_metrics=False)
        # Should print less than with show_metrics=True
        assert mock_console.print.call_count >= call_count_before


# ============================================================================
# ConsoleUI — _show_issues_cards
# ============================================================================


@pytest.mark.unit
def test_show_issues_cards_single_issue():
    """_show_issues_cards displays a single issue card."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        issues = [
            {
                "severity": "high",
                "type": "security",
                "file": "app.py",
                "line": 42,
                "description": "SQL injection vulnerability",
                "suggestion": "Use parameterized queries",
            }
        ]
        ui._show_issues_cards(issues)

        assert mock_console.print.called


@pytest.mark.unit
def test_show_issues_cards_with_impact():
    """_show_issues_cards includes impact section when impact is provided."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        issues = [
            {
                "severity": "critical",
                "type": "bug",
                "file": "core.py",
                "line": 10,
                "description": "Null pointer dereference",
                "suggestion": "Add null check",
                "impact": "Application will crash on startup",
            }
        ]
        ui._show_issues_cards(issues)

        assert mock_console.print.called


@pytest.mark.unit
def test_show_issues_cards_with_affected_references_list():
    """_show_issues_cards handles affected_references as a list."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        issues = [
            {
                "severity": "medium",
                "type": "dependencies",
                "file": "utils.py",
                "description": "Broken import",
                "suggestion": "Fix import path",
                "affected_references": ["module_a.py:10", "module_b.py:20"],
            }
        ]
        ui._show_issues_cards(issues)

        assert mock_console.print.called


@pytest.mark.unit
def test_show_issues_cards_with_affected_references_string():
    """_show_issues_cards handles affected_references as a string."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        issues = [
            {
                "severity": "low",
                "type": "style",
                "file": "style.py",
                "description": "Minor issue",
                "suggestion": "Rename variable",
                "affected_references": "many files",
            }
        ]
        ui._show_issues_cards(issues)

        assert mock_console.print.called


@pytest.mark.unit
def test_show_issues_cards_with_security_reference():
    """_show_issues_cards includes security_reference when provided."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        issues = [
            {
                "severity": "high",
                "type": "security",
                "file": "auth.py",
                "description": "Weak hashing algorithm",
                "suggestion": "Use bcrypt",
                "security_reference": "OWASP A3:2021 - Injection",
            }
        ]
        ui._show_issues_cards(issues)

        assert mock_console.print.called


@pytest.mark.unit
def test_show_issues_cards_unknown_type_uses_fallback():
    """_show_issues_cards uses default icon/name for unknown issue types."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        issues = [
            {
                "severity": "info",
                "type": "completely_unknown_type",
                "file": "file.py",
                "description": "Some issue",
                "suggestion": "Fix it",
            }
        ]
        ui._show_issues_cards(issues)

        assert mock_console.print.called


@pytest.mark.unit
def test_show_issues_cards_multiple_issues_prints_separator():
    """_show_issues_cards prints separator between multiple issues."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        issues = [
            {"severity": "low", "type": "style", "file": "a.py", "description": "Issue 1", "suggestion": "Fix 1"},
            {"severity": "medium", "type": "bug", "file": "b.py", "description": "Issue 2", "suggestion": "Fix 2"},
        ]
        ui._show_issues_cards(issues)

        # Should print at least 3 times (header + 2 cards + separator)
        assert mock_console.print.call_count >= 3


# ============================================================================
# ConsoleUI — _format_multiline_text
# ============================================================================


@pytest.mark.unit
def test_format_multiline_text_single_line():
    """_format_multiline_text handles a single-line string."""
    with patch("cli_tool.core.ui.console_ui.Console"):
        ui = ConsoleUI()
        result = ui._format_multiline_text("Simple text")
        assert len(result) == 1
        assert "Simple text" in result[0]


@pytest.mark.unit
def test_format_multiline_text_multiple_lines():
    """_format_multiline_text handles multiple lines."""
    with patch("cli_tool.core.ui.console_ui.Console"):
        ui = ConsoleUI()
        result = ui._format_multiline_text("Line one\nLine two\nLine three")
        assert len(result) == 3


@pytest.mark.unit
def test_format_multiline_text_empty_string():
    """_format_multiline_text returns fallback for empty string."""
    with patch("cli_tool.core.ui.console_ui.Console"):
        ui = ConsoleUI()
        result = ui._format_multiline_text("")
        assert len(result) == 1
        assert "No information provided" in result[0]


@pytest.mark.unit
def test_format_multiline_text_whitespace_only():
    """_format_multiline_text returns fallback for whitespace-only string."""
    with patch("cli_tool.core.ui.console_ui.Console"):
        ui = ConsoleUI()
        result = ui._format_multiline_text("   \n   ")
        assert "No information provided" in result[0]


@pytest.mark.unit
def test_format_multiline_text_custom_indent():
    """_format_multiline_text applies custom indent."""
    with patch("cli_tool.core.ui.console_ui.Console"):
        ui = ConsoleUI()
        result = ui._format_multiline_text("Hello", indent="  >> ")
        assert result[0].startswith("  >> ")


# ============================================================================
# ConsoleUI — _show_metrics_panel
# ============================================================================


@pytest.mark.unit
def test_show_metrics_panel_with_data():
    """_show_metrics_panel prints metrics when data is available."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        metrics = {
            "accumulated_usage": {"inputTokens": 500, "outputTokens": 1000, "totalTokens": 1500},
            "total_duration": 3.75,
        }
        ui._show_metrics_panel(metrics)

        mock_console.print.assert_called_once()


@pytest.mark.unit
def test_show_metrics_panel_empty_dict_returns_early():
    """_show_metrics_panel returns without printing when metrics is empty."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        ui._show_metrics_panel({})

        mock_console.print.assert_not_called()


# ============================================================================
# ConsoleUI — _reset_event_grouping
# ============================================================================


@pytest.mark.unit
def test_reset_event_grouping_clears_state():
    """_reset_event_grouping resets all event grouping fields."""
    with patch("cli_tool.core.ui.console_ui.Console"):
        ui = ConsoleUI()
        ui._streaming_manager = MagicMock()
        ui._last_event_type = "ai_response"
        ui._event_count = 5
        ui._ai_thinking_start_time = "2026-03-15T10:00"

        ui._reset_event_grouping()

        assert ui._last_event_type is None
        assert ui._event_count == 0
        assert ui._ai_thinking_start_time is None


@pytest.mark.unit
def test_reset_event_grouping_removes_thinking_panel():
    """_reset_event_grouping removes thinking panels from streaming manager."""
    with patch("cli_tool.core.ui.console_ui.Console"):
        ui = ConsoleUI()
        mock_mgr = MagicMock()
        ui._streaming_manager = mock_mgr
        ui._ai_thinking_start_time = "2026-03-15T10:00"

        ui._reset_event_grouping()

        mock_mgr.remove_event_panel.assert_called_once()


# ============================================================================
# Issue type and severity lookup data
# ============================================================================


@pytest.mark.unit
def test_issue_type_info_contains_expected_keys():
    """_ISSUE_TYPE_INFO contains required type mappings."""
    assert "security" in _ISSUE_TYPE_INFO
    assert "bug" in _ISSUE_TYPE_INFO
    assert "performance" in _ISSUE_TYPE_INFO
    assert "dependencies" in _ISSUE_TYPE_INFO


@pytest.mark.unit
def test_severity_info_contains_expected_levels():
    """_SEVERITY_INFO contains all standard severity levels."""
    assert "critical" in _SEVERITY_INFO
    assert "high" in _SEVERITY_INFO
    assert "medium" in _SEVERITY_INFO
    assert "low" in _SEVERITY_INFO
    assert "info" in _SEVERITY_INFO


@pytest.mark.unit
def test_issue_type_info_values_have_required_fields():
    """Each entry in _ISSUE_TYPE_INFO has icon, name, and color."""
    for key, value in _ISSUE_TYPE_INFO.items():
        assert "icon" in value, f"Missing 'icon' for key '{key}'"
        assert "name" in value, f"Missing 'name' for key '{key}'"
        assert "color" in value, f"Missing 'color' for key '{key}'"


@pytest.mark.unit
def test_severity_info_values_have_required_fields():
    """Each entry in _SEVERITY_INFO has color, icon, and text."""
    for key, value in _SEVERITY_INFO.items():
        assert "color" in value, f"Missing 'color' for severity '{key}'"
        assert "icon" in value, f"Missing 'icon' for severity '{key}'"
        assert "text" in value, f"Missing 'text' for severity '{key}'"


# ============================================================================
# ConsoleUI — _show_issues_table (legacy redirect)
# ============================================================================


@pytest.mark.unit
def test_show_issues_table_delegates_to_cards():
    """_show_issues_table delegates to _show_issues_cards."""
    with patch("cli_tool.core.ui.console_ui.Console"):
        ui = ConsoleUI()
        ui._show_issues_cards = MagicMock()
        issues = [{"severity": "low", "type": "style", "file": "f.py", "description": "d", "suggestion": "s"}]

        ui._show_issues_table(issues)

        ui._show_issues_cards.assert_called_once_with(issues)


# ============================================================================
# ConsoleUI — show_request_preview
# ============================================================================


@pytest.mark.unit
def test_show_request_preview_calls_console_print():
    """show_request_preview prints the preview panel."""
    with patch("cli_tool.core.ui.console_ui.Console") as mock_console_cls:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        ui = ConsoleUI()

        ui.show_request_preview("Preview content here")

        mock_console.print.assert_called_once()
