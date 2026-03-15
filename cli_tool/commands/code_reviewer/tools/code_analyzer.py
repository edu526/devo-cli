"""
Optimized code analysis tools with concise documentation.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from strands import tool

from cli_tool.core.ui.console_ui import console_ui


def get_smart_search_patterns(symbol_name: str) -> List[str]:
    """Generate smart search patterns for complex symbols."""
    import re

    patterns = []
    escaped_full = re.escape(symbol_name)
    patterns.append(f"\\b{escaped_full}\\b")

    # Function calls like "createTrip(cache)" -> extract "createTrip"
    func_call_match = re.match(r"^([a-zA-Z_]\w*)\s*\(", symbol_name)
    if func_call_match:
        base_name = func_call_match.group(1)
        escaped_base = re.escape(base_name)
        patterns.extend(
            [
                f"\\b{escaped_base}\\b",
                f"\\b{escaped_base}\\s*\\(",
                f"\\.{escaped_base}\\s*\\(",
            ]
        )

    # Method calls like "obj.method" -> extract "method"
    method_call_match = re.match(r"^.*\.([a-zA-Z_]\w*)", symbol_name)
    if method_call_match:
        method_name = method_call_match.group(1)
        escaped_method = re.escape(method_name)
        patterns.extend(
            [
                f"\\b{escaped_method}\\b",
                f"\\.{escaped_method}\\b",
                f"\\.{escaped_method}\\s*\\(",
            ]
        )

    # Remove duplicates
    seen = set()
    unique_patterns = []
    for pattern in patterns:
        if pattern not in seen:
            seen.add(pattern)
            unique_patterns.append(pattern)
    return unique_patterns


def _gitignore_line_to_excludes(line: str) -> List[str]:
    """Convert a single .gitignore pattern line into grep exclude flags."""
    if line.endswith("/"):
        return [f"--exclude-dir='{line.rstrip('/')}'"]
    if "*" in line or "?" in line:
        return [f"--exclude='{line}'"]
    return [f"--exclude-dir='{line}'", f"--exclude='{line}'"]


def _read_gitignore_lines(gitignore_path: Path) -> List[str]:
    """Read and return non-empty, non-comment lines from a .gitignore file."""
    try:
        with open(gitignore_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
    except Exception:
        return []


def _parse_gitignore_patterns(gitignore_path: Path) -> List[str]:
    """Parse .gitignore file and return grep exclude flags for each pattern."""
    excludes = []
    for line in _read_gitignore_lines(gitignore_path):
        excludes.extend(_gitignore_line_to_excludes(line))
    return excludes


def get_gitignore_excludes() -> str:
    """Generate grep exclude patterns from .gitignore file."""
    gitignore_path = Path(".gitignore")
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
        ".DS_Store",
        "Thumbs.db",
    ]

    excludes = [f"--exclude-dir='{pattern}'" for pattern in default_excludes]

    if gitignore_path.exists():
        excludes.extend(_parse_gitignore_patterns(gitignore_path))

    return " ".join(excludes)


def parse_grep_results(output: str, _symbol_name: str) -> List[Dict[str, Any]]:
    """Parse grep output into structured results."""
    results = []
    for line in output.strip().split("\n"):
        if ":" in line:
            try:
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    file_path = parts[0]
                    line_number = int(parts[1])
                    content = parts[2]
                    preview = content[:100] + "..." if len(content) > 100 else content
                    results.append(
                        {
                            "file_path": file_path,
                            "line_number": line_number,
                            "content": content.strip(),
                            "preview": preview,
                        }
                    )
            except (ValueError, IndexError):
                continue
    return results


def _run_grep_search(pattern: str, include_pattern: str, exclude_pattern: str, case_sensitive: bool) -> List[Dict[str, Any]]:
    """Run a single grep search and return parsed results."""
    case_flag = "" if case_sensitive else "-i"
    cmd = f"grep -r -n -E {case_flag} {include_pattern} {exclude_pattern} '{pattern}' ."
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        cwd=os.getcwd(),
        encoding="utf-8",
        errors="ignore",
    )
    if result.returncode == 0 and result.stdout and result.stdout.strip():
        return parse_grep_results(result.stdout, pattern)
    return []


def _collect_unique_results(
    search_patterns: List[str],
    include_pattern: str,
    exclude_pattern: str,
    case_sensitive: bool,
    symbol_or_pattern: str,
) -> List[Dict[str, Any]]:
    """Run all grep patterns and collect deduplicated results."""
    all_results = []
    seen_locations: set = set()
    for pattern in search_patterns:
        parsed_results = _run_grep_search(pattern, include_pattern, exclude_pattern, case_sensitive)
        for res in parsed_results:
            location_key = f"{res['file_path']}:{res['line_number']}"
            if location_key not in seen_locations:
                all_results.append(res)
                seen_locations.add(location_key)
    return all_results


def _group_results_by_file(results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group a list of result dicts by their file_path key."""
    files_dict: Dict[str, List[Dict[str, Any]]] = {}
    for res in results:
        file_path = res["file_path"]
        if file_path not in files_dict:
            files_dict[file_path] = []
        files_dict[file_path].append(res)
    return files_dict


