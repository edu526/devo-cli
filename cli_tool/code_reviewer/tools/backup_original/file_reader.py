"""
Advanced file reading tool with multiple specialized reading modes.

This module combines the best features from Strands file_read tool with our custom
UI components and code analysis capabilities. It provides comprehensive file reading
capabilities with rich output formatting, pattern searching, and multiple specialized modes.

Key Features:

1. Multiple Reading Modes:
   • view: Display full file contents with syntax highlighting
   • find: List matching files with directory tree visualization
   • lines: Show specific line ranges with context
   • chunk: Read byte chunks from specific offsets
   • search: Pattern searching with context highlighting
   • stats: File statistics and metrics
   • preview: Quick content preview
   • diff: Compare files or directories
   • time_machine: View version history (Git integration)

2. Advanced Capabilities:
   • Multi-file support with comma-separated paths
   • Wildcard pattern matching (*.py, src/**)
   • Recursive directory traversal
   • Git integration for version history
   • Smart line finding with context
   • Highlighted search results

3. Rich UI Integration:
   • Syntax highlighting based on file type
   • Formatted panels for better readability
   • Directory tree visualization
   • Line numbering and statistics
   • Streaming display support

Usage Examples:
```python
from strands import tool

# View file content with syntax highlighting
get_file_content(path="/path/to/file.py", mode="view")

# List files matching a pattern
get_file_content(path="/path/to/project/*.py", mode="find")

# Read specific line ranges
get_file_content(
    path="/path/to/file.txt",
    mode="lines",
    start_line=10,
    end_line=20
)

# Search for patterns
get_file_content(
    path="/path/to/file.txt",
    mode="search",
    search_pattern="function",
    context_lines=3
)

# Compare files
get_file_content(
    path="/path/to/file1.txt",
    mode="diff",
    comparison_path="/path/to/file2.txt"
)
```
"""

import glob
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from strands import tool

from cli_tool.ui.console_ui import console_ui


def get_gitignore_excludes() -> List[str]:
    """Generate exclude patterns from .gitignore file for file operations."""
    gitignore_path = Path(".gitignore")
    excludes = []

    # Common patterns to always exclude
    default_excludes = [
        ".git",
        ".venv",
        "__pycache__",
        "node_modules",
        ".pytest_cache",
        "*.pyc",
        "*.pyo",
        "*.egg-info",
        "build",
        "dist",
        ".tox",
        ".idea",
        ".vscode",
        "*.log",
        "*.tmp",
    ]

    excludes.extend(default_excludes)

    # Read .gitignore if it exists
    if gitignore_path.exists():
        try:
            with open(gitignore_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith("#"):
                        # Clean up gitignore patterns
                        if line.endswith("/"):
                            excludes.append(line.rstrip("/"))
                        else:
                            excludes.append(line)
        except Exception:
            # If we can't read .gitignore, just use defaults
            pass

    return excludes


def should_exclude_path(file_path: str, excludes: List[str]) -> bool:
    """Check if a file path should be excluded based on gitignore patterns."""
    path_obj = Path(file_path)
    path_str = str(path_obj)
    path_parts = path_obj.parts

    for exclude in excludes:
        # Direct match
        if exclude in path_str:
            return True

        # Check against any part of the path
        if any(exclude in part for part in path_parts):
            return True

        # Pattern matching for wildcards
        if "*" in exclude:
            try:
                if path_obj.match(exclude):
                    return True
            except (AttributeError, ValueError):
                pass

    return False


def find_files(
    pattern: str, recursive: bool = True, max_files: int = 1000
) -> List[str]:
    """
    Find files matching a pattern with gitignore exclusion support.

    Args:
        pattern: File pattern to search for (supports wildcards)
        recursive: Whether to search recursively
        max_files: Maximum number of files to return

    Returns:
        List of matching file paths
    """
    excludes = get_gitignore_excludes()
    matching_files = []

    try:
        # Handle different pattern types
        if os.path.isfile(pattern):
            # Direct file path
            if not should_exclude_path(pattern, excludes):
                matching_files.append(pattern)
        elif os.path.isdir(pattern):
            # Directory - list all files
            pattern_path = Path(pattern)
            if recursive:
                for file_path in pattern_path.rglob("*"):
                    if file_path.is_file() and not should_exclude_path(
                        str(file_path), excludes
                    ):
                        matching_files.append(str(file_path))
                        if len(matching_files) >= max_files:
                            break
            else:
                for file_path in pattern_path.iterdir():
                    if file_path.is_file() and not should_exclude_path(
                        str(file_path), excludes
                    ):
                        matching_files.append(str(file_path))
                        if len(matching_files) >= max_files:
                            break
        else:
            # Glob pattern
            if recursive and "**" not in pattern:
                # Add recursive pattern if not present
                pattern = f"**/{pattern}"

            for file_path in glob.glob(pattern, recursive=recursive):
                if os.path.isfile(file_path) and not should_exclude_path(
                    file_path, excludes
                ):
                    matching_files.append(file_path)
                    if len(matching_files) >= max_files:
                        break

    except Exception:
        # If glob fails, try simpler approach
        pass

    return sorted(matching_files)


def split_path_list(path: str) -> List[str]:
    """Split comma-separated paths and clean them up."""
    if "," in path:
        return [p.strip() for p in path.split(",") if p.strip()]
    return [path.strip()]


def detect_language_from_path(file_path: str) -> str:
    """Detect programming language from file extension."""
    ext = Path(file_path).suffix.lower()

    language_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".jsx": "jsx",
        ".html": "html",
        ".css": "css",
        ".scss": "scss",
        ".sass": "sass",
        ".json": "json",
        ".xml": "xml",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".md": "markdown",
        ".sql": "sql",
        ".sh": "bash",
        ".bat": "batch",
        ".ps1": "powershell",
        ".java": "java",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".php": "php",
        ".rb": "ruby",
        ".go": "go",
        ".rs": "rust",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".r": "r",
        ".m": "matlab",
        ".pl": "perl",
        ".lua": "lua",
        ".dart": "dart",
        ".vue": "vue",
        ".svelte": "svelte",
    }

    return language_map.get(ext, "text")


