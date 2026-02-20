"""
Optimized file reading tool with concise documentation.
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
    excludes = [
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

    if gitignore_path.exists():
        try:
            with open(gitignore_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        excludes.append(
                            line.rstrip("/") if line.endswith("/") else line
                        )
        except Exception:
            pass
    return excludes


def should_exclude_path(file_path: str, excludes: List[str]) -> bool:
    """Check if a file path should be excluded based on gitignore patterns."""
    path_obj = Path(file_path)
    path_str = str(path_obj)
    path_parts = path_obj.parts

    for exclude in excludes:
        if exclude in path_str or any(exclude in part for part in path_parts):
            return True
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
    """Find files matching a pattern with gitignore exclusion support."""
    excludes = get_gitignore_excludes()
    matching_files = []

    try:
        if os.path.isfile(pattern):
            if not should_exclude_path(pattern, excludes):
                matching_files.append(pattern)
        elif os.path.isdir(pattern):
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
            if recursive and "**" not in pattern:
                pattern = f"**/{pattern}"
            for file_path in glob.glob(pattern, recursive=recursive):
                if os.path.isfile(file_path) and not should_exclude_path(
                    file_path, excludes
                ):
                    matching_files.append(file_path)
                    if len(matching_files) >= max_files:
                        break
    except Exception:
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
        ".json": "json",
        ".xml": "xml",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".md": "markdown",
        ".sql": "sql",
        ".sh": "bash",
        ".java": "java",
        ".cpp": "cpp",
        ".c": "c",
        ".cs": "csharp",
        ".php": "php",
        ".rb": "ruby",
        ".go": "go",
        ".rs": "rust",
    }
    return language_map.get(ext, "text")


def read_file_lines(
    file_path: str, start_line: int = 1, end_line: Optional[int] = None
) -> tuple[List[str], Dict[str, Any]]:
    """Read specific lines from file with metadata."""
    file_path = os.path.expanduser(file_path)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    if not os.path.isfile(file_path):
        raise ValueError(f"Path is not a file: {file_path}")

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        all_lines = f.readlines()

    total_lines = len(all_lines)
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

    lines = all_lines[start_line - 1 : end_line]
    metadata = {
        "total_lines": total_lines,
        "start_line": start_line,
        "end_line": end_line,
        "lines_read": len(lines),
        "file_path": file_path,
    }
    return lines, metadata


def get_smart_search_patterns_for_file(term: str) -> List[str]:
    """Generate smart search patterns for file content search."""
    import re

    patterns = []
    escaped_term = re.escape(term)
    patterns.append(escaped_term)
    patterns.append(f"\\b{escaped_term}\\b")

    if "(" in term:
        func_name = term.split("(")[0]
        escaped_func = re.escape(func_name)
        patterns.extend(
            [
                f"{escaped_func}\\s*\\(",
                f"\\.{escaped_func}\\s*\\(",
                f"\\w+\\.{escaped_func}\\s*\\(",
            ]
        )
    elif "." in term:
        parts = term.split(".")
        if len(parts) == 2:
            obj_part, method_part = parts
            escaped_obj = re.escape(obj_part)
            escaped_method = re.escape(method_part)
            patterns.extend(
                [
                    f"{escaped_obj}\\.{escaped_method}",
                    f"\\w*{escaped_obj}\\w*\\.{escaped_method}",
                    f"\\.{escaped_method}",
                ]
            )
    elif term.isidentifier():
        escaped_term = re.escape(term)
        patterns.extend(
            [
                f"\\b{escaped_term}\\s*[=:]",
                f"def\\s+{escaped_term}\\s*\\(",
                f"class\\s+{escaped_term}\\b",
                f"import\\s+.*{escaped_term}",
                f"from\\s+.*{escaped_term}",
            ]
        )

    return patterns


def search_in_file(
    file_path: str, pattern: str, context_lines: int = 2, search_mode: str = "smart"
) -> List[Dict[str, Any]]:
    """Search for a pattern in a file with context lines."""
    import re

    file_path = os.path.expanduser(file_path)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    matches = []
    seen_lines = set()

    patterns = (
        get_smart_search_patterns_for_file(pattern)
        if search_mode == "smart"
        else [pattern]
    )

    for search_pattern in patterns:
        try:
            for i, line in enumerate(lines):
                if (
                    re.search(search_pattern, line, re.IGNORECASE)
                    and i not in seen_lines
                ):
                    seen_lines.add(i)
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
            continue

    matches.sort(key=lambda x: x["line_number"])
    return matches


def generate_file_preview(file_path: str, max_lines: int = 20) -> str:
    """Generate file preview with specified number of lines."""
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        preview_lines = []
        for i, line in enumerate(f):
            if i >= max_lines:
                break
            preview_lines.append(line.rstrip())
    return "\n".join(preview_lines)


def get_file_stats(
    file_path: str, include_preview: bool = False, preview_lines: int = 20
) -> Dict[str, Any]:
    """Get comprehensive file statistics."""
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
            i = 0
            preview_content = []
            for i, line in enumerate(f, 1):
                stripped = line.strip()
                if stripped:
                    stats["non_empty_lines"] += 1
                if include_preview and i <= preview_lines:
                    preview_content.append(line.rstrip())
                if stripped.startswith(("#", "//", "/*", "*", "<!--")):
                    stats["comment_lines"] += 1
                if any(
                    keyword in stripped
                    for keyword in ["def ", "function ", "func ", "async def"]
                ):
                    stats["function_lines"].append(i)
                if any(
                    keyword in stripped
                    for keyword in ["class ", "interface ", "struct "]
                ):
                    stats["class_lines"].append(i)

            stats["line_count"] = i

        stats["preview"] = "\n".join(preview_content) if include_preview else ""
        if stats["size_bytes"] < 1024 * 1024:
            stats["size_human"] = f"{stats['size_bytes'] / 1024:.2f} KB"
        else:
            stats["size_human"] = f"{stats['size_bytes'] / (1024 * 1024):.2f} MB"
    except Exception as e:
        stats["error"] = str(e)

    return stats


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
    recursive: bool = True,
    max_files: int = 100,
) -> str:
    """
    Advanced file reading with multiple modes. Supports wildcards and multi-file operations.

    Args:
        path: File path(s), supports wildcards (*.py, src/**/*.js)
        mode: Reading mode - view, find, lines, search, stats, preview, diff
        start_line: Starting line for 'lines' mode (1-based)
        end_line: Ending line for 'lines' mode (inclusive)
        lines_count: Number of lines to read from start_line
        show_line_numbers: Whether to show line numbers in output
        search_pattern: Pattern for 'search' mode
        search_mode: 'smart' (auto-patterns) or 'regex' (direct pattern)
        context_lines: Context lines for search results
        recursive: Whether to search directories recursively
        max_files: Max files to process in multi-file modes

    Examples:
        get_file_content("*.py", mode="find")  # Find Python files
        get_file_content("main.py", mode="lines", start_line=10, lines_count=20)
        get_file_content("src/", mode="search", search_pattern="createTrip", search_mode="smart")
    """
    # [Implementation remains the same but with reduced docstring]
    # ... [keeping all the existing implementation code] ...

    # Show tool input
    tool_params = {
        "path": path,
        "mode": mode,
        "start_line": start_line,
        "end_line": end_line,
        "lines_count": lines_count,
        "show_line_numbers": show_line_numbers,
        "search_pattern": search_pattern,
        "search_mode": search_mode,
        "context_lines": context_lines,
        "recursive": recursive,
        "max_files": max_files,
    }
    console_ui.show_tool_input("get_file_content", "📄", tool_params)

    try:
        paths = split_path_list(path)
        all_files = []

        for path_pattern in paths:
            if mode == "find":
                files = find_files(
                    path_pattern, recursive=recursive, max_files=max_files
                )
                all_files.extend(files)
            else:
                if os.path.isfile(path_pattern):
                    all_files.append(path_pattern)
                else:
                    files = find_files(
                        path_pattern, recursive=recursive, max_files=max_files
                    )
                    all_files.extend(files)

        all_files = sorted(list(set(all_files)))

        if not all_files and mode != "find":
            error_msg = f"No files found matching pattern(s): {', '.join(paths)}"
            console_ui.show_file_error(path, error_msg)
            return error_msg

        if mode == "find":
            if all_files:
                result = f"Found {len(all_files)} files:\n\n"
                dirs = {}
                for file_path in all_files:
                    dir_path = os.path.dirname(file_path) or "."
                    if dir_path not in dirs:
                        dirs[dir_path] = []
                    dirs[dir_path].append(os.path.basename(file_path))

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

        results = []
        for file_path in all_files[:max_files]:
            try:
                if mode == "view":
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    language = detect_language_from_path(file_path)
                    console_ui.show_code_content(file_path, content, 1, language)
                    results.append(f"Content of {file_path}:\n{content}")

                elif mode == "lines":
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

                elif mode == "search":
                    if not search_pattern:
                        raise ValueError("search_pattern is required for search mode")
                    matches = search_in_file(
                        file_path, search_pattern, context_lines, search_mode
                    )

                    if matches:
                        search_result = (
                            f"Found {len(matches)} matches in {file_path}:\n"
                        )
                        for i, match in enumerate(matches[:5], 1):
                            search_result += (
                                f"  Match {i} (line {match['line_number']}):\n"
                            )
                            for ctx_line in match["context_before"]:
                                search_result += f"    {ctx_line}\n"
                            search_result += f"  > {match['match_line']} <-- MATCH\n"
                            for ctx_line in match["context_after"]:
                                search_result += f"    {ctx_line}\n"
                            search_result += "\n"

                        if len(matches) > 5:
                            search_result += (
                                f"    ... and {len(matches) - 5} more matches\n"
                            )

                        file_search_result = {
                            "file_path": file_path,
                            "matches": matches,
                            "search_result": search_result,
                        }
                        results.append(file_search_result)
                    else:
                        no_match_msg = (
                            f"No matches found for '{search_pattern}' in {file_path}"
                        )
                        file_search_result = {
                            "file_path": file_path,
                            "matches": [],
                            "search_result": no_match_msg,
                        }
                        results.append(file_search_result)

                elif mode == "stats":
                    stats = get_file_stats(file_path)
                    stats_text = f"""File Statistics for {file_path}:
Size: {stats['size_human']} ({stats['size_bytes']:,} bytes)
Lines: {stats['line_count']:,} total, {stats['non_empty_lines']:,} non-empty
Functions: {len(stats['function_lines'])} at lines {stats['function_lines'][:5]}
Classes: {len(stats['class_lines'])} at lines {stats['class_lines'][:5]}"""
                    console_ui.show_tool_output(
                        f"File Statistics - {os.path.basename(file_path)}", stats_text
                    )
                    results.append(json.dumps(stats, indent=2))

                elif mode == "preview":
                    stats = get_file_stats(
                        file_path, include_preview=True, preview_lines=20
                    )
                    preview_content = stats["preview"]

                    language = detect_language_from_path(file_path)
                    title = f"{file_path} - Preview (first 20 lines of {stats['line_count']} total)"
                    console_ui.show_code_content(title, preview_content, 1, language)

                    preview_text = f"Preview of {file_path} ({stats['size_human']}, {stats['line_count']} lines):\n{preview_content}"
                    results.append(preview_text)

                else:
                    raise ValueError(f"Unknown mode: {mode}")

            except Exception as e:
                error_msg = f"Error processing {file_path}: {str(e)}"
                console_ui.show_file_error(file_path, str(e))
                results.append(error_msg)

        if mode == "search" and results:
            # Consolidate search results
            file_results = [r for r in results if isinstance(r, dict)]
            if file_results:
                total_matches = sum(
                    len(result.get("matches", [])) for result in file_results
                )
                files_with_matches = [
                    result for result in file_results if result.get("matches")
                ]

                consolidated = (
                    f"🔍 Search Results for '{search_pattern}' ({search_mode} mode):\n"
                )
                consolidated += f"Files searched: {len(all_files)}, Files with matches: {len(files_with_matches)}, Total matches: {total_matches}\n\n"

                for result in files_with_matches[
                    :3
                ]:  # Limit to 3 files for readability
                    consolidated += (
                        f"📄 {result['file_path']}:\n{result['search_result']}\n"
                    )

                if len(files_with_matches) > 3:
                    consolidated += f"... and {len(files_with_matches) - 3} more files with matches\n"

                console_ui.show_tool_output(
                    f"Search Results - {search_pattern}", consolidated
                )
                return consolidated

        return "\n\n".join(results) if results else f"No results for mode '{mode}'"

    except Exception as e:
        error_response = f"Error in get_file_content: {str(e)}"
        console_ui.show_tool_error("get_file_content", str(e))
        return error_response


@tool(name="get_file_info")
def get_file_info(file_path: str) -> str:
    """
    Get file information to help decide reading strategy.

    Args:
        file_path: Path to the file to inspect

    Returns:
        File information including size, lines, structure overview

    Examples:
        get_file_info("src/main.py")  # Get basic info
        # Then: get_file_content("main.py", mode="lines", start_line=100, lines_count=50)
    """
    try:
        console_ui.show_tool_input("get_file_info", "📊", {"file_path": file_path})
        stats = get_file_stats(file_path)

        info_text = f"""File: {file_path}
Size: {stats['size_human']} ({stats['size_bytes']:,} bytes)
Lines: {stats['line_count']:,} total, {stats['non_empty_lines']:,} non-empty
Functions: {len(stats['function_lines'])} at lines {stats['function_lines'][:5]}
Classes: {len(stats['class_lines'])} at lines {stats['class_lines'][:5]}

Reading recommendations:"""

        if stats["line_count"] < 100:
            info_text += "\n• Small file - use mode='view'"
        elif stats["line_count"] < 500:
            info_text += "\n• Medium file - use mode='lines' with ~100 line chunks"
        else:
            info_text += "\n• Large file - use mode='lines' with targeted chunks or mode='search'"
        console_ui.show_tool_output("File Information", info_text)
        return info_text

    except Exception as e:
        error_msg = f"Error getting file info for {file_path}: {str(e)}"
        console_ui.show_tool_error("get_file_info", str(e))
        return error_msg
