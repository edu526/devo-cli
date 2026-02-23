"""
UI Components for displaying tool interactions and results.
"""

from datetime import datetime
from typing import Any, Dict, List

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table


class StreamingDisplayManager:
    """Manages streaming display with event panels similar to Marvin's approach."""

    def __init__(self, console: Console):
        self.console = console
        self.live_display = None
        self.event_panels = {}  # Store panels by stable event ID
        self.is_active = False

    def start_streaming(self):
        """Start the live display for streaming updates."""
        if not self.is_active:
            self.live_display = Live(
                Group(*self.event_panels.values()) if self.event_panels else "",
                console=self.console,
                auto_refresh=True,
                refresh_per_second=10,
            )
            self.live_display.start()
            self.is_active = True

    def stop_streaming(self):
        """Stop the live display and clear panels."""
        if self.is_active and self.live_display:
            self.live_display.stop()
            self.live_display = None
            self.is_active = False
            self.event_panels.clear()

    def update_event_panel(self, event_id: str, panel: Panel):
        """Update or create an event panel with stable ID."""
        self.event_panels[event_id] = panel

        if self.is_active and self.live_display:
            # Update the live display with all current panels
            self.live_display.update(Group(*self.event_panels.values()), refresh=True)

    def remove_event_panel(self, event_id: str):
        """Remove an event panel."""
        if event_id in self.event_panels:
            del self.event_panels[event_id]
            if self.is_active and self.live_display:
                self.live_display.update(Group(*self.event_panels.values()), refresh=True)