def _build_search_response(
    all_results: List[Dict[str, Any]],
    max_results: int,
    symbol_or_pattern: str,
    use_regex: bool,
    file_extensions: str,
) -> str:
    """Build formatted response string for search_code_references results."""
    if not all_results:
        search_type = "regex pattern" if use_regex else "symbol"
        search_label = f"Regex: {symbol_or_pattern}" if use_regex else symbol_or_pattern
        console_ui.show_search_results(search_label, [])
        return f"No matches found for {search_type} '{symbol_or_pattern}' in files with extensions: {file_extensions}"

    limited_results = all_results[:max_results]
    files_dict = _group_results_by_file(limited_results)
    search_type = "regex pattern" if use_regex else "symbol"
    response = f"Found {len(limited_results)} matches for {search_type} '{symbol_or_pattern}' in {len(files_dict)} files:\n\n"

    for file_path, file_results in files_dict.items():
        response += f"📄 {file_path} ({len(file_results)} matches):\n"
        for res in file_results:
            response += f"  Line {res['line_number']}: {res['preview']}\n"
        response += "\n"

    if len(all_results) > max_results:
        response += f"... and {len(all_results) - max_results} more results\n"

    formatted_ui_results = [
        f"📄 {res['file_path']}:{res['line_number']}: {res['preview']}" for file_results in files_dict.values() for res in file_results
    ]
    search_label = f"Regex: {symbol_or_pattern}" if use_regex else symbol_or_pattern
    console_ui.show_search_results(
        search_label,
        formatted_ui_results,
        f"✅ Found {len(limited_results)} matches",
    )
    return response


@tool
def search_code_references(
    symbol_or_pattern: str,
    file_extensions: str = "py,js,ts,jsx,tsx",
    max_results: int = 50,
    use_regex: bool = False,
    case_sensitive: bool = False,
) -> str:
    """
    Search for symbol references across codebase with smart pattern matching.

    Args:
        symbol_or_pattern: Symbol name or regex pattern to search
        file_extensions: File extensions to search (default: py,js,ts,jsx,tsx)
        max_results: Maximum results to return (default: 50)
        use_regex: If True, use as regex; if False, use smart symbol matching
        case_sensitive: Case sensitive search (default: False)

    Examples:
        search_code_references("createTrip", "py,js")  # Smart symbol search
        search_code_references("createTrip\\\\(", "js", use_regex=True)  # Regex search
    """
    console_ui.show_tool_input(
        "search_code_references",
        "🔍",
        {
            "symbol_or_pattern": symbol_or_pattern,
            "file_extensions": file_extensions,
            "max_results": max_results,
            "use_regex": use_regex,
            "case_sensitive": case_sensitive,
        },
    )

    try:
        extensions = [ext.strip() for ext in file_extensions.split(",")]
        include_pattern = " ".join([f"--include='*.{ext}'" for ext in extensions])
        exclude_pattern = get_gitignore_excludes()

        search_patterns = [symbol_or_pattern] if use_regex else get_smart_search_patterns(symbol_or_pattern)
        all_results = _collect_unique_results(search_patterns, include_pattern, exclude_pattern, case_sensitive, symbol_or_pattern)
        all_results.sort(key=lambda x: (x["file_path"], x["line_number"]))

        return _build_search_response(all_results, max_results, symbol_or_pattern, use_regex, file_extensions)

    except Exception as e:
        error_response = f"Error searching for {'regex pattern' if use_regex else 'symbol'}: {str(e)}"
        console_ui.show_tool_error("search_code_references", str(e))
        return error_response


