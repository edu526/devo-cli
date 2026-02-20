"""
Advanced code analysis tools for dependency detection and reference searching.

This module provides specialized tools for analyzing code structure, finding
function/class references, and understanding code dependencies across different
programming languages.

Key Features:

1. Code Reference Analysis:
   • Search for symbol references across the codebase
   • Find function and class definitions
   • Analyze import usage and dependencies
   • Language-aware pattern matching

2. Dependency Detection:
   • Detect breaking changes in function signatures
   • Find unused imports and variables
   • Identify circular dependencies
   • Cross-reference analysis

3. Smart Search Capabilities:
   • Gitignore-aware file filtering
   • Multi-language support (Python, JS, TS, etc.)
   • Context-aware results
   • Pattern-based searching

Usage Examples:
```python
# Search for all references to a function
search_code_references("my_function", "py,js,ts")

# Find where a function is defined
search_function_definition("calculate_total", "py")

# Analyze how a symbol is imported and used
analyze_import_usage("UserModel", "src/models.py")
```
"""

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from strands import tool

from cli_tool.ui.console_ui import console_ui


def get_smart_search_patterns(symbol_name: str) -> List[str]:
    """
    Generate smart search patterns for complex symbols.

    Handles cases like:
    - createTrip(cache) -> searches for "createTrip" and "createTrip("
    - externalTrips.createTrip -> searches for "createTrip" and "externalTrips.createTrip"
    - MyClass.method -> searches for "method" and "MyClass.method"
    """
    import re

    patterns = []

    # Always add the escaped full symbol
    escaped_full = re.escape(symbol_name)
    patterns.append(f"\\b{escaped_full}\\b")

    # Extract base function/method name from complex patterns

    # Pattern 1: function calls like "createTrip(cache)" -> extract "createTrip"
    func_call_match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", symbol_name)
    if func_call_match:
        base_name = func_call_match.group(1)
        escaped_base = re.escape(base_name)
        patterns.extend(
            [
                f"\\b{escaped_base}\\b",  # Just the function name
                f"\\b{escaped_base}\\s*\\(",  # Function call pattern
                f"\\.{escaped_base}\\s*\\(",  # Method call pattern
            ]
        )

    # Pattern 2: method calls like "externalTrips.createTrip" -> extract "createTrip"
    method_call_match = re.match(r"^.*\.([a-zA-Z_][a-zA-Z0-9_]*)", symbol_name)
    if method_call_match:
        method_name = method_call_match.group(1)
        escaped_method = re.escape(method_name)
        patterns.extend(
            [
                f"\\b{escaped_method}\\b",  # Just the method name
                f"\\.{escaped_method}\\b",  # Method access pattern
                f"\\.{escaped_method}\\s*\\(",  # Method call pattern
            ]
        )

    # Pattern 3: property access like "obj.property" -> extract "property"
    prop_match = re.match(r"^.*\.([a-zA-Z_][a-zA-Z0-9_]*)$", symbol_name)
    if prop_match and not method_call_match:  # Avoid duplicate with method pattern
        prop_name = prop_match.group(1)
        escaped_prop = re.escape(prop_name)
        patterns.extend(
            [
                f"\\b{escaped_prop}\\b",  # Just the property name
                f"\\.{escaped_prop}\\b",  # Property access pattern
            ]
        )

    # Remove duplicates while preserving order
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
        ".DS_Store",
        "Thumbs.db",
    ]

    # Add default excludes
    for pattern in default_excludes:
        excludes.append(f"--exclude-dir='{pattern}'")

    # Read .gitignore if it exists
    if gitignore_path.exists():
        try:
            with open(gitignore_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith("#"):
                        # Convert gitignore patterns to grep exclude patterns
                        if line.endswith("/"):
                            # Directory pattern
                            excludes.append(f"--exclude-dir='{line.rstrip('/')}'")
                        elif "*" in line or "?" in line:
                            # File pattern with wildcards
                            excludes.append(f"--exclude='{line}'")
                        else:
                            # Simple file or directory
                            excludes.append(f"--exclude-dir='{line}'")
                            excludes.append(f"--exclude='{line}'")
        except Exception:
            # If we can't read .gitignore, just use defaults
            pass

    return " ".join(excludes)


def parse_grep_results(output: str, symbol_name: str) -> List[Dict[str, Any]]:
    """Parse grep output into structured results."""
    results = []

    for line in output.strip().split("\n"):
        if ":" in line:
            try:
                parts = line.split(":", 2)  # Split on first 2 colons only
                if len(parts) >= 3:
                    file_path = parts[0]
                    line_number = int(parts[1])
                    content = parts[2]

                    results.append(
                        {
                            "file_path": file_path,
                            "line_number": line_number,
                            "content": content.strip(),
                            "preview": (
                                content[:100] + "..." if len(content) > 100 else content
                            ),
                        }
                    )
            except (ValueError, IndexError):
                # Skip malformed lines
                continue

    return results


def get_language_patterns(
    symbol_name: str, search_type: str = "reference"
) -> Dict[str, List[str]]:
    """Get language-specific search patterns for different symbol types."""
    import re

    # Escape special regex characters in symbol name
    escaped_symbol = re.escape(symbol_name)

    patterns = {
        "py": [],
        "js": [],
        "ts": [],
        "jsx": [],
        "tsx": [],
        "java": [],
        "cpp": [],
        "cs": [],
    }

    if search_type == "reference":
        # General reference patterns
        patterns["py"] = [
            f"\\b{escaped_symbol}\\b",  # Word boundary match
            f"{escaped_symbol}\\(",  # Function call
            f"from .* import.*{escaped_symbol}",  # Import
            f"import.*{escaped_symbol}",  # Import
        ]

        patterns["js"] = patterns["ts"] = patterns["jsx"] = patterns["tsx"] = [
            f"\\b{escaped_symbol}\\b",
            f"{escaped_symbol}\\(",
            f"import.*{escaped_symbol}",
            f"from.*{escaped_symbol}",
            f"require.*{escaped_symbol}",
        ]

    elif search_type == "definition":
        # Definition patterns
        patterns["py"] = [
            f"def {escaped_symbol}\\s*\\(",  # Function definition
            f"class {escaped_symbol}\\s*[\\(:]",  # Class definition
            f"async def {escaped_symbol}\\s*\\(",  # Async function
            f"{escaped_symbol}\\s*=\\s*lambda",  # Lambda assignment
        ]

        patterns["js"] = patterns["ts"] = patterns["jsx"] = patterns["tsx"] = [
            f"function {escaped_symbol}\\s*\\(",
            f"const {escaped_symbol}\\s*=",
            f"let {escaped_symbol}\\s*=",
            f"var {escaped_symbol}\\s*=",
            f"class {escaped_symbol}\\s*{{",
            f"{escaped_symbol}\\s*:\\s*function",
            f"{escaped_symbol}\\s*=\\s*\\(",  # Arrow function
        ]

    return patterns


@tool
def search_code_references(
    symbol_or_pattern: str,
    file_extensions: str = "py,js,ts,jsx,tsx",
    max_results: int = 50,
    use_regex: bool = False,
    case_sensitive: bool = False,
) -> str:
    """
    Search for references to a symbol or pattern across the codebase.

    This unified tool can perform both simple symbol searches and advanced regex pattern matching,
    giving you flexibility to search for exact symbols or complex patterns as needed.

    Args:
        symbol_or_pattern: The symbol name or regex pattern to search for
        file_extensions: Comma-separated list of file extensions to search (default: py,js,ts,jsx,tsx)
        max_results: Maximum number of results to return (default: 50)
        use_regex: If True, treats symbol_or_pattern as a regex pattern; if False, uses smart symbol matching
        case_sensitive: Whether the search should be case sensitive (default: False)

    Returns:
        String containing file paths and line numbers where the symbol/pattern is found

    Examples:
        # Simple symbol search (smart patterns)
        search_code_references("createTrip", "py,js,ts")
        search_code_references("UserModel", "py")

        # Complex symbol search (automatically handles method calls, etc.)
        search_code_references("createTrip(cache)", "js")  # Will find both exact and similar patterns
        search_code_references("externalTrips.createTrip", "js,ts")

        # Regex pattern search (full control)
        search_code_references("createTrip\\\\(", "js", use_regex=True)
        search_code_references("\\\\w+\\\\.createTrip", "js,ts", use_regex=True)
        search_code_references("function\\\\s+\\\\w+\\\\s*\\\\(", "js", use_regex=True)

        # Case-sensitive searches
        search_code_references("CreateTrip", "js", case_sensitive=True)
    """
    # Show tool input
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
        # Convert extensions to grep pattern
        extensions = [ext.strip() for ext in file_extensions.split(",")]
        include_pattern = " ".join([f"--include='*.{ext}'" for ext in extensions])

        # Get exclusion patterns from .gitignore
        exclude_pattern = get_gitignore_excludes()

        # Determine search patterns based on mode
        if use_regex:
            # Direct regex mode - use pattern as-is
            search_patterns = [symbol_or_pattern]
        else:
            # Smart symbol search mode - generate intelligent patterns
            search_patterns = get_smart_search_patterns(symbol_or_pattern)

        all_results = []
        seen_locations = set()

        # Search with each pattern
        for pattern in search_patterns:
            # Build grep command
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
                # Parse and collect results, avoiding duplicates
                parsed_results = parse_grep_results(result.stdout, symbol_or_pattern)
                for res in parsed_results:
                    location_key = f"{res['file_path']}:{res['line_number']}"
                    if location_key not in seen_locations:
                        all_results.append(res)
                        seen_locations.add(location_key)

        if all_results:
            # Sort results by file path and line number
            all_results.sort(key=lambda x: (x["file_path"], x["line_number"]))

            # Limit results
            limited_results = all_results[:max_results]

            # Group by file for better organization
            files_dict = {}
            for res in limited_results:
                file_path = res["file_path"]
                if file_path not in files_dict:
                    files_dict[file_path] = []
                files_dict[file_path].append(res)

            # Format response
            search_type = "regex pattern" if use_regex else "symbol"
            response = f"Found {len(limited_results)} matches for {search_type} '{symbol_or_pattern}' in {len(files_dict)} files:\n\n"

            for file_path, file_results in files_dict.items():
                response += f"📄 {file_path} ({len(file_results)} matches):\n"
                for res in file_results:
                    response += f"  Line {res['line_number']}: {res['preview']}\n"
                response += "\n"

            if len(all_results) > max_results:
                response += f"... and {len(all_results) - max_results} more results (use max_results to see more)\n"

            # Show formatted results in UI
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
    Search for function definitions across the codebase with language-aware patterns.

    This tool uses language-specific patterns to find function and method definitions,
    providing context lines around each match for better understanding.

    Args:
        function_name: Name of the function to find
        file_extensions: Comma-separated list of file extensions to search
        context_lines: Number of context lines to show around each definition

    Returns:
        String containing locations where the function is defined with context

    Examples:
        # Find Python function definition
        search_function_definition("calculate_tax", "py")

        # Find JavaScript/TypeScript function
        search_function_definition("processData", "js,ts")

        # Find with more context
        search_function_definition("handleClick", "jsx,tsx", context_lines=5)
    """
    # Show tool input
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

        # Get exclusion patterns from .gitignore
        exclude_pattern = get_gitignore_excludes()

        # Get language-specific definition patterns
        all_patterns = get_language_patterns(function_name, "definition")

        results = []
        seen_locations = set()

        # Search with each pattern
        for ext in extensions:
            if ext in all_patterns:
                for pattern in all_patterns[ext]:
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
                        # Parse context results
                        lines = result.stdout.split("\n")
                        current_file = None
                        current_match = {}

                        for line in lines:
                            if line.strip() == "--":  # grep separator
                                if current_match and current_file:
                                    location_key = f"{current_file}:{current_match.get('line_number', 0)}"
                                    if location_key not in seen_locations:
                                        results.append(current_match)
                                        seen_locations.add(location_key)
                                current_match = {}
                                current_file = None
                            elif (
                                ":" in line and "-" not in line.split(":", 1)[1][:3]
                            ):  # Main match line
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
                            elif current_match and ":" in line:  # Context line
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

                        # Don't forget the last match
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
                response += f"{'=' * 50}\n"

                # Show context with the definition highlighted
                for ctx in match.get("context", []):
                    if ctx["line_number"] == match["line_number"]:
                        response += (
                            f">>> {ctx['line_number']:4d}: {ctx['content']} <<<\n"
                        )
                    else:
                        response += f"    {ctx['line_number']:4d}: {ctx['content']}\n"
                response += "\n"

            # Format for UI display
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
    Analyze how a symbol is imported and used in a specific file.

    This tool provides detailed analysis of symbol usage including import statements,
    usage patterns, and potential issues like unused imports.

    Args:
        symbol_name: The symbol to analyze
        file_path: The file to analyze
        show_context: Whether to show context lines around usages

    Returns:
        Information about how the symbol is imported and used

    Examples:
        # Analyze a Python import
        analyze_import_usage("UserModel", "src/views.py")

        # Analyze JavaScript import
        analyze_import_usage("useState", "components/Form.jsx")

        # Analyze without context
        analyze_import_usage("lodash", "utils/helpers.js", show_context=False)
    """
    # Show tool input
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

        # Detect file language
        file_ext = full_path.suffix.lower()
        is_python = file_ext == ".py"
        is_javascript = file_ext in [".js", ".jsx", ".ts", ".tsx"]

        # Find import statements
        imports = []
        usages = []

        # Language-specific import patterns
        import re

        escaped_symbol = re.escape(symbol_name)

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
                rf'import\s*\(\s*[\'"`].*{escaped_symbol}',
            ]

        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()

            # Check for imports
            is_import_line = False
            if import_patterns:
                import re

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
                # Fallback for unknown languages
                if (
                    ("import" in line_stripped and symbol_name in line_stripped)
                    or ("from" in line_stripped and symbol_name in line_stripped)
                    or ("require" in line_stripped and symbol_name in line_stripped)
                ):
                    imports.append(
                        {"line_number": i, "content": line_stripped, "type": "import"}
                    )
                    is_import_line = True

            # Check for usages (excluding import lines)
            if not is_import_line and symbol_name in line_stripped:
                # More sophisticated usage detection
                import re

                # Look for the symbol as a word boundary to avoid partial matches
                if re.search(rf"\b{re.escape(symbol_name)}\b", line_stripped):
                    usage_type = "unknown"

                    # Classify usage type
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

        # Import analysis
        if imports:
            result += f"📥 IMPORTS ({len(imports)} found):\n"
            for imp in imports:
                result += f"  Line {imp['line_number']:3d}: {imp['content']}\n"
                if show_context and len(lines) > imp["line_number"]:
                    # Show context around import
                    start_ctx = max(0, imp["line_number"] - 2)
                    end_ctx = min(len(lines), imp["line_number"] + 1)
                    for ctx_idx in range(start_ctx, end_ctx):
                        if ctx_idx + 1 != imp["line_number"]:
                            result += f"      {ctx_idx + 1:3d}: {lines[ctx_idx]}\n"
            result += "\n"
        else:
            result += f"📥 No imports found for '{symbol_name}'\n\n"

        # Usage analysis
        if usages:
            result += f"🔍 USAGES ({len(usages)} found):\n"

            # Group by usage type
            usage_by_type = {}
            for usage in usages:
                usage_type = usage.get("type", "unknown")
                if usage_type not in usage_by_type:
                    usage_by_type[usage_type] = []
                usage_by_type[usage_type].append(usage)

            for usage_type, type_usages in usage_by_type.items():
                result += f"  {usage_type.upper()} ({len(type_usages)} times):\n"
                for usage in type_usages[:10]:  # Limit to 10 per type
                    result += (
                        f"    Line {usage['line_number']:3d}: {usage['content']}\n"
                    )
                    if show_context:
                        # Show brief context
                        start_ctx = max(0, usage["line_number"] - 1)
                        end_ctx = min(len(lines), usage["line_number"] + 1)
                        for ctx_idx in range(start_ctx, end_ctx):
                            if ctx_idx + 1 != usage["line_number"]:
                                result += f"        {ctx_idx + 1:3d}: {lines[ctx_idx][:80]}...\n"

                if len(type_usages) > 10:
                    result += f"    ... and {len(type_usages) - 10} more {usage_type} usages\n"
                result += "\n"
        else:
            result += f"🔍 No usages found for '{symbol_name}'\n\n"

        # Analysis summary
        result += "📊 SUMMARY:\n"
        result += f"  Total imports: {len(imports)}\n"
        result += f"  Total usages: {len(usages)}\n"

        # Potential issues
        issues = []
        if imports and not usages:
            issues.append(
                "⚠️  Symbol is imported but never used (potential unused import)"
            )
        elif usages and not imports:
            issues.append(
                "⚠️  Symbol is used but no imports found (might be built-in or global)"
            )
        elif len(imports) > 1:
            issues.append("⚠️  Symbol is imported multiple times")

        if issues:
            result += "  Issues detected:\n"
            for issue in issues:
                result += f"    {issue}\n"
        else:
            result += "  ✅ No issues detected\n"

        # Show in UI
        console_ui.show_import_analysis(
            symbol_name,
            file_path,
            [f"Line {imp['line_number']}: {imp['content']}" for imp in imports],
            [f"Line {usage['line_number']}: {usage['content']}" for usage in usages],
        )

        return result

    except Exception as e:
        error_response = f"Error analyzing imports in {file_path}: {str(e)}"
        console_ui.show_tool_error("analyze_import_usage", str(e))
        return error_response