def read_file_lines(
    file_path: str, start_line: int = 1, end_line: Optional[int] = None
) -> tuple[List[str], Dict[str, Any]]:
    """
    Read specific lines from file with metadata.

    Args:
        file_path: Path to the file
        start_line: First line to read (1-based)
        end_line: Last line to read (optional)

    Returns:
        Tuple of (lines, metadata dict)
    """
    file_path = os.path.expanduser(file_path)

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if not os.path.isfile(file_path):
        raise ValueError(f"Path is not a file: {file_path}")

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        all_lines = f.readlines()

    total_lines = len(all_lines)

    # Validate and adjust line numbers (convert to 0-based)
    start_line = max(1, start_line)
    if end_line is None:
        end_line = total_lines
    end_line = min(total_lines, end_line)

    if start_line > total_lines:
        raise ValueError(
            f"Start line {start_line} exceeds file length ({total_lines} lines)"
        )

    if start_line > end_line:
        raise ValueError(f"Start line {start_line} is greater than end line {end_line}")

    # Extract lines (convert to 0-based indexing)
    lines = all_lines[start_line - 1 : end_line]

    metadata = {
        "total_lines": total_lines,
        "start_line": start_line,
        "end_line": end_line,
        "lines_read": len(lines),
        "file_path": file_path,
    }

    return lines, metadata


def read_file_chunk(
    file_path: str, chunk_size: int, chunk_offset: int = 0
) -> tuple[str, Dict[str, Any]]:
    """
    Read a chunk of file from given offset.

    Args:
        file_path: Path to the file
        chunk_size: Number of bytes to read
        chunk_offset: Starting offset in bytes

    Returns:
        Tuple of (content, metadata dict)
    """
    file_path = os.path.expanduser(file_path)

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if not os.path.isfile(file_path):
        raise ValueError(f"Path is not a file: {file_path}")

    file_size = os.path.getsize(file_path)

    if chunk_offset < 0 or chunk_offset > file_size:
        raise ValueError(
            f"Invalid chunk_offset: {chunk_offset}. File size is {file_size} bytes."
        )

    if chunk_size < 0:
        raise ValueError(f"Invalid chunk_size: {chunk_size}")

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        f.seek(chunk_offset)
        content = f.read(chunk_size)

    metadata = {
        "file_size": file_size,
        "chunk_offset": chunk_offset,
        "chunk_size": chunk_size,
        "content_length": len(content),
        "file_path": file_path,
    }

    return content, metadata