def _build_definition_patterns(function_name: str) -> Dict[str, List[str]]:
    """Build language-specific grep patterns for function/class definitions."""
    escaped_name = re.escape(function_name)
    return {
        "py": [
            f"def {escaped_name}\\s*\\(",
            f"async def {escaped_name}\\s*\\(",
            f"class {escaped_name}\\s*[\\(:]",
        ],
        "js": [
            f"function {escaped_name}\\s*\\(",
            f"const {escaped_name}\\s*=",
            f"class {escaped_name}\\s*{{",
        ],
        "ts": [
            f"function {escaped_name}\\s*\\(",
            f"const {escaped_name}\\s*=",
            f"class {escaped_name}\\s*{{",
        ],
    }


def _try_parse_numbered_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse a grep output line (file:lineno:content) into a dict, or return None."""
    if ":" not in line:
        return None
    parts = line.split(":", 2)
    if len(parts) < 3:
        return None
    try:
        line_number = int(parts[1])
        return {"file": parts[0], "line_number": line_number, "content": parts[2]}
    except ValueError:
        return None


def _flush_current_match(
    current_match: Dict[str, Any],
    current_file: Optional[str],
    seen_locations: set,
    results: List[Dict[str, Any]],
) -> None:
    """Append current_match to results if it's valid and not already seen."""
    if current_match and current_file:
        location_key = f"{current_file}:{current_match.get('line_number', 0)}"
        if location_key not in seen_locations:
            results.append(current_match)
            seen_locations.add(location_key)


def _process_grep_context_output(output: str, results: List[Dict[str, Any]], seen_locations: set) -> None:
    """Parse grep -A/-B context output and append unique matches to results."""
    lines = output.split("\n")
    current_file: Optional[str] = None
    current_match: Dict[str, Any] = {}

    for line in lines:
        if line.strip() == "--":
            _flush_current_match(current_match, current_file, seen_locations, results)
            current_match = {}
            current_file = None
            continue

        parsed = _try_parse_numbered_line(line)
        if parsed is None:
            continue

        file_candidate = parsed["file"]
        line_number = parsed["line_number"]
        content = parsed["content"]

        # Detect whether this is a match line or a context line.
        # grep uses ':' as separator for match lines and '-' for context lines.
        # We identify match lines by checking the raw separator character.
        raw_sep = line[len(file_candidate) : len(file_candidate) + 1] if len(line) > len(file_candidate) else ""

        if raw_sep == ":" and (not current_match or file_candidate != current_file):
            # New match line — start a fresh match entry
            _flush_current_match(current_match, current_file, seen_locations, results)
            current_file = file_candidate
            current_match = {
                "file_path": current_file,
                "line_number": line_number,
                "definition_line": content.strip(),
                "context": [],
            }
        elif current_match:
            current_match["context"].append({"line_number": line_number, "content": content.rstrip()})

    _flush_current_match(current_match, current_file, seen_locations, results)


def _run_definition_grep(pattern: str, ext: str, context_lines: int, exclude_pattern: str) -> str:
    """Run grep for a single definition pattern and return raw stdout."""
    cmd = f"grep -r -n -A {context_lines} -B {context_lines} -E --include='*.{ext}' {exclude_pattern} '{pattern}' ."
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        cwd=os.getcwd(),
        encoding="utf-8",
        errors="ignore",
    )
    if result.returncode == 0 and result.stdout and result.stdout.strip():
        return result.stdout
    return ""


def _build_definition_response(results: List[Dict[str, Any]], function_name: str) -> str:
    """Format search_function_definition results into a human-readable string."""
    if not results:
        console_ui.show_function_definitions(function_name, [])
        return f"No definitions found for function '{function_name}'"

    response = f"Found {len(results)} definition(s) for '{function_name}':\n\n"
    for i, match in enumerate(results, 1):
        response += f"Definition {i}: {match['file_path']}:{match['line_number']}\n"
        for ctx in match.get("context", []):
            if ctx["line_number"] == match["line_number"]:
                response += f">>> {ctx['line_number']:4d}: {ctx['content']} <<<\n"
            else:
                response += f"    {ctx['line_number']:4d}: {ctx['content']}\n"
        response += "\n"

    ui_results = [f"📍 {match['file_path']}:{match['line_number']}: {match['definition_line'][:80]}..." for match in results]
    console_ui.show_function_definitions(function_name, ui_results)
    return response


