"""
Optimized tools guide - removed verbose examples and duplications.
"""

TOOLS_GUIDE = """
**Available Tools:**
- `get_file_info(file_path)` - Get file structure and metadata
- `get_file_content(path, mode, ...)` - Advanced file reading:
  • `mode="view"` - Full file with syntax highlighting
  • `mode="find"` - List matching files (supports `*.py`, `src/**/*.js`)
  • `mode="lines"` - Specific line ranges with context
  • `mode="search"` - Pattern search with smart/regex modes
- `search_code_references(symbol, extensions, use_regex)` - Find symbol references across codebase
- `search_function_definition(function_name, extensions)` - Find function definitions
- `analyze_import_usage(symbol_name, file_path)` - Analyze symbol imports and usage
"""

SEARCH_MODES_GUIDE = """
**Search Modes:**
- **Smart mode** (use_regex=False): Auto-generates patterns for "createTrip", "obj.method()"
- **Regex mode** (use_regex=True): Direct patterns like "createTrip\\\\(", "\\\\w+\\.method"

**Strategy:**
1. Analyze diff to understand changes
2. Use `get_file_info()` for large files structure
3. Read relevant sections with `get_file_content(mode="lines")`
4. Use search tools to understand impact on other code
5. Request additional context intelligently as needed
"""
