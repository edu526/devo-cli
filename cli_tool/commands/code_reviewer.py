"""Thin wrapper for code-reviewer command - imports from cli_tool/code_reviewer/."""

from cli_tool.code_reviewer.commands.analyze import analyze as code_reviewer

__all__ = ["code_reviewer"]