@tool
def search_function_definition(function_name: str, file_extensions: str = "py,js,ts", context_lines: int = 3) -> str:
    """
    Find function definitions with language-aware patterns.

    Args:
        function_name: Function name to find
        file_extensions: File extensions to search
        context_lines: Context lines around definition

    Examples:
        search_function_definition("calculate_tax", "py")
        search_function_definition("processData", "js,ts")
    """
    console_ui.show_tool_input(
        "search_function_definition",
        "🔧",
        {
            "function_name": function_name,
            "file_extensions": file_extensions,
            "context_lines": context_lines,
        },
    )

    try:
        extensions = [ext.strip() for ext in file_extensions.split(",")]
        exclude_pattern = get_gitignore_excludes()
        patterns = _build_definition_patterns(function_name)

        results: List[Dict[str, Any]] = []
        seen_locations: set = set()

        for ext in extensions:
            if ext not in patterns:
                continue
            for pattern in patterns[ext]:
                raw_output = _run_definition_grep(pattern, ext, context_lines, exclude_pattern)
                if raw_output:
                    _process_grep_context_output(raw_output, results, seen_locations)

        return _build_definition_response(results, function_name)

    except Exception as e:
        error_response = f"Error searching for function definition: {str(e)}"
        console_ui.show_tool_error("search_function_definition", str(e))
        return error_response


def _build_import_patterns(escaped_symbol: str, is_python: bool, is_javascript: bool) -> List[str]:
    """Return language-specific regex patterns for detecting import statements."""
    if is_python:
        return [
            rf"from\s+.*\s+import\s+.*\b{escaped_symbol}\b",
            rf"import\s+.*\b{escaped_symbol}\b",
            rf"from\s+\b{escaped_symbol}\b",
            rf"import\s+\b{escaped_symbol}\b",
        ]
    if is_javascript:
        return [
            rf"import\s+.*\b{escaped_symbol}\b.*from",
            rf"import\s+\b{escaped_symbol}\b",
            rf'require\s*\(\s*[\'"`].*{escaped_symbol}',
            rf"const\s+.*\b{escaped_symbol}\b.*=.*require",
        ]
    return []


def _classify_usage_type(symbol_name: str, line_stripped: str) -> str:
    """Determine the usage category of a symbol occurrence in a line of code."""
    if "(" in line_stripped and symbol_name in line_stripped.split("(")[0]:
        return "function_call"
    if "=" in line_stripped and symbol_name in line_stripped.split("=")[0]:
        return "assignment"
    if "." in line_stripped and f"{symbol_name}." in line_stripped:
        return "attribute_access"
    if line_stripped.startswith("class ") and symbol_name in line_stripped:
        return "inheritance"
    if any(keyword in line_stripped for keyword in ["def ", "function "]):
        return "in_definition"
    return "reference"


def _is_import_line(line_stripped: str, symbol_name: str, import_patterns: List[str]) -> bool:
    """Return True if the given line matches any import pattern for symbol_name."""
    if import_patterns:
        return any(re.search(p, line_stripped, re.IGNORECASE) for p in import_patterns)
    has_import = "import" in line_stripped and symbol_name in line_stripped
    has_from = "from" in line_stripped and symbol_name in line_stripped
    has_require = "require" in line_stripped and symbol_name in line_stripped
    return has_import or has_from or has_require


def _scan_lines_for_symbol(
    lines: List[str],
    symbol_name: str,
    import_patterns: List[str],
) -> tuple:
    """Scan file lines and return (imports list, usages list) for symbol_name."""
    imports = []
    usages = []
    escaped_symbol = re.escape(symbol_name)

    for i, line in enumerate(lines, 1):
        line_stripped = line.strip()
        if _is_import_line(line_stripped, symbol_name, import_patterns):
            imports.append({"line_number": i, "content": line_stripped, "type": "import"})
        elif symbol_name in line_stripped and re.search(rf"\b{escaped_symbol}\b", line_stripped):
            usage_type = _classify_usage_type(symbol_name, line_stripped)
            usages.append({"line_number": i, "content": line_stripped, "type": usage_type})

    return imports, usages