class ConsoleUI:
    """Handles Rich-based UI components for tool interactions."""

    def __init__(self):
        self.console = Console()
        # State for grouping continuous events
        self._last_event_type = None
        self._accumulated_response = ""
        self._event_count = 0
        self._last_panel_content = None
        # Streaming display manager
        self._streaming_manager = StreamingDisplayManager(self.console)
        # Track AI thinking events with timestamps for stable IDs
        self._ai_thinking_start_time = None
        self._ai_response_start_time = None

    def show_tool_input(self, tool_name: str, icon: str, parameters: Dict[str, Any]):
        """Display tool input parameters in a formatted panel."""
        params_text = "\n".join([f"• {key}: [green]'{value}'[/green]" for key, value in parameters.items()])

        self.console.print(
            Panel(
                f"[bold cyan]{icon} {tool_name}[/bold cyan]\n\n" f"[yellow]Parameters:[/yellow]\n" f"{params_text}",
                title="📥 Tool Input",
                border_style="blue",
            )
        )

    def show_tool_output(self, title: str, content: str, success: bool = True):
        """Display generic tool output in a formatted panel."""
        border_style = "green" if success else "red"
        icon = "✅" if success else "❌"

        self.console.print(
            Panel(
                f"{icon} {content}",
                title=f"📤 Tool Output - {title}",
                border_style=border_style,
            )
        )

    def show_tool_error(self, tool_name: str, error_message: str):
        """Display tool error in a formatted panel."""
        self.console.print(
            Panel(
                f"❌ Error in {tool_name}: {error_message}",
                title="📤 Tool Output - Error",
                border_style="red",
            )
        )

    def show_file_error(self, file_path: str, error_message: str):
        """Display file-related error in a formatted panel."""
        self.console.print(
            Panel(
                f"📄 File: {file_path}\n❌ {error_message}",
                title="📤 Tool Output - File Error",
                border_style="red",
            )
        )

    def show_code_content(self, file_path: str, content: str, start_line: int = 1, language: str = "text"):
        """Display code content with syntax highlighting."""
        try:
            syntax = Syntax(content, language, line_numbers=True, start_line=start_line)
            title = "📄 Tool Output - {}".format(file_path)
            if start_line > 1:
                # Calculate end line based on content
                line_count = len(content.split("\n"))
                end_line = start_line + line_count - 1
                title += " (lines {}-{})".format(start_line, end_line)

            self.console.print(Panel(syntax, title=title, border_style="green"))
        except Exception:
            # Fallback to plain text if syntax highlighting fails
            self.show_tool_output("{} (lines {}+)".format(file_path, start_line), content)

    def show_search_results(self, symbol_name: str, results: list, success_message: str = None):
        """Display search results in a formatted way."""
        if results:
            output_text = success_message or "✅ Success"
            output_text += "\n\n"
            for result in results:
                output_text += "{}\n".format(result)

            self.show_tool_output("Search Results", output_text.strip())
        else:
            self.show_tool_output(
                "No Results",
                f"No references found for '{symbol_name}' (search completed successfully)",
                success=True,
            )

    def show_function_definitions(self, function_name: str, results: list):
        """Display function definition search results."""
        if results:
            output_text = f"Found {len(results)} definition(s) for '{function_name}'\n\n"
            for i, result in enumerate(results[:3], 1):
                lines = result.strip().split("\n")
                for line in lines[:2]:
                    if ":" in line:
                        file_part, content = line.split(":", 1)
                        output_text += f"📍 {file_part}: {content[:80]}{'...' if len(content) > 80 else ''}\n"
            if len(results) > 3:
                output_text += f"\n... and {len(results) - 3} more definitions"

            self.show_tool_output("Function Definitions Found", output_text.strip())
        else:
            self.show_tool_output(
                "No Results",
                f"✅ No definitions found for '{function_name}' (search completed successfully)",
                success=True,
            )

    def show_import_analysis(self, symbol_name: str, file_path: str, imports: list, usages: list):
        """Display import and usage analysis."""
        output_text = f"Analysis of '{symbol_name}' in {file_path}\n\n"

        if imports:
            output_text += f"📥 Imports ({len(imports)}):\n"
            for imp in imports[:3]:
                output_text += f"   {imp}\n"
            if len(imports) > 3:
                output_text += f"   ... and {len(imports) - 3} more imports\n"
        else:
            output_text += f"📥 No imports found for '{symbol_name}'\n"

        if usages:
            output_text += f"\n🔍 Usages ({len(usages)}):\n"
            for usage in usages:
                output_text += f"   {usage}\n"
            # if len(usages) > 5:
            # output_text += f"   ... and {len(usages) - 5} more usages\n"
        else:
            output_text += f"\n🔍 No usages found for '{symbol_name}'\n"

        self.show_tool_output("Import & Usage Analysis", output_text.strip())

    def show_request_to_ai(
        self,
        request_length: int,
        files_count: int,
        current_branch: str,
        base_branch: str,
    ):
        """Display AI request information panel."""
        self.console.print(
            Panel(
                f"🤖 Sending Analysis Request to AI Agent\n\n"
                f"📊 Request length: {request_length:,} characters\n"
                f"📁 Files to analyze: {files_count}\n"
                f"🔄 Current branch: {current_branch}\n"
                f"🎯 Base branch: {base_branch}",
                title="🧠 Request to AI",
                border_style="cyan",
            )
        )

    def show_request_preview(self, preview_content: str):
        """Display request preview panel."""
        self.console.print(Panel(preview_content, title="📋 Request Preview", border_style="blue"))

    def show_processing_status(self):
        """Display processing status."""
        self.console.print("\n🔄 [bold yellow]AI is processing the request...[/bold yellow]\n")

    def show_ai_thinking(self, thought: str):
        """Display AI thinking process in real-time using streaming panels."""
        # Create stable event ID based on start time and event type
        if self._ai_thinking_start_time is None:
            self._ai_thinking_start_time = datetime.now().isoformat(timespec="minutes")

        event_id = f"ai_thinking_{self._ai_thinking_start_time}"

        # Start streaming if not already active
        self._streaming_manager.start_streaming()

        # Create the panel with current thought
        panel = Panel(f"💭 {thought}", title="🧠 AI Thinking", border_style="cyan", padding=(0, 1))

        # Update the streaming panel
        self._streaming_manager.update_event_panel(event_id, panel)

    def _reset_event_grouping(self):
        """Reset event grouping state and clear thinking panels."""
        # Remove any existing thinking panels
        if hasattr(self, "_ai_thinking_start_time") and self._ai_thinking_start_time:
            thinking_event_id = f"ai_thinking_{self._ai_thinking_start_time}"
            self._streaming_manager.remove_event_panel(thinking_event_id)

        # Reset all state
        self._last_event_type = None
        self._event_count = 0
        self._ai_thinking_start_time = None

    def show_ai_action(self, action: str, details: str = ""):
        """Display what action the AI is taking."""
        # Stop streaming and reset grouping for important actions
        self._streaming_manager.stop_streaming()
        self._reset_event_grouping()

        content = f"🎯 {action}"
        if details:
            content += f"\n\n📋 {details}"

        self.console.print(Panel(content, title="🤖 AI Action", border_style="blue", padding=(0, 1)))

    def show_ai_progress(self, step: str, current: int, total: int):
        """Display AI progress through analysis steps."""
        # Stop streaming and reset grouping for progress updates
        self._streaming_manager.stop_streaming()
        self._reset_event_grouping()

        progress_bar = "█" * current + "░" * (total - current)
        self.console.print(
            Panel(
                f"📊 Step {current}/{total}: {step}\n\n" f"Progress: [{progress_bar}] {current}/{total}",
                title="⚡ AI Progress",
                border_style="green",
                padding=(0, 1),
            )
        )

    def show_ai_writing(self, content_preview: str, writing_status: str = "Writing analysis..."):
        """Display AI writing process with content preview."""
        # Truncate preview if too long
        if len(content_preview) > 300:
            content_preview = content_preview[:300] + "..."

        self.console.print(
            Panel(
                f"✍️ {writing_status}\n\n" f"📝 Current output:\n{content_preview}",
                title="📄 AI Writing in Real-Time",
                border_style="yellow",
                padding=(0, 1),
            )
        )

    def show_ai_real_response(self, response_chunk: str, is_complete: bool = False):
        """Show real AI response as it's being generated using streaming panels."""
        # Create stable event ID based on start time
        if self._ai_response_start_time is None:
            self._ai_response_start_time = datetime.now().isoformat(timespec="minutes")

        event_id = f"ai_response_{self._ai_response_start_time}"

        # Accumulate response chunks
        if self._last_event_type != "ai_response":
            self._accumulated_response = ""
            self._event_count = 0

        self._accumulated_response += response_chunk
        self._event_count += 1
        self._last_event_type = "ai_response"

        # Prepare display content
        status = "✅ Complete" if is_complete else f"⏳ Generating... ({self._event_count} chunks)"

        # For long content during streaming, show a sliding window to keep new content visible
        display_content = self._accumulated_response
        if not is_complete and len(display_content) > 1500:
            # Split into lines and show recent content + indicator
            lines = display_content.split("\n")
            char_count = len(display_content)

            if len(lines) > 20:
                # Show only the last 20 lines during streaming
                recent_lines = lines[-20:]
                hidden_lines = len(lines) - 20

                display_content = f"... ({hidden_lines} previous lines, {char_count:,} chars total) ...\n\n" + "\n".join(recent_lines)

        # Create the panel
        panel = Panel(
            f"🤖 {status}\n\n{display_content}",
            title="🧠 Live AI Response",
            border_style="yellow",
            padding=(0, 1),
        )

        if is_complete:
            # Update the final panel one last time and then stop streaming
            self._streaming_manager.start_streaming()  # Ensure streaming is active
            self._streaming_manager.update_event_panel(event_id, panel)
            # Stop streaming after a brief moment to show the final state
            self._streaming_manager.stop_streaming()
            # Reset state
            self._accumulated_response = ""
            self._last_event_type = None
            self._event_count = 0
            self._ai_response_start_time = None
        else:
            # Start streaming if not already active
            self._streaming_manager.start_streaming()
            # Update the streaming panel
            self._streaming_manager.update_event_panel(event_id, panel)

    def show_analysis_complete(self, response_length: int):
        """Display analysis completion panel."""
        # Stop any active streaming
        self._streaming_manager.stop_streaming()
        self._reset_event_grouping()

        self.console.print(
            Panel(
                f"🎯 AI Analysis Completed!\n\n" f"📝 Response length: {response_length:,} characters\n" f"📊 Processing JSON response...",
                title="✅ Analysis Complete",
                border_style="green",
            )
        )

    def show_analysis_results_table(self, analysis_result: Dict[str, Any], show_metrics: bool = True):
        """Display analysis results in a rich table format."""
        # Stop any active streaming
        self._streaming_manager.stop_streaming()
        self._reset_event_grouping()

        # Show summary
        if "summary" in analysis_result:
            self.console.print(
                Panel(
                    analysis_result["summary"],
                    title="📋 Analysis Summary",
                    border_style="cyan",
                )
            )

        # Show PR context
        if "pr_context" in analysis_result:
            context = analysis_result["pr_context"]
            context_info = (
                f"🔄 Current branch: [bold green]{context.get('current_branch', 'N/A')}[/bold green]\n"
                f"🎯 Base branch: [bold blue]{context.get('base_branch', 'N/A')}[/bold blue]\n"
                f"📁 Total files changed: {context.get('total_files', 0)}\n"
                f"📄 Supported files analyzed: {context.get('supported_files', 0)}"
            )
            self.console.print(Panel(context_info, title="📊 PR Context", border_style="blue"))

        # Show issues in cards format
        issues = analysis_result.get("issues", [])
        if issues:
            self._show_issues_cards(issues)
        else:
            self.console.print(
                Panel(
                    "✅ No issues found in the analysis!",
                    title="🎉 Great News!",
                    border_style="green",
                )
            )

        # Show files analyzed
        files_analyzed = analysis_result.get("files_analyzed", [])
        if files_analyzed:
            self._show_files_analyzed_table(files_analyzed)

        # Show metrics if available and requested
        metrics = analysis_result.get("metrics", {})
        if metrics and show_metrics:
            self._show_metrics_panel(metrics)

    def _format_multiline_text(self, text: str, indent: str = "   ") -> List[str]:
        """
        Format multiline text with consistent indentation.

        Args:
            text: The text to format (may contain multiple lines)
            indent: The indentation string to use for each line

        Returns:
            List of formatted lines with proper indentation
        """
        if not text or not text.strip():
            return [f"{indent}No information provided"]

        lines = text.strip().split("\n")
        formatted_lines = []

        for i, line in enumerate(lines):
            clean_line = line.strip()
            if clean_line:
                formatted_lines.append(f"{indent}{clean_line}")
            elif i > 0 and i < len(lines) - 1:
                # Only add empty lines if they're between content lines (not at start/end)
                # This creates proper spacing between sections
                next_lines_have_content = any(lines[j].strip() for j in range(i + 1, len(lines)))
                if next_lines_have_content:
                    formatted_lines.append("")

        return formatted_lines

    def _show_issues_cards(self, issues: List[Dict[str, Any]]):
        """Display issues as individual cards for better readability."""
        self.console.print(f"\n[bold magenta]🚨 Issues Found ({len(issues)} total)[/bold magenta]\n")

        for i, issue in enumerate(issues, 1):
            # Get severity color and style
            severity = issue.get("severity", "unknown").lower()
            severity_info = {
                "critical": {"color": "bold red", "icon": "🔴", "text": "CRITICAL"},
                "high": {"color": "red", "icon": "🟠", "text": "HIGH"},
                "medium": {"color": "yellow", "icon": "🟡", "text": "MEDIUM"},
                "low": {"color": "green", "icon": "🟢", "text": "LOW"},
                "info": {"color": "blue", "icon": "🔵", "text": "INFO"},
            }.get(severity, {"color": "white", "icon": "⚪", "text": severity.upper()})

            # Get issue type with icon - normalize the type for better matching
            issue_type = issue.get("type", "unknown").lower()
            issue_type_normalized = issue_type.replace(" ", "").replace("_", "").replace("-", "")

            type_info = {
                # Dependencies
                "dependencies": {"icon": "📦", "name": "Dependencies", "color": "cyan"},
                "dependency": {"icon": "📦", "name": "Dependencies", "color": "cyan"},
                "import": {"icon": "📦", "name": "Dependencies", "color": "cyan"},
                "imports": {"icon": "📦", "name": "Dependencies", "color": "cyan"},
                "missingimport": {
                    "icon": "📦",
                    "name": "Dependencies",
                    "color": "cyan",
                },
                "unusedimport": {"icon": "📦", "name": "Dependencies", "color": "cyan"},
                "invalidimport": {
                    "icon": "📦",
                    "name": "Dependencies",
                    "color": "cyan",
                },
                "package": {"icon": "📦", "name": "Dependencies", "color": "cyan"},
                "packages": {"icon": "📦", "name": "Dependencies", "color": "cyan"},
                # Broken references
                "brokenreferences": {
                    "icon": "🔗",
                    "name": "Broken References",
                    "color": "red",
                },
                "brokenreference": {
                    "icon": "🔗",
                    "name": "Broken References",
                    "color": "red",
                },
                "reference": {
                    "icon": "🔗",
                    "name": "Broken References",
                    "color": "red",
                },
                "references": {
                    "icon": "🔗",
                    "name": "Broken References",
                    "color": "red",
                },
                "undefined": {
                    "icon": "🔗",
                    "name": "Broken References",
                    "color": "red",
                },
                "notfound": {"icon": "🔗", "name": "Broken References", "color": "red"},
                "missing": {"icon": "🔗", "name": "Broken References", "color": "red"},
                # Code quality
                "codequality": {
                    "icon": "✨",
                    "name": "Code Quality",
                    "color": "magenta",
                },
                "quality": {"icon": "✨", "name": "Code Quality", "color": "magenta"},
                "unused": {"icon": "✨", "name": "Code Quality", "color": "magenta"},
                "unusedvariable": {
                    "icon": "✨",
                    "name": "Code Quality",
                    "color": "magenta",
                },
                "redundant": {"icon": "✨", "name": "Code Quality", "color": "magenta"},
                "errorhandling": {
                    "icon": "✨",
                    "name": "Code Quality",
                    "color": "magenta",
                },
                "asyncawait": {
                    "icon": "✨",
                    "name": "Code Quality",
                    "color": "magenta",
                },
                "async": {"icon": "✨", "name": "Code Quality", "color": "magenta"},
                # Security
                "security": {"icon": "🔒", "name": "Security", "color": "red"},
                "securityissue": {"icon": "🔒", "name": "Security", "color": "red"},
                "secret": {"icon": "🔒", "name": "Security", "color": "red"},
                "secrets": {"icon": "🔒", "name": "Security", "color": "red"},
                "eval": {"icon": "🔒", "name": "Security", "color": "red"},
                "injection": {"icon": "🔒", "name": "Security", "color": "red"},
                "validation": {"icon": "🔒", "name": "Security", "color": "red"},
                "unsafe": {"icon": "🔒", "name": "Security", "color": "red"},
                # Best practices
                "bestpractices": {
                    "icon": "📋",
                    "name": "Best Practices",
                    "color": "blue",
                },
                "bestpractice": {
                    "icon": "📋",
                    "name": "Best Practices",
                    "color": "blue",
                },
                "maintainability": {
                    "icon": "📋",
                    "name": "Best Practices",
                    "color": "blue",
                },
                "readability": {
                    "icon": "📋",
                    "name": "Best Practices",
                    "color": "blue",
                },
                "naming": {"icon": "📋", "name": "Best Practices", "color": "blue"},
                "namingconvention": {
                    "icon": "📋",
                    "name": "Best Practices",
                    "color": "blue",
                },
                "consistency": {
                    "icon": "📋",
                    "name": "Best Practices",
                    "color": "blue",
                },
                "convention": {"icon": "📋", "name": "Best Practices", "color": "blue"},
                # Performance
                "performance": {"icon": "⚡", "name": "Performance", "color": "yellow"},
                "perf": {"icon": "⚡", "name": "Performance", "color": "yellow"},
                "loop": {"icon": "⚡", "name": "Performance", "color": "yellow"},
                "loops": {"icon": "⚡", "name": "Performance", "color": "yellow"},
                "duplicate": {"icon": "⚡", "name": "Performance", "color": "yellow"},
                "query": {"icon": "⚡", "name": "Performance", "color": "yellow"},
                "expensive": {"icon": "⚡", "name": "Performance", "color": "yellow"},
                "optimization": {
                    "icon": "⚡",
                    "name": "Performance",
                    "color": "yellow",
                },
                # Configuration
                "configuration": {
                    "icon": "⚙️",
                    "name": "Configuration",
                    "color": "cyan",
                },
                "config": {"icon": "⚙️", "name": "Configuration", "color": "cyan"},
                "syntax": {"icon": "⚙️", "name": "Configuration", "color": "cyan"},
                "syntaxerror": {"icon": "⚙️", "name": "Configuration", "color": "cyan"},
                "deprecated": {"icon": "⚙️", "name": "Configuration", "color": "cyan"},
                "settings": {"icon": "⚙️", "name": "Configuration", "color": "cyan"},
                # Documentation
                "documentation": {
                    "icon": "📚",
                    "name": "Documentation",
                    "color": "blue",
                },
                "docs": {"icon": "📚", "name": "Documentation", "color": "blue"},
                "doc": {"icon": "📚", "name": "Documentation", "color": "blue"},
                "accuracy": {"icon": "📚", "name": "Documentation", "color": "blue"},
                "clarity": {"icon": "📚", "name": "Documentation", "color": "blue"},
                "completeness": {
                    "icon": "📚",
                    "name": "Documentation",
                    "color": "blue",
                },
                # Breaking changes
                "breaking": {"icon": "💥", "name": "Breaking Change", "color": "red"},
                "breakingchange": {
                    "icon": "💥",
                    "name": "Breaking Change",
                    "color": "red",
                },
                "breakingchanges": {
                    "icon": "💥",
                    "name": "Breaking Change",
                    "color": "red",
                },
                "rename": {"icon": "💥", "name": "Breaking Change", "color": "red"},
                "deletion": {"icon": "💥", "name": "Breaking Change", "color": "red"},
                "signature": {"icon": "💥", "name": "Breaking Change", "color": "red"},
                "signaturechange": {
                    "icon": "💥",
                    "name": "Breaking Change",
                    "color": "red",
                },
                # General categories
                "bug": {"icon": "🐛", "name": "Bug", "color": "red"},
                "error": {"icon": "🐛", "name": "Bug", "color": "red"},
                "logic": {"icon": "🧠", "name": "Logic", "color": "magenta"},
                "logicalerror": {"icon": "🧠", "name": "Logic", "color": "magenta"},
                "style": {"icon": "🎨", "name": "Style", "color": "blue"},
                "styleguide": {"icon": "🎨", "name": "Style", "color": "blue"},
                "codestyle": {"icon": "🎨", "name": "Style", "color": "blue"},
            }.get(
                issue_type_normalized,
                {"icon": "⚠️", "name": issue_type.title(), "color": "white"},
            )

            # Build the card content
            file_path = issue.get("file", "N/A")
            line_number = issue.get("line", "-")
            description = issue.get("description", "No description provided")
            suggestion = issue.get("suggestion", "No suggestion provided")
            impact = issue.get("impact", None)

            # Create the card content
            card_content = []

            # Header with issue number, type, and severity
            header = f"[bold]{type_info['icon']} Issue #{i}: [{type_info['color']}]{type_info['name']}[/{type_info['color']}][/bold]"
            header += f"   {severity_info['icon']} [{severity_info['color']}]{severity_info['text']}[/{severity_info['color']}]"
            card_content.append(header)
            card_content.append("")

            # File and line information
            card_content.append(f"📍 [cyan]Location:[/cyan] {file_path}")
            if line_number != "-":
                card_content.append(f"📏 [cyan]Line:[/cyan] {line_number}")
            card_content.append("")

            # Description
            card_content.append("📝 [cyan]Description:[/cyan]")
            description_lines = self._format_multiline_text(description)
            card_content.extend(description_lines)
            card_content.append("")

            # Impact (if available)
            if impact and impact.strip():
                card_content.append("💥 [cyan]Impact:[/cyan]")
                impact_lines = self._format_multiline_text(impact)
                card_content.extend(impact_lines)
                card_content.append("")

            # Suggestion
            card_content.append("💡 [cyan]Suggestion:[/cyan]")
            suggestion_lines = self._format_multiline_text(suggestion)
            card_content.extend(suggestion_lines)

            # Affected references (if available)
            affected_references = issue.get("affected_references", None)
            if affected_references:
                card_content.append("")
                card_content.append("🔗 [cyan]Affected References:[/cyan]")
                if isinstance(affected_references, list):
                    for ref in affected_references:  # Show all references
                        card_content.append(f"   • {ref}")
                else:
                    ref_lines = self._format_multiline_text(str(affected_references))
                    card_content.extend(ref_lines)

            # Security reference (if available)
            security_reference = issue.get("security_reference", None)
            if security_reference and security_reference.strip():
                card_content.append("")
                card_content.append("🔒 [cyan]Security Reference:[/cyan]")
                security_ref_lines = self._format_multiline_text(security_reference)
                card_content.extend(security_ref_lines)

            # Determine border style based on severity
            border_style = {
                "critical": "red",
                "high": "red",
                "medium": "yellow",
                "low": "green",
                "info": "blue",
            }.get(severity, "white")

            # Create and show the card
            card_text = "\n".join(card_content)
            self.console.print(Panel(card_text, border_style=border_style, padding=(0, 1), expand=False))

            # Add separator between cards (except for the last one)
            if i < len(issues):
                self.console.print("")

    def _show_issues_table(self, issues: List[Dict[str, Any]]):
        """Legacy table display method - kept for compatibility."""
        # Redirect to new card display
        self._show_issues_cards(issues)

    def _show_files_analyzed_table(self, files: List[str]):
        """Display analyzed files in a table."""
        table = Table(
            title="📁 Files Analyzed",
            show_header=True,
            header_style="bold blue",
            expand=True,
            show_lines=True,
        )

        table.add_column("File Path", style="cyan", min_width=40, no_wrap=False)
        table.add_column("Status", style="green", min_width=15, no_wrap=True)

        for file_path in files:
            table.add_row(file_path, "✅ Analyzed")

        self.console.print(table)

    def _show_metrics_panel(self, metrics: Dict[str, Any]):
        """Display execution metrics from Strands agent."""
        if not metrics:
            return

        content = []

        # Token Usage Metrics
        accumulated_usage = metrics.get("accumulated_usage", {})
        if accumulated_usage:
            content.append("📊 [bold cyan]Token Usage:[/bold cyan]")
            input_tokens = accumulated_usage.get("inputTokens", 0)
            output_tokens = accumulated_usage.get("outputTokens", 0)
            total_tokens = accumulated_usage.get("totalTokens", 0)
            total_duration = metrics.get("total_duration", 0)

            content.append(f"   🔼 Input tokens: [green]{input_tokens:,}[/green]")
            content.append(f"   🔽 Output tokens: [yellow]{output_tokens:,}[/yellow]")
            content.append(f"   📈 Total tokens: [bold]{total_tokens:,}[/bold]")
            content.append(f"   ⏱️ Total duration: [green]{total_duration:.2f}s[/green]")
            content.append("")

        if not content:
            content = ["📊 No metrics data available"]

        # Create and display the metrics panel
        self.console.print(
            Panel(
                "\n".join(content).rstrip(),
                title="📈 Execution Metrics",
                border_style="green",
                padding=(0, 1),
            )
        )


# Global instance for easy access
console_ui = ConsoleUI()