def get_smart_search_patterns_for_file(term: str) -> List[str]:
    """
    Generate smart search patterns for file content search, similar to search_code_references.

    Args:
        term: The search term to generate patterns for

    Returns:
        List of regex patterns to search for
    """
    import re

    patterns = []

    # Escape special regex characters for exact matches
    escaped_term = re.escape(term)

    # 1. Exact match (case insensitive)
    patterns.append(escaped_term)

    # 2. Word boundary match (for cleaner matches)
    patterns.append(f"\\b{escaped_term}\\b")

    # 3. If it looks like a function call (has parentheses), search for variations
    if "(" in term:
        # Extract function name
        func_name = term.split("(")[0]
        escaped_func = re.escape(func_name)

        # Function call patterns
        patterns.append(f"{escaped_func}\\s*\\(")  # function(
        patterns.append(f"\\.{escaped_func}\\s*\\(")  # .function(
        patterns.append(f"\\w+\\.{escaped_func}\\s*\\(")  # object.function(

    # 4. If it looks like a method call (has dot), search for variations
    elif "." in term:
        parts = term.split(".")
        if len(parts) == 2:
            obj_part, method_part = parts
            escaped_obj = re.escape(obj_part)
            escaped_method = re.escape(method_part)

            # Method call patterns
            patterns.append(f"{escaped_obj}\\.{escaped_method}")  # exact match
            patterns.append(
                f"\\w*{escaped_obj}\\w*\\.{escaped_method}"
            )  # flexible object name
            patterns.append(f"\\.{escaped_method}")  # any object with this method

    # 5. If it's a simple identifier, search for common programming contexts
    elif term.isidentifier():
        escaped_term = re.escape(term)

        # Variable declarations and assignments
        patterns.append(f"\\b{escaped_term}\\s*[=:]")  # assignment
        patterns.append(f"def\\s+{escaped_term}\\s*\\(")  # function definition
        patterns.append(f"class\\s+{escaped_term}\\b")  # class definition
        patterns.append(f"import\\s+.*{escaped_term}")  # imports
        patterns.append(f"from\\s+.*{escaped_term}")  # from imports

    return patterns


def search_in_file(
    file_path: str, pattern: str, context_lines: int = 2, search_mode: str = "smart"
) -> List[Dict[str, Any]]:
    """
    Search for a pattern in a file with context lines and multiple search modes.

    Args:
        file_path: Path to the file
        pattern: Pattern to search for
        context_lines: Number of context lines before and after match
        search_mode: Search mode - "smart" (auto-generate patterns) or "regex" (use pattern directly)

    Returns:
        List of match dictionaries with context
    """
    import re

    file_path = os.path.expanduser(file_path)

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    matches = []
    seen_lines = set()  # To avoid duplicate matches

    # Determine search patterns based on mode
    if search_mode == "smart":
        patterns = get_smart_search_patterns_for_file(pattern)
    else:  # regex mode
        patterns = [pattern]

    # Search with each pattern
    for search_pattern in patterns:
        try:
            for i, line in enumerate(lines):
                if (
                    re.search(search_pattern, line, re.IGNORECASE)
                    and i not in seen_lines
                ):
                    seen_lines.add(i)

                    # Get context lines
                    start_ctx = max(0, i - context_lines)
                    end_ctx = min(len(lines), i + context_lines + 1)

                    context = {
                        "line_number": i + 1,
                        "match_line": line.rstrip(),
                        "matched_pattern": search_pattern,
                        "original_pattern": pattern,
                        "context_before": [
                            lines[j].rstrip() for j in range(start_ctx, i)
                        ],
                        "context_after": [
                            lines[j].rstrip() for j in range(i + 1, end_ctx)
                        ],
                        "file_path": file_path,
                    }
                    matches.append(context)
        except re.error:
            # Skip invalid regex patterns
            continue

    # Sort matches by line number
    matches.sort(key=lambda x: x["line_number"])

    return matches


