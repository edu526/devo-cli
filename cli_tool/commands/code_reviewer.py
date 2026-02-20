"""
Main entry point for the Code Reviewer application.
"""

import json
import sys
from typing import Optional

import click

from cli_tool.code_reviewer.analyzer import CodeReviewAnalyzer
from cli_tool.ui.console_ui import console_ui


@click.command()
@click.option(
    "--base-branch",
    "-b",
    default=None,
    help="Base branch to compare against (default: auto-detect main/master)",
)
@click.option(
    "--repo-path",
    "-r",
    default=None,
    help="Path to the Git repository (default: current directory)",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format (table: rich tables, json: raw JSON)",
)
@click.option(
    "--show-metrics",
    "-m",
    is_flag=True,
    default=False,
    help="Include detailed execution metrics in the output",
)
@click.option(
    "--full-prompt",
    "-f",
    is_flag=True,
    default=False,
    help="Use full detailed prompt (default: optimized short prompt)",
)
@click.pass_context
def code_reviewer(
    ctx,
    base_branch: Optional[str],
    repo_path: Optional[str],
    output: str,
    show_metrics: bool,
    full_prompt: bool,
):
    """
    🚀 Code Reviewer - AI-Powered Code Analysis

    Analyze code changes in your Git repository using AI agents.
    Perfect for PR reviews and continuous integration pipelines.

    Examples:
        # Analyze PR changes (current branch vs main)
        devo code-reviewer

        # Analyze PR changes vs specific branch
        devo code-reviewer --base-branch develop

        # Get JSON output for CI/CD integration
        devo code-reviewer --output json

        # Get table output (default and most readable)
        devo code-reviewer --output table

        # Show detailed execution metrics
        devo code-reviewer --show-metrics

        # Use full detailed prompt (more comprehensive but slower)
        devo code-reviewer --full-prompt

        # Combine options
        devo code-reviewer --base-branch develop --show-metrics --output json --full-prompt

        # Use specific AWS profile
        devo --profile my-profile code-reviewer
    """
    try:
        analyzer = CodeReviewAnalyzer()
        result = analyzer.analyze_pr(
            base_branch=base_branch,
            repo_path=repo_path,
            use_short_prompt=not full_prompt,
        )

        if output == "json":
            if not show_metrics:
                # Remove metrics from JSON output unless explicitly requested
                result_copy = result.copy()
                result_copy.pop("metrics", None)
                click.echo(json.dumps(result_copy, indent=2))
            else:
                click.echo(json.dumps(result, indent=2))
        else:
            # For table output, show results in a rich table
            # Pass the show_metrics flag to control metrics display
            console_ui.show_analysis_results_table(result, show_metrics=show_metrics)

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)
