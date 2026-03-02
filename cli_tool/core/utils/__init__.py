"""Shared utilities."""

# Note: Imports are intentionally not done here to avoid circular dependencies
# Import directly from submodules instead:
#   from cli_tool.core.utils.aws import create_aws_session, create_aws_client
#   from cli_tool.core.utils.config_manager import load_config, save_config
#   from cli_tool.core.utils.git_utils import get_branch_name, get_staged_diff

__all__ = [
    "aws",
    "aws_profile",
    "config_manager",
    "git_utils",
    "version_check",
]