def get_file_stats(file_path: str) -> Dict[str, Any]:
    """
    Get comprehensive file statistics.

    Args:
        file_path: Path to the file

    Returns:
        Dictionary with file statistics
    """
    file_path = os.path.expanduser(file_path)

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    stats = {
        "file_path": file_path,
        "size_bytes": os.path.getsize(file_path),
        "line_count": 0,
        "non_empty_lines": 0,
        "comment_lines": 0,
        "function_lines": [],
        "class_lines": [],
        "preview": "",
    }

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        stats["line_count"] = len(lines)
        preview_lines = []

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            if stripped:
                stats["non_empty_lines"] += 1

            # Preview (first 20 lines)
            if i <= 20:
                preview_lines.append(line.rstrip())

            # Comment detection
            if stripped.startswith(("#", "//", "/*", "*", "<!--")):
                stats["comment_lines"] += 1

            # Function detection
            if any(
                keyword in stripped
                for keyword in ["def ", "function ", "func ", "async def"]
            ):
                stats["function_lines"].append(i)

            # Class detection
            if any(
                keyword in stripped for keyword in ["class ", "interface ", "struct "]
            ):
                stats["class_lines"].append(i)

        stats["preview"] = "\n".join(preview_lines)
        stats["size_human"] = (
            f"{stats['size_bytes'] / 1024:.2f} KB"
            if stats["size_bytes"] < 1024 * 1024
            else f"{stats['size_bytes'] / (1024 * 1024):.2f} MB"
        )

    except Exception as e:
        stats["error"] = str(e)

    return stats


def create_diff(file_path1: str, file_path2: str) -> str:
    """
    Create a diff between two files.

    Args:
        file_path1: First file path
        file_path2: Second file path

    Returns:
        Formatted diff string
    """
    import difflib

    file_path1 = os.path.expanduser(file_path1)
    file_path2 = os.path.expanduser(file_path2)

    if not os.path.exists(file_path1):
        raise FileNotFoundError(f"First file not found: {file_path1}")

    if not os.path.exists(file_path2):
        raise FileNotFoundError(f"Second file not found: {file_path2}")

    with open(file_path1, "r", encoding="utf-8", errors="ignore") as f1:
        lines1 = f1.readlines()

    with open(file_path2, "r", encoding="utf-8", errors="ignore") as f2:
        lines2 = f2.readlines()

    diff = difflib.unified_diff(
        lines1, lines2, fromfile=file_path1, tofile=file_path2, lineterm=""
    )

    return "\n".join(diff)