def _build_usage_section(symbol_name: str, usages: List[Dict[str, Any]]) -> str:
    """Format the USAGES section of the analyze_import_usage response."""
    if not usages:
        return f"🔍 No usages found for '{symbol_name}'\n\n"

    usage_by_type: Dict[str, List[Dict[str, Any]]] = {}
    for usage in usages:
        usage_type = usage.get("type", "unknown")
        if usage_type not in usage_by_type:
            usage_by_type[usage_type] = []
        usage_by_type[usage_type].append(usage)

    section = f"🔍 USAGES ({len(usages)}):\n"
    for usage_type, type_usages in usage_by_type.items():
        section += f"  {usage_type.upper()} ({len(type_usages)}):\n"
        for usage in type_usages[:5]:
            section += f"    Line {usage['line_number']:3d}: {usage['content']}\n"
        if len(type_usages) > 5:
            section += f"    ... and {len(type_usages) - 5} more\n"
        section += "\n"
    return section


def _build_summary_section(imports: List[Dict[str, Any]], usages: List[Dict[str, Any]]) -> str:
    """Format the SUMMARY section including any detected issues."""
    section = "📊 SUMMARY:\n"
    section += f"  Total imports: {len(imports)}\n"
    section += f"  Total usages: {len(usages)}\n"

    issues = []
    if imports and not usages:
        issues.append("⚠️ Symbol imported but never used")
    elif usages and not imports:
        issues.append("⚠️ Symbol used but no imports found")
    elif len(imports) > 1:
        issues.append("⚠️ Symbol imported multiple times")

    if issues:
        section += "  Issues:\n"
        for issue in issues:
            section += f"    {issue}\n"
    else:
        section += "  ✅ No issues detected\n"
    return section


@tool
def analyze_import_usage(symbol_name: str, file_path: str, show_context: bool = True) -> str:  # noqa: ARG001
    """
    Analyze symbol imports and usage in a file.

    Args:
        symbol_name: Symbol to analyze
        file_path: File to analyze
        show_context: Show context lines around usages

    Examples:
        analyze_import_usage("UserModel", "src/views.py")
        analyze_import_usage("useState", "components/Form.jsx")
    """
    console_ui.show_tool_input(
        "analyze_import_usage",
        "📦",
        {
            "symbol_name": symbol_name,
            "file_path": file_path,
            "show_context": show_context,
        },
    )

    try:
        full_path = Path(file_path)
        if not full_path.exists():
            console_ui.show_file_error(file_path, "File not found")
            return f"File not found: {file_path}"

        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            lines = content.splitlines()

        file_ext = full_path.suffix.lower()
        is_python = file_ext == ".py"
        is_javascript = file_ext in [".js", ".jsx", ".ts", ".tsx"]

        escaped_symbol = re.escape(symbol_name)
        import_patterns = _build_import_patterns(escaped_symbol, is_python, is_javascript)
        imports, usages = _scan_lines_for_symbol(lines, symbol_name, import_patterns)

        result = f"Analysis of '{symbol_name}' in {file_path}:\n"
        result += f"{'=' * 60}\n\n"

        if imports:
            result += f"📥 IMPORTS ({len(imports)}):\n"
            for imp in imports:
                result += f"  Line {imp['line_number']:3d}: {imp['content']}\n"
            result += "\n"
        else:
            result += f"📥 No imports found for '{symbol_name}'\n\n"

        result += _build_usage_section(symbol_name, usages)
        result += _build_summary_section(imports, usages)

        import_lines = [f"Line {imp['line_number']}: {imp['content']}" for imp in imports]
        usage_lines = [f"Line {usage['line_number']}: {usage['content']}" for usage in usages]
        console_ui.show_import_analysis(symbol_name, file_path, import_lines, usage_lines)
        return result

    except Exception as e:
        error_response = f"Error analyzing imports in {file_path}: {str(e)}"
        console_ui.show_tool_error("analyze_import_usage", str(e))
        return error_response
