"""Commit message generation business logic."""

import re
import subprocess
from typing import Optional, Tuple

from cli_tool.agents.base_agent import BaseAgent


class CommitMessageGenerator:
    """Generates conventional commit messages using AI."""

    SYSTEM_PROMPT = """You are an AI that generates ONE conventional commit message.

CRITICAL: Generate ONLY ONE commit message, not multiple. Find the PRIMARY purpose of all changes.

FORMAT (first line):
type(scope): summary

VALID TYPES: feat, fix, refactor, chore, docs, test, style, perf

RULES:
1. First line: type(scope): summary (max 50 chars)
2. Summary explains WHY, not what
3. Optional: blank line + bullet points with details
4. NO markdown, NO multiple messages, NO explanations

CORRECT EXAMPLES:
refactor(agents): simplify commit message generation

fix(auth): resolve credential validation error

- Fixed caching logic
- Added error handling

INCORRECT (DO NOT DO):
❌ Multiple commit messages listed
❌ refactor(agents): improve X
   fix(base): enhance Y
   refactor(commit): replace Z

Generate ONE message capturing the main purpose of ALL changes."""

    def __init__(self, profile_name: Optional[str] = None):
        """Initialize the commit message generator.

        Args:
          profile_name: AWS profile to use for AI agent
        """
        self.agent = BaseAgent(
            name="CommitMessageGenerator",
            system_prompt=self.SYSTEM_PROMPT,
            profile_name=profile_name,
            enable_rich_logging=False,
        )

    def extract_ticket_from_branch(self, branch_name: str) -> Optional[str]:
        """Extract ticket number from branch name.

        Args:
          branch_name: Git branch name

        Returns:
          Ticket number or None
        """
        match = re.match(r"(?:feature|fix|chore)/([A-Za-z0-9]+-\d+)", branch_name)
        return match.group(1) if match else None

    def get_git_context(self) -> Tuple[str, str]:
        """Get git status and recent commits for context.

        Returns:
          Tuple of (git_status, recent_commits)
        """
        try:
            git_status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
            )
            git_status = git_status_result.stdout

            git_log_result = subprocess.run(
                ["git", "log", "--oneline", "-10"],
                capture_output=True,
                text=True,
                check=True,
            )
            recent_commits = git_log_result.stdout

            return git_status, recent_commits
        except subprocess.CalledProcessError:
            return "Unable to get git status", "Unable to get recent commits"

    def parse_commit_message(self, ai_response: str) -> Tuple[str, str, str]:
        """Parse AI response into commit components.

        Args:
          ai_response: Raw AI response

        Returns:
          Tuple of (commit_type, scope, summary_with_details)
        """
        lines = ai_response.strip().split("\n")
        first_line = lines[0].strip()

        # Extract type, scope, and summary from first line
        if ":" in first_line:
            type_scope, summary = first_line.split(":", 1)
            summary = summary.strip()

            # Extract type and scope
            if "(" in type_scope and ")" in type_scope:
                commit_type = type_scope.split("(")[0].strip()
                scope = type_scope.split("(")[1].split(")")[0].strip()
            else:
                commit_type = type_scope.strip()
                scope = "general"
        else:
            # Fallback if format is not as expected
            commit_type = "chore"
            scope = "general"
            summary = first_line

        # Get details if present (everything after first line)
        details = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
        summary_with_details = summary + ("\n\n" + details if details else "")

        return commit_type, scope, summary_with_details

    def generate(
        self,
        diff_text: str,
        branch_name: str,
        git_status: Optional[str] = None,
        recent_commits: Optional[str] = None,
    ) -> str:
        """Generate a commit message from staged changes.

        Args:
          diff_text: Git diff of staged changes
          branch_name: Current branch name
          git_status: Git status output (optional)
          recent_commits: Recent commit history (optional)

        Returns:
          Generated commit message
        """
        ticket_number = self.extract_ticket_from_branch(branch_name)

        # Get git context if not provided
        if git_status is None or recent_commits is None:
            git_status, recent_commits = self.get_git_context()

        context_prompt = f"""Generate ONE commit message for these changes.

IMPORTANT: All these changes are part of ONE commit. Find the PRIMARY purpose and create ONE message.

CONTEXT:
Branch: {branch_name}
Ticket: {ticket_number or 'None'} (will be added automatically if present, do NOT include it in your message)

STAGED DIFF:
{diff_text}

GIT STATUS:
{git_status}

RECENT COMMITS (for style):
{recent_commits}

Remember: Generate ONLY ONE commit message that captures the main purpose of ALL these changes together.
Do NOT include the ticket number in your response - it will be added automatically if present in branch name."""

        ai_response = self.agent.query(context_prompt)
        commit_type, scope, summary_with_details = self.parse_commit_message(ai_response)

        # Add ticket number to summary if present and not already included
        summary_parts = summary_with_details.split("\n\n", 1)
        summary = summary_parts[0]
        details = summary_parts[1] if len(summary_parts) > 1 else ""

        if ticket_number and ticket_number not in summary:
            summary = f"{ticket_number} {summary}"

        commit_message = f"{commit_type}({scope}): {summary}"
        if details:
            commit_message += f"\n\n{details}"

        return commit_message.strip()

    def add_ticket_to_message(self, message: str, branch_name: str) -> str:
        """Add ticket number to a manual commit message if not present.

        Args:
          message: Commit message
          branch_name: Current branch name

        Returns:
          Message with ticket number prepended if applicable
        """
        ticket_number = self.extract_ticket_from_branch(branch_name)
        if ticket_number and ticket_number not in message:
            return f"{ticket_number} {message}"
        return message