@tool
def get_file_content(
    path: str,
    mode: str = "view",
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    lines_count: Optional[int] = None,
    show_line_numbers: bool = True,
    search_pattern: Optional[str] = None,
    search_mode: str = "smart",
    context_lines: int = 2,
    chunk_size: Optional[int] = None,
    chunk_offset: int = 0,
    comparison_path: Optional[str] = None,
    recursive: bool = True,
    max_files: int = 100,
) -> str:
    """
    Advanced file reading tool with multiple specialized modes and enhanced search capabilities.

    This is an enhanced version that combines the power of Strands file_read
    with our custom UI components and code analysis capabilities, now including
    unified smart and regex search modes similar to search_code_references.

    Args:
        path: Path(s) to file(s). For multiple files, use comma-separated list.
              Supports wildcards like '*.py' or 'src/**/*.js'
        mode: Reading mode to use:
            - 'view': Display full file contents with syntax highlighting
            - 'find': List matching files with directory tree visualization
            - 'lines': Show specific line ranges with context
            - 'chunk': Read byte chunks from specific offsets
            - 'search': Pattern searching with context highlighting
            - 'stats': File statistics and metrics
            - 'preview': Quick content preview (first 20 lines)
            - 'diff': Compare two files
        start_line: Starting line number for 'lines' mode (1-based)
        end_line: Ending line number for 'lines' mode (1-based)
        lines_count: Number of lines to read from start_line (alternative to end_line)
        show_line_numbers: Include line numbers in output for applicable modes
        search_pattern: Pattern to search for in 'search' mode
        search_mode: Search strategy for 'search' mode:
            - 'smart': Auto-generate patterns based on the search term (default)
                      Handles function calls, method calls, variable assignments, etc.
                      Example: "createTrip(cache)" → searches for exact match, function calls, method calls
            - 'regex': Use search_pattern as a direct regex pattern
                      Example: "createTrip\\(" → searches for literal "createTrip(" pattern
        context_lines: Number of context lines for 'search' mode
        chunk_size: Number of bytes to read in 'chunk' mode
        chunk_offset: Starting offset in bytes for 'chunk' mode
        comparison_path: Second file path for 'diff' mode
        recursive: Whether to search recursively in 'find' mode
        max_files: Maximum number of files to process in 'find' mode

    Returns:
        String containing the requested file content or operation results

    Examples:
        # View a single file
        get_file_content("src/main.py", mode="view")

        # Find all Python files
        get_file_content("*.py", mode="find")

        # Read specific lines
        get_file_content("src/main.py", mode="lines", start_line=10, end_line=20)

        # Smart search for function calls (auto-generates patterns)
        get_file_content("src/main.py", mode="search", search_pattern="createTrip(cache)", search_mode="smart")

        # Regex search for specific patterns
        get_file_content("src/main.py", mode="search", search_pattern="createTrip\\(", search_mode="regex")

        # Get file statistics
        get_file_content("src/main.py", mode="stats")

        # Compare two files
        get_file_content("file1.py", mode="diff", comparison_path="file2.py")

        # Search across multiple files using wildcards
        get_file_content("src/*.py", mode="search", search_pattern="externalTrips.createTrip", search_mode="smart")

        # Search in entire directory (recursively)
        get_file_content("src/", mode="search", search_pattern="UserModel", search_mode="smart")

        # Search across specific file types in directory
        get_file_content("src/**/*.js", mode="search", search_pattern="api.call", search_mode="smart")
    """
    # Show tool input
    console_ui.show_tool_input(
        "get_file_content",
        "📄",
        {
            "path": path,
            "mode": mode,
            "start_line": start_line,
            "end_line": end_line,
            "lines_count": lines_count,
            "search_pattern": search_pattern,
            "search_mode": search_mode,
            "recursive": recursive,
            "max_files": max_files,
        },
    )

    try:
        # Split comma-separated paths
        paths = split_path_list(path)
        all_files = []

        # Find all matching files
        for path_pattern in paths:
            if mode == "find":
                # For find mode, we want to show the pattern matching process
                files = find_files(
                    path_pattern, recursive=recursive, max_files=max_files
                )
                all_files.extend(files)
            else:
                # For other modes, resolve to actual files
                if os.path.isfile(path_pattern):
                    all_files.append(path_pattern)
                else:
                    files = find_files(
                        path_pattern, recursive=recursive, max_files=max_files
                    )
                    all_files.extend(files)

        # Remove duplicates and sort
        all_files = sorted(list(set(all_files)))

        if not all_files and mode != "find":
            error_msg = f"No files found matching pattern(s): {', '.join(paths)}"
            console_ui.show_file_error(path, error_msg)
            return error_msg

        # Handle different modes
        if mode == "find":
            # Show file tree and list
            if all_files:
                result = f"Found {len(all_files)} files:\n\n"

                # Group by directory for tree display
                dirs = {}
                for file_path in all_files:
                    dir_path = os.path.dirname(file_path) or "."
                    if dir_path not in dirs:
                        dirs[dir_path] = []
                    dirs[dir_path].append(os.path.basename(file_path))

                # Create tree structure text
                tree_text = "📁 File Tree:\n"
                for dir_path, files in sorted(dirs.items()):
                    tree_text += "  📁 {}/\n".format(dir_path)
                    for file_name in sorted(files):
                        tree_text += "    📄 {}\n".format(file_name)

                result += tree_text + "\n"
                result += "📋 Full Paths:\n" + "\n".join(
                    ["  {}".format(fp) for fp in all_files]
                )

                console_ui.show_tool_output("File Search Results", result)
            else:
                result = f"No files found matching pattern(s): {', '.join(paths)}"
                console_ui.show_tool_output("No Files Found", result, success=True)

            return result

        # Process files for other modes
        results = []

        for file_path in all_files[:max_files]:  # Limit processing
            try:
                if mode == "view":
                    # Read full file content
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    language = detect_language_from_path(file_path)
                    console_ui.show_code_content(file_path, content, 1, language)
                    results.append(f"Content of {file_path}:\n{content}")

                elif mode == "lines":
                    # Read specific line ranges
                    actual_start = start_line or 1
                    actual_end = end_line

                    if lines_count and not actual_end:
                        actual_end = actual_start + lines_count - 1

                    lines, metadata = read_file_lines(
                        file_path, actual_start, actual_end
                    )

                    if show_line_numbers:
                        formatted_lines = []
                        for i, line in enumerate(lines, start=metadata["start_line"]):
                            formatted_lines.append(f"{i:4d}: {line.rstrip()}")
                        content = "\n".join(formatted_lines)
                    else:
                        content = "".join(lines)

                    language = detect_language_from_path(file_path)
                    title = f"{file_path} (lines {metadata['start_line']}-{metadata['end_line']})"
                    console_ui.show_code_content(
                        title, content, metadata["start_line"], language
                    )
                    results.append(content)

                elif mode == "chunk":
                    # Read file chunk
                    actual_chunk_size = chunk_size or 1024
                    content, metadata = read_file_chunk(
                        file_path, actual_chunk_size, chunk_offset
                    )

                    info_text = (
                        f"Chunk from {file_path}:\n"
                        f"File size: {metadata['file_size']:,} bytes\n"
                        f"Chunk offset: {metadata['chunk_offset']:,} bytes\n"
                        f"Chunk size: {metadata['chunk_size']:,} bytes\n"
                        f"Content length: {metadata['content_length']:,} bytes\n\n{content}"
                    )

                    console_ui.show_tool_output(
                        f"File Chunk - {os.path.basename(file_path)}", info_text
                    )
                    results.append(content)

                elif mode == "search":
                    # Search for pattern in file with enhanced capabilities
                    if not search_pattern:
                        raise ValueError("search_pattern is required for search mode")

                    matches = search_in_file(
                        file_path, search_pattern, context_lines, search_mode
                    )

                    if matches:
                        # Group matches by pattern used (for smart mode)
                        pattern_groups = {}
                        for match in matches:
                            pattern_key = match.get("matched_pattern", search_pattern)
                            if pattern_key not in pattern_groups:
                                pattern_groups[pattern_key] = []
                            pattern_groups[pattern_key].append(match)

                        search_result = (
                            f"Found {len(matches)} matches in {file_path}:\n"
                        )
                        search_result += f"Search mode: {search_mode}\n"
                        search_result += f"Original pattern: {search_pattern}\n\n"

                        # Show results grouped by pattern (for smart mode understanding)
                        pattern_count = 0
                        for pattern_key, pattern_matches in pattern_groups.items():
                            pattern_count += 1
                            if search_mode == "smart" and pattern_key != search_pattern:
                                search_result += f"Pattern {pattern_count}: {pattern_key} ({len(pattern_matches)} matches)\n"
                            else:
                                search_result += f"Matches: {len(pattern_matches)}\n"

                            # Show up to 5 matches per pattern to keep output manageable
                            for i, match in enumerate(pattern_matches[:5], 1):
                                search_result += (
                                    f"  Match {i} (line {match['line_number']}):\n"
                                )

                                # Show context
                                for ctx_line in match["context_before"]:
                                    search_result += f"    {ctx_line}\n"
                                search_result += (
                                    f"  > {match['match_line']} <-- MATCH\n"
                                )
                                for ctx_line in match["context_after"]:
                                    search_result += f"    {ctx_line}\n"
                                search_result += "\n"

                            if len(pattern_matches) > 5:
                                search_result += f"    ... and {len(pattern_matches) - 5} more matches for this pattern\n\n"
                            else:
                                search_result += "\n"

                        if len(matches) > 25:  # Total limit across all patterns
                            search_result += (
                                "Total matches truncated at 25 for readability.\n"
                            )

                        # Store individual file results for later consolidation if searching multiple files
                        file_search_result = {
                            "file_path": file_path,
                            "matches": matches,
                            "pattern_groups": pattern_groups,
                            "search_result": search_result,
                        }
                        results.append(file_search_result)
                    else:
                        no_match_msg = f"No matches found for '{search_pattern}' in {file_path} (search mode: {search_mode})"
                        # For no matches, still store the result structure for consolidation
                        file_search_result = {
                            "file_path": file_path,
                            "matches": [],
                            "pattern_groups": {},
                            "search_result": no_match_msg,
                        }
                        results.append(file_search_result)

                elif mode == "stats":
                    # Get file statistics
                    stats = get_file_stats(file_path)

                    stats_text = f"""File Statistics for {file_path}:
Size: {stats['size_human']} ({stats['size_bytes']:,} bytes)
Total lines: {stats['line_count']:,}
Non-empty lines: {stats['non_empty_lines']:,}
Comment lines: {stats['comment_lines']:,}
Functions found at lines: {stats['function_lines'][:10]}{'...' if len(stats['function_lines']) > 10 else ''}
Classes found at lines: {stats['class_lines'][:10]}{'...' if len(stats['class_lines']) > 10 else ''}

Preview (first 20 lines):
{stats['preview']}"""

                    console_ui.show_tool_output(
                        f"File Statistics - {os.path.basename(file_path)}", stats_text
                    )
                    results.append(json.dumps(stats, indent=2))

                elif mode == "preview":
                    # Quick preview
                    stats = get_file_stats(file_path)
                    preview_content = stats["preview"]

                    language = detect_language_from_path(file_path)
                    title = f"{file_path} - Preview (first 20 lines of {stats['line_count']} total)"
                    console_ui.show_code_content(title, preview_content, 1, language)

                    preview_text = f"Preview of {file_path} ({stats['size_human']}, {stats['line_count']} lines):\n{preview_content}"
                    results.append(preview_text)

                elif mode == "diff":
                    # Compare files
                    if not comparison_path:
                        raise ValueError("comparison_path is required for diff mode")

                    diff_content = create_diff(file_path, comparison_path)

                    if diff_content.strip():
                        console_ui.show_code_content(
                            f"Diff: {file_path} vs {comparison_path}",
                            diff_content,
                            1,
                            "diff",
                        )
                        results.append(
                            f"Diff between {file_path} and {comparison_path}:\n{diff_content}"
                        )
                    else:
                        no_diff_msg = f"No differences found between {file_path} and {comparison_path}"
                        console_ui.show_tool_output(
                            "No Differences", no_diff_msg, success=True
                        )
                        results.append(no_diff_msg)

                else:
                    raise ValueError(f"Unknown mode: {mode}")

            except Exception as e:
                error_msg = f"Error processing {file_path}: {str(e)}"
                console_ui.show_file_error(file_path, str(e))
                results.append(error_msg)

        # Special handling for search mode - consolidate results from multiple files
        if mode == "search" and results:
            return consolidate_search_results(
                results, search_pattern, search_mode, len(all_files)
            )

        return "\n\n".join(results) if results else f"No results for mode '{mode}'"

    except Exception as e:
        error_response = f"Error in get_file_content: {str(e)}"
        console_ui.show_tool_error("get_file_content", str(e))
        return error_response


