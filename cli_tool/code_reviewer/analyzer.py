"""
Code Review Analyzer - Core functionality for analyzing code with AI agents.
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional

from cli_tool.agents.base_agent import BaseAgent
from cli_tool.code_reviewer.git_utils import GitManager
from cli_tool.code_reviewer.prompt.code_reviewer import (
    CODE_REVIEWER_PROMPT,
    CODE_REVIEWER_PROMPT_SHORT,
)
from cli_tool.code_reviewer.tools import (
    analyze_import_usage,
    get_file_content,
    get_file_info,
    search_code_references,
    search_function_definition,
)
from cli_tool.ui.console_ui import console_ui


class CodeReviewAnalyzer:
    """Main class for analyzing code using AI agents with BaseAgent."""

    def __init__(self):
        """Initialize the analyzer."""
        self.project_root = Path(__file__).parent.parent

    def _create_agent(self, use_short_prompt: bool = True) -> BaseAgent:
        """Create and configure the BaseAgent with code review tools."""
        # Tools for dependency analysis and smart context reading
        tools = [
            search_code_references,
            get_file_content,
            search_function_definition,
            analyze_import_usage,
            get_file_info,
        ]

        # Choose prompt based on parameter
        prompt = CODE_REVIEWER_PROMPT_SHORT if use_short_prompt else CODE_REVIEWER_PROMPT

        return BaseAgent(
            name="CodeReviewer",
            system_prompt=prompt,
            tools=tools,
        )

    def _get_agent_with_streaming(self, request: str, use_short_prompt: bool = True):
        """Get agent response with real-time streaming display."""
        agent = self._get_agent(use_short_prompt)

        # Show AI starting to think
        console_ui.show_ai_thinking("AI is starting to process the request...")

        try:
            # Use BaseAgent's query method
            result = agent.query(request)

            # Capture metrics after execution
            self._last_metrics = agent.get_last_metrics()
            self._metrics_summary = agent.get_metrics_summary()

            return result

        except Exception as e:
            console_ui.show_ai_thinking(f"AI encountered an error: {str(e)}")
            raise

    def _get_agent(self, use_short_prompt: bool = True) -> BaseAgent:
        """Create a new agent instance with the specified prompt type."""
        return self._create_agent(use_short_prompt)

    def analyze_pr(
        self,
        base_branch: Optional[str] = None,
        repo_path: Optional[str] = None,
        use_short_prompt: bool = True,
    ) -> Dict[str, any]:
        """
        Analyze a Pull Request by detecting changed files and analyzing only the diff.

        Args:
            base_branch: Branch to compare against (default: auto-detect main/master)
            repo_path: Path to the Git repository (default: current directory)

        Returns:
            Dictionary with comprehensive PR analysis focused on diff changes only
        """
        # Clear terminal for a clean analysis experience
        os.system("cls" if os.name == "nt" else "clear")

        try:
            git_manager = GitManager(repo_path)
            pr_context = git_manager.get_pr_context(base_branch)

            # If no supported files changed, return early
            if not pr_context["supported_files"]:
                return {
                    "summary": "No supported code files were modified in this PR.",
                    "pr_context": {
                        "current_branch": pr_context["current_branch"],
                        "base_branch": pr_context["base_branch"],
                        "total_files": pr_context["total_changed_files"],
                        "supported_files": 0,
                    },
                    "issues": [],
                    "files_analyzed": [],
                    "metrics": {},
                }

            # Analyze the diff - let AI decide what context it needs via tools
            diff_analysis = self._analyze_pr_diff_only(pr_context, repo_path, use_short_prompt)

            # Get metrics if available
            metrics_data = {}
            if hasattr(self, "_metrics_summary") and self._metrics_summary:
                metrics_data = self._metrics_summary

            return {
                "summary": diff_analysis.get("summary", "Diff analysis completed"),
                "pr_context": {
                    "current_branch": pr_context["current_branch"],
                    "base_branch": pr_context["base_branch"],
                    "total_files": pr_context["total_changed_files"],
                    "supported_files": len(pr_context["supported_files"]),
                    "changed_files": pr_context["changed_files"],
                },
                "issues": diff_analysis.get("issues", []),
                "files_analyzed": pr_context["supported_files"],
                "metrics": metrics_data,
            }

        except Exception as e:
            return {
                "error": f"Failed to analyze PR: {str(e)}",
                "summary": "Error occurred during PR analysis",
                "issues": [],
                "metrics": {},
            }

    def _analyze_pr_diff_only(
        self,
        pr_context: Dict[str, any],
        repo_path: Optional[str] = None,
        use_short_prompt: bool = True,
    ) -> Dict[str, any]:
        """
        Analyze only the PR diff changes, using file context for reference.

        Args:
            pr_context: PR context from GitManager
            repo_path: Path to the repository

        Returns:
            Parsed JSON analysis focused only on diff changes
        """
        # Show AI thinking process
        console_ui.show_ai_thinking("Preparing to analyze the PR diff and identify potential issues...")

        # Show what we're analyzing
        console_ui.show_ai_action(
            "Building analysis context",
            f"Analyzing {pr_context['supported_changed_files']} files with changes",
        )

        # Minimal context - let AI use tools to get what it needs
        analysis_request = f"""Current branch: {pr_context['current_branch']}
