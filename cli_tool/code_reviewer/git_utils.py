"""
Git utilities for detecting changes and diffs for PR analysis.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional


class GitManager:
    """Manages Git operations for code review analysis."""

    def __init__(self, repo_path: Optional[str] = None):
        """Initialize GitManager with repository path."""
        # Lazy import to avoid git initialization at module import time
        from git import InvalidGitRepositoryError, Repo

        self.repo_path = repo_path or os.getcwd()
        try:
            self.repo = Repo(self.repo_path)
        except InvalidGitRepositoryError:
            raise InvalidGitRepositoryError(f"No valid Git repository found at {self.repo_path}")

    def get_current_branch(self) -> str:
        """Get the name of the current branch."""
        return str(self.repo.active_branch.name)

    def get_base_branch(self, default_base: str = "main") -> str:
        """
        Determine the base branch for comparison.

        Args:
            default_base: Default branch name to use (main, master, develop, etc.)

        Returns:
            Name of the base branch
        """
        # Check if the default base exists
        if default_base in [ref.name for ref in self.repo.refs]:
            return default_base

        # Fallback options
        common_bases = ["main", "master", "develop", "dev"]
        for base in common_bases:
            if base in [ref.name for ref in self.repo.refs]:
                return base

        # If no common base found, use the first branch
        branches = [ref.name for ref in self.repo.refs if not ref.name.startswith("origin/")]
        if branches:
            return branches[0]

        raise ValueError("No suitable base branch found")

    def get_changed_files(self, base_branch: Optional[str] = None) -> List[str]:
        """
        Get list of files that have been modified in the current branch compared to base.

        Args:
            base_branch: Branch to compare against (default: auto-detect)

        Returns:
            List of file paths that have been modified
        """
        if base_branch is None:
            base_branch = self.get_base_branch()

        current_branch = self.get_current_branch()

        # Get the merge base (common ancestor)
        try:
            merge_base = self.repo.merge_base(base_branch, current_branch)[0]
        except IndexError:
            # If no merge base found, compare directly with base branch
            merge_base = base_branch

        # Get list of changed files
        changed_files = []
        for item in self.repo.git.diff(merge_base, current_branch, name_only=True).split("\n"):
            if item.strip():
                changed_files.append(item.strip())

        return changed_files

    def get_file_diff(self, file_path: str, base_branch: Optional[str] = None) -> str:
        """
        Get the diff for a specific file.

        Args:
            file_path: Path to the file
            base_branch: Branch to compare against

        Returns:
            Diff content as string
        """
        if base_branch is None:
            base_branch = self.get_base_branch()

        current_branch = self.get_current_branch()

        try:
            merge_base = self.repo.merge_base(base_branch, current_branch)[0]
        except IndexError:
            merge_base = base_branch

        try:
            # Check if file exists in both commits

            # Try to get the diff
            diff_output = self.repo.git.diff(merge_base, current_branch, file_path)

            # If diff is empty, the file might not exist in base
            if not diff_output.strip():
                # Check if file exists in current branch but not in base
                try:
                    self.repo.git.show(f"{merge_base}:{file_path}")
                    # File exists in base but no changes
                    return f"No changes in {file_path}"
                except Exception:
                    # File is new in current branch
                    try:
                        file_content = self.repo.git.show(f"{current_branch}:{file_path}")
                        diff_header = (
                            f"diff --git a/{file_path} b/{file_path}\n"
                            f"new file mode 100644\nindex 0000000..1234567\n"
                            f"--- /dev/null\n+++ b/{file_path}\n"
                            f"@@ -0,0 +1,{len(file_content.splitlines())} @@\n"
                        )
                        return diff_header + "\n".join(f"+{line}" for line in file_content.splitlines())
                    except Exception:
                        return f"Error: Could not read new file {file_path}"

            return diff_output

        except Exception as e:
            return f"Error getting diff for {file_path}: {str(e)}"

    def get_full_diff(self, base_branch: Optional[str] = None) -> str:
        """
        Get the complete diff between current branch and base.

        Args:
            base_branch: Branch to compare against

        Returns:
            Complete diff as string
        """
        if base_branch is None:
            base_branch = self.get_base_branch()

        current_branch = self.get_current_branch()

        try:
            merge_base = self.repo.merge_base(base_branch, current_branch)[0]
        except IndexError:
            merge_base = base_branch

        return self.repo.git.diff(merge_base, current_branch)

    def is_file_supported(self, file_path: str) -> bool:
        """
        Check if the file type is supported for analysis.
        Now supports all file types for comprehensive analysis.

        Args:
            file_path: Path to the file

        Returns:
            True if file is supported for analysis (now always True for all files)
        """
        # Support all file types for comprehensive analysis
        file_extension = Path(file_path).suffix.lower()

        # Skip binary files and common non-code files
        binary_extensions = {
            ".exe",
            ".dll",
            ".so",
            ".dylib",
            ".bin",
            ".obj",
            ".o",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".bmp",
            ".ico",
            ".svg",
            ".mp3",
            ".mp4",
            ".avi",
            ".mov",
            ".wav",
            ".zip",
            ".tar",
            ".gz",
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
        }

        # Skip if it's a known binary file
        if file_extension in binary_extensions:
            return False

        # Support all text-based files (including code, config, docs, etc.)
        return True

    def filter_supported_files(self, file_paths: List[str]) -> List[str]:
        """
        Filter list of files to only include supported file types.
        Now includes all text-based files, excluding only binary files.

        Args:
            file_paths: List of file paths

        Returns:
            Filtered list of supported files
        """
        return [fp for fp in file_paths if self.is_file_supported(fp)]

    def get_pr_context(self, base_branch: Optional[str] = None) -> Dict[str, any]:
        """
        Get comprehensive PR context including changed files, diffs, and metadata.

        Args:
            base_branch: Branch to compare against

        Returns:
            Dictionary with PR context information
        """
        if base_branch is None:
            base_branch = self.get_base_branch()

        current_branch = self.get_current_branch()
        changed_files = self.get_changed_files(base_branch)
        supported_files = self.filter_supported_files(changed_files)

        context = {
            "current_branch": current_branch,
            "base_branch": base_branch,
            "total_changed_files": len(changed_files),
            "supported_changed_files": len(supported_files),
            "changed_files": changed_files,
            "supported_files": supported_files,
            "full_diff": self.get_full_diff(base_branch),
            "file_diffs": {},
        }

        # Get individual file diffs for supported files only
        for file_path in supported_files:
            diff = self.get_file_diff(file_path, base_branch)
            if not diff.startswith("Error getting diff"):
                context["file_diffs"][file_path] = diff

        # Update supported files to only include those with valid diffs
        context["supported_files"] = list(context["file_diffs"].keys())
        context["supported_changed_files"] = len(context["supported_files"])

        return context