def consolidate_search_results(
    search_results: List[Dict], search_pattern: str, search_mode: str, total_files: int
) -> str:
    """
    Consolidate search results from multiple files into a unified report.

    Args:
        search_results: List of file search result dictionaries
        search_pattern: Original search pattern
        search_mode: Search mode used (smart/regex)
        total_files: Total number of files searched

    Returns:
        Consolidated search report string
    """
    # Extract search result dictionaries (filter out error strings)
    file_results = [r for r in search_results if isinstance(r, dict)]

    if not file_results:
        # Fallback to string concatenation if no structured results
        return "\n\n".join([str(r) for r in search_results])

    # Calculate totals
    total_matches = sum(len(result.get("matches", [])) for result in file_results)
    files_with_matches = [result for result in file_results if result.get("matches")]
    files_without_matches = [
        result for result in file_results if not result.get("matches")
    ]

    # Build consolidated report
    consolidated = f"""🔍 CONSOLIDATED SEARCH RESULTS 🔍
Search Pattern: {search_pattern}
Search Mode: {search_mode}
Files Searched: {total_files}
Files with Matches: {len(files_with_matches)}
Total Matches Found: {total_matches}

"""

    if files_with_matches:
        consolidated += "📋 SUMMARY BY FILE:\n"
        for result in files_with_matches:
            file_path = result["file_path"]
            matches = result["matches"]
            consolidated += f"  📄 {file_path}: {len(matches)} matches\n"

        consolidated += "\n📝 DETAILED RESULTS:\n\n"

        # Show detailed results for files with matches (limit to prevent overwhelming output)
        max_files_to_show = 5
        for i, result in enumerate(files_with_matches[:max_files_to_show]):
            file_path = result["file_path"]
            search_result = result["search_result"]

            consolidated += f"{'=' * 80}\n"
            consolidated += f"📄 FILE {i + 1}/{len(files_with_matches)}: {file_path}\n"
            consolidated += f"{'=' * 80}\n"
            consolidated += search_result + "\n\n"

        if len(files_with_matches) > max_files_to_show:
            remaining = len(files_with_matches) - max_files_to_show
            consolidated += f"... and {remaining} more files with matches (truncated for readability)\n\n"

    if files_without_matches:
        consolidated += f"📝 FILES WITHOUT MATCHES ({len(files_without_matches)}):\n"
        for result in files_without_matches[:10]:  # Show up to 10 files without matches
            file_path = result["file_path"]
            consolidated += f"  📄 {file_path}\n"

        if len(files_without_matches) > 10:
            remaining = len(files_without_matches) - 10
            consolidated += f"  ... and {remaining} more files without matches\n"

    # Show the consolidated result in UI
    title = (
        f"Search Results - {search_pattern} ({search_mode} mode) - {total_files} files"
    )
    console_ui.show_tool_output(title, consolidated)

    return consolidated