Base branch: {pr_context['base_branch']}
Files changed: {pr_context['total_changed_files']} total, {pr_context['supported_changed_files']} supported
Changed files: {', '.join(pr_context['changed_files'])}

Diff:
```diff
{pr_context['full_diff']}
```"""

        # Show AI request info
        console_ui.show_request_to_ai(
            len(analysis_request),
            len(pr_context["supported_files"]),
            pr_context["current_branch"],
            pr_context["base_branch"],
        )

        # Show AI action before analysis
        console_ui.show_ai_action(
            "Analyzing code with AI",
            "The AI will examine the diff for breaking changes, security issues, and code quality problems",
        )

        # Show processing status
        console_ui.show_processing_status()

        # Call the agent with real streaming
        result = self._get_agent_with_streaming(analysis_request, use_short_prompt)

        # Extract and parse the JSON response
        response_text = self._extract_agent_response(result)

        # Display metrics summary if available
        if hasattr(self, "_metrics_summary") and self._metrics_summary:
            self._display_metrics_summary()

        try:
            # Try to parse as JSON
            if response_text.strip().startswith("{"):
                parsed_result = json.loads(response_text)
                console_ui.show_analysis_complete(len(response_text))
                return parsed_result
            else:
                # If not JSON, look for JSON block in the response
                import re

                json_match = re.search(r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL)
                if json_match:
                    parsed_result = json.loads(json_match.group(1))
                    console_ui.show_analysis_complete(len(response_text))
                    return parsed_result
                else:
                    # Fallback: create a structured response
                    console_ui.show_ai_thinking("Could not find JSON in response, creating fallback structure...")
                    return {
                        "summary": (response_text[:500] + "..." if len(response_text) > 500 else response_text),
                        "issues": [],
                    }
        except json.JSONDecodeError as e:
            # If JSON parsing fails, return the raw response in a structured format
            console_ui.show_ai_thinking(f"JSON parsing failed: {str(e)}, returning raw response...")
            return {
                "summary": f"Analysis completed (JSON parsing failed): {response_text[:200]}...",
                "issues": [],
                "raw_response": response_text,
            }

    def _extract_agent_response(self, result) -> str:
        """Extract text content from agent result."""
        # BaseAgent returns string directly
        if isinstance(result, str):
            return result

        # Fallback for other formats
        if hasattr(result, "message") and "content" in result.message:
            content = result.message["content"]
            if isinstance(content, list) and len(content) > 0:
                if "text" in content[0]:
                    return content[0]["text"]
        return str(result)

    def _display_metrics_summary(self):
        """Display a summary of execution metrics during analysis."""
        if not hasattr(self, "_metrics_summary") or not self._metrics_summary:
            return

        metrics = self._metrics_summary

        # Extract key metrics
        total_tokens = metrics.get("accumulated_usage", {}).get("totalTokens", 0)
        total_duration = metrics.get("total_duration", 0)
        total_cycles = metrics.get("total_cycles", 0)
        tool_count = len(metrics.get("tool_usage", {}))

        # Display concise metrics summary
        if total_tokens or total_duration or total_cycles:
            summary_text = []
            if total_tokens:
                summary_text.append(f"🎯 {total_tokens:,} tokens used")
            if total_duration:
                summary_text.append(f"⏱️ {total_duration:.1f}s execution time")
            if total_cycles:
                summary_text.append(f"🔄 {total_cycles} reasoning cycles")
            if tool_count:
                summary_text.append(f"🔧 {tool_count} tools used")

            console_ui.show_ai_thinking(f"Analysis complete: {' | '.join(summary_text)}")
