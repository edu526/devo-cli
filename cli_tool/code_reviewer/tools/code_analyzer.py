"""
Optimized code analysis tools with concise documentation.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from strands import tool

from cli_tool.ui.console_ui import console_ui


def get_smart_search_patterns(symbol_name: str) -> List[str]:
    """Generate smart search patterns for complex symbols."""
    import re

    patterns = []
    escaped_full = re.escape(symbol_name)
    patterns.append(f"\\b{escaped_full}\\b")

    # Function calls like "createTrip(cache)" -> extract "createTrip"
    func_call_match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", symbol_name)
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
    method_call_match = re.match(r"^.*\.([a-zA-Z_][a-zA-Z0-9_]*)", symbol_name)
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


def get_gitignore_excludes() -> str:
    """Generate grep exclude patterns from .gitignore file."""
    gitignore_path = Path(".gitignore")
    excludes = []
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

    for pattern in default_excludes:
        excludes.append(f"--exclude-dir='{pattern}'")

    if gitignore_path.exists():
        try:
            with open(gitignore_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if line.endswith("/"):
                            excludes.append(f"--exclude-dir='{line.rstrip('/')}'")
                        elif "*" in line or "?" in line:
                            excludes.append(f"--exclude='{line}'")
                        else:
                            excludes.append(f"--exclude-dir='{line}'")
                            excludes.append(f"--exclude='{line}'")
        except Exception:
            pass
    return " ".join(excludes)


def parse_grep_results(output: str, symbol_name: str) -> List[Dict[str, Any]]:
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

        search_patterns = (
            [symbol_or_pattern]
            if use_regex
            else get_smart_search_patterns(symbol_or_pattern)
        )
        all_results = []
        seen_locations = set()

        for pattern in search_patterns:
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
                parsed_results = parse_grep_results(result.stdout, symbol_or_pattern)
                for res in parsed_results:
                    location_key = f"{res['file_path']}:{res['line_number']}"
                    if location_key not in seen_locations:
                        all_results.append(res)
                        seen_locations.add(location_key)

        if all_results:
            all_results.sort(key=lambda x: (x["file_path"], x["line_number"]))
            limited_results = all_results[:max_results]

            files_dict = {}
            for res in limited_results:
                file_path = res["file_path"]
                if file_path not in files_dict:
                    files_dict[file_path] = []
                files_dict[file_path].append(res)

            search_type = "regex pattern" if use_regex else "symbol"
            response = f"Found {len(limited_results)} matches for {search_type} '{symbol_or_pattern}' in {len(files_dict)} files:\n\n"

            for file_path, file_results in files_dict.items():
                response += f"📄 {file_path} ({len(file_results)} matches):\n"
                for res in file_results:
                    response += f"  Line {res['line_number']}: {res['preview']}\n"
                response += "\n"

            if len(all_results) > max_results:
                response += f"... and {len(all_results) - max_results} more results\n"

            formatted_ui_results = []
            for file_path, file_results in files_dict.items():
                for res in file_results:
                    formatted_ui_results.append(
                        f"📄 {res['file_path']}:{res['line_number']}: {res['preview']}"
                    )

            search_label = (
                f"Regex: {symbol_or_pattern}" if use_regex else symbol_or_pattern
            )
            console_ui.show_search_results(
                search_label,
                formatted_ui_results,
                f"✅ Found {len(limited_results)} matches",
            )
        else:
            search_type = "regex pattern" if use_regex else "symbol"
            response = f"No matches found for {search_type} '{symbol_or_pattern}' in files with extensions: {file_extensions}"
            search_label = (
                f"Regex: {symbol_or_pattern}" if use_regex else symbol_or_pattern
            )
            console_ui.show_search_results(search_label, [])

        return response

    except Exception as e:
        error_response = f"Error searching for {'regex pattern' if use_regex else 'symbol'}: {str(e)}"
        console_ui.show_tool_error("search_code_references", str(e))
        return error_response


@tool
def search_function_definition(
    function_name: str, file_extensions: str = "py,js,ts", context_lines: int = 3
) -> str:
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

        # Language-specific definition patterns
        escaped_name = re.escape(function_name)
        patterns = {
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

        results = []
        seen_locations = set()

        for ext in extensions:
            if ext in patterns:
                for pattern in patterns[ext]:
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

                    if (
                        result.returncode == 0
                        and result.stdout
                        and result.stdout.strip()
                    ):
                        lines = result.stdout.split("\n")
                        current_file = None
                        current_match = {}

                        for line in lines:
                            if line.strip() == "--":
                                if current_match and current_file:
                                    location_key = f"{current_file}:{current_match.get('line_number', 0)}"
                                    if location_key not in seen_locations:
                                        results.append(current_match)
                                        seen_locations.add(location_key)
                                current_match = {}
                                current_file = None
                            elif ":" in line and "-" not in line.split(":", 1)[1][:3]:
                                parts = line.split(":", 2)
                                if len(parts) >= 3:
                                    current_file = parts[0]
                                    try:
                                        line_number = int(parts[1])
                                        content = parts[2]
                                        current_match = {
                                            "file_path": current_file,
                                            "line_number": line_number,
                                            "definition_line": content.strip(),
                                            "context": [],
                                        }
                                    except ValueError:
                                        continue
                            elif current_match and ":" in line:
                                parts = line.split(":", 2)
                                if len(parts) >= 3:
                                    try:
                                        ctx_line_num = int(parts[1])
                                        ctx_content = parts[2]
                                        current_match["context"].append(
                                            {
                                                "line_number": ctx_line_num,
                                                "content": ctx_content.rstrip(),
                                            }
                                        )
                                    except ValueError:
                                        continue

                        if current_match and current_file:
                            location_key = (
                                f"{current_file}:{current_match.get('line_number', 0)}"
                            )
                            if location_key not in seen_locations:
                                results.append(current_match)
                                seen_locations.add(location_key)

        if results:
            response = f"Found {len(results)} definition(s) for '{function_name}':\n\n"
            for i, match in enumerate(results, 1):
                response += (
                    f"Definition {i}: {match['file_path']}:{match['line_number']}\n"
                )
                for ctx in match.get("context", []):
                    if ctx["line_number"] == match["line_number"]:
                        response += (
                            f">>> {ctx['line_number']:4d}: {ctx['content']} <<<\n"
                        )
                    else:
                        response += f"    {ctx['line_number']:4d}: {ctx['content']}\n"
                response += "\n"

            ui_results = []
            for match in results:
                ui_results.append(
                    f"📍 {match['file_path']}:{match['line_number']}: {match['definition_line'][:80]}..."
                )
            console_ui.show_function_definitions(function_name, ui_results)
        else:
            response = f"No definitions found for function '{function_name}'"
            console_ui.show_function_definitions(function_name, [])

        return response

    except Exception as e:
        error_response = f"Error searching for function definition: {str(e)}"
        console_ui.show_tool_error("search_function_definition", str(e))
        return error_response


@tool
def analyze_import_usage(
    symbol_name: str, file_path: str, show_context: bool = True
) -> str:
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

        imports = []
        usages = []
        import re

        escaped_symbol = re.escape(symbol_name)

        # Language-specific import patterns
        import_patterns = []
        if is_python:
            import_patterns = [
                rf"from\s+.*\s+import\s+.*\b{escaped_symbol}\b",
                rf"import\s+.*\b{escaped_symbol}\b",
                rf"from\s+\b{escaped_symbol}\b",
                rf"import\s+\b{escaped_symbol}\b",
            ]
        elif is_javascript:
            import_patterns = [
                rf"import\s+.*\b{escaped_symbol}\b.*from",
                rf"import\s+\b{escaped_symbol}\b",
                rf'require\s*\(\s*[\'"`].*{escaped_symbol}',
                rf"const\s+.*\b{escaped_symbol}\b.*=.*require",
            ]

        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()
            is_import_line = False

            # Check for imports
            if import_patterns:
                for pattern in import_patterns:
                    if re.search(pattern, line_stripped, re.IGNORECASE):
                        imports.append(
                            {
                                "line_number": i,
                                "content": line_stripped,
                                "type": "import",
                            }
                        )
                        is_import_line = True
                        break
            else:
                has_import = "import" in line_stripped and symbol_name in line_stripped
                has_from = "from" in line_stripped and symbol_name in line_stripped
                has_require = (
                    "require" in line_stripped and symbol_name in line_stripped
                )
                if has_import or has_from or has_require:
                    imports.append(
                        {"line_number": i, "content": line_stripped, "type": "import"}
                    )
                    is_import_line = True

            # Check for usages (excluding import lines)
            if not is_import_line and symbol_name in line_stripped:
                if re.search(rf"\b{re.escape(symbol_name)}\b", line_stripped):
                    usage_type = "unknown"
                    if (
                        "(" in line_stripped
                        and symbol_name in line_stripped.split("(")[0]
                    ):
                        usage_type = "function_call"
                    elif (
                        "=" in line_stripped
                        and symbol_name in line_stripped.split("=")[0]
                    ):
                        usage_type = "assignment"
                    elif "." in line_stripped and f"{symbol_name}." in line_stripped:
                        usage_type = "attribute_access"
                    elif (
                        line_stripped.startswith("class ")
                        and symbol_name in line_stripped
                    ):
                        usage_type = "inheritance"
                    elif any(
                        keyword in line_stripped for keyword in ["def ", "function "]
                    ):
                        usage_type = "in_definition"
                    else:
                        usage_type = "reference"

                    usages.append(
                        {"line_number": i, "content": line_stripped, "type": usage_type}
                    )

        # Build analysis result
        result = f"Analysis of '{symbol_name}' in {file_path}:\n"
        result += f"{'=' * 60}\n\n"

        if imports:
            result += f"📥 IMPORTS ({len(imports)}):\n"
            for imp in imports:
                result += f"  Line {imp['line_number']:3d}: {imp['content']}\n"
            result += "\n"
        else:
            result += f"📥 No imports found for '{symbol_name}'\n\n"

        if usages:
            result += f"🔍 USAGES ({len(usages)}):\n"
            usage_by_type = {}
            for usage in usages:
                usage_type = usage.get("type", "unknown")
                if usage_type not in usage_by_type:
                    usage_by_type[usage_type] = []
                usage_by_type[usage_type].append(usage)

            for usage_type, type_usages in usage_by_type.items():
                result += f"  {usage_type.upper()} ({len(type_usages)}):\n"
                for usage in type_usages[:5]:  # Limit to 5 per type
                    result += (
                        f"    Line {usage['line_number']:3d}: {usage['content']}\n"
                    )
                if len(type_usages) > 5:
                    result += f"    ... and {len(type_usages) - 5} more\n"
                result += "\n"
        else:
            result += f"🔍 No usages found for '{symbol_name}'\n\n"

        # Summary
        result += "📊 SUMMARY:\n"
        result += f"  Total imports: {len(imports)}\n"
        result += f"  Total usages: {len(usages)}\n"

        # Issues
        issues = []
        if imports and not usages:
            issues.append("⚠️ Symbol imported but never used")
        elif usages and not imports:
            issues.append("⚠️ Symbol used but no imports found")
        elif len(imports) > 1:
            issues.append("⚠️ Symbol imported multiple times")

        if issues:
            result += "  Issues:\n"
            for issue in issues:
                result += f"    {issue}\n"
        else:
            result += "  ✅ No issues detected\n"

        import_lines = [
            f"Line {imp['line_number']}: {imp['content']}" for imp in imports
        ]
        usage_lines = [
            f"Line {usage['line_number']}: {usage['content']}" for usage in usages
        ]
        console_ui.show_import_analysis(
            symbol_name, file_path, import_lines, usage_lines
        )
        return result

    except Exception as e:
        error_response = f"Error analyzing imports in {file_path}: {str(e)}"
        console_ui.show_tool_error("analyze_import_usage", str(e))
        return error_response