@tool(name="get_file_info")
def get_file_info(file_path: str) -> str:
    """
    Get comprehensive information about a file to help decide what chunks to read.

    This function provides detailed metadata about a file including size, line count,
    structure overview, and content analysis to help you make informed decisions
    about how to read the file efficiently.

    Args:
        file_path: Path to the file to inspect

    Returns:
        Comprehensive file information including structure analysis

    Examples:
        # Get basic file info
        get_file_info("src/main.py")

        # Use info to decide how to read large files
        info = get_file_info("large_file.py")
        # Then: get_file_content("large_file.py", mode="lines", start_line=100, lines_count=50)
    """
    try:
        console_ui.show_tool_input("get_file_info", "📊", {"file_path": file_path})

        # Use the enhanced stats function
        stats = get_file_stats(file_path)

        # Enhanced analysis
        info_text = f"""File Information: {file_path}

📏 Size: {stats['size_human']} ({stats['size_bytes']:,} bytes)
📄 Lines: {stats['line_count']:,} total, {stats['non_empty_lines']:,} non-empty
💬 Comments: {stats['comment_lines']:,} lines
🔧 Functions: {len(stats['function_lines'])} found at lines {stats['function_lines'][:5]}{'...' if len(stats['function_lines']) > 5 else ''}
🏗️ Classes: {len(stats['class_lines'])} found at lines {stats['class_lines'][:5]}{'...' if len(stats['class_lines']) > 5 else ''}

📖 Reading Recommendations:
"""

        # Add reading recommendations based on file size
        if stats["line_count"] < 100:
            info_text += "• Small file - use mode='view' to read entire file\n"
        elif stats["line_count"] < 500:
            info_text += "• Medium file - use mode='lines' with chunks of ~100 lines\n"
            info_text += "• Suggested chunks: lines 1-100, 101-200, etc.\n"
        else:
            info_text += "• Large file - use mode='lines' with targeted chunks\n"
            info_text += "• Consider mode='search' to find specific content\n"
            info_text += "• Use mode='preview' for quick overview\n"

        if stats["function_lines"]:
            info_text += f"• Functions at lines: {', '.join(map(str, stats['function_lines'][:10]))}\n"

        if stats["class_lines"]:
            info_text += f"• Classes at lines: {', '.join(map(str, stats['class_lines'][:10]))}\n"

        info_text += f"\n📋 Preview (first 20 lines):\n{stats['preview']}"

        console_ui.show_tool_output("File Information", info_text)
        return info_text

    except Exception as e:
        error_msg = f"Error getting file info for {file_path}: {str(e)}"
        console_ui.show_tool_error("get_file_info", str(e))
        return error_msg
