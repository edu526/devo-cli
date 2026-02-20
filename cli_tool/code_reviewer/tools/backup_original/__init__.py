"""
Advanced Tools Module for Code Analysis and File Operations.

This module provides a comprehensive suite of tools for analyzing code,
reading files with multiple specialized modes, and detecting dependencies
and breaking changes across different programming languages.

Key Components:

1. File Reader (file_reader.py):
   • Advanced file reading with 8+ specialized modes
   • Multi-file support with wildcard patterns
   • Syntax highlighting and rich UI integration
   • Git-aware file filtering

2. Code Analyzer (code_analyzer.py):
   • Symbol reference searching across codebases
   • Function/class definition discovery
   • Import usage analysis
   • Breaking change detection

3. Enhanced Features:
   • .gitignore pattern integration
   • Multi-language support (Python, JS, TS, etc.)
   • Context-aware search results
   • Rich UI components with streaming display

Usage Examples:
```python
from .file_reader import get_file_content, get_file_info
from .code_analyzer import search_code_references, search_function_definition

# Read files with different modes
get_file_content("src/*.py", mode="find")  # Find all Python files
get_file_content("main.py", mode="view")   # View with syntax highlighting
get_file_content("large.py", mode="lines", start_line=100, lines_count=50)

# Analyze code dependencies
search_code_references("MyClass", "py,js,ts")
search_function_definition("calculate_total", "py")
```

Tool Compatibility:
- Combines best features from Strands file_read tool
- Maintains backward compatibility with existing tools
- Enhanced with custom UI components and streaming display
- Git-aware with automatic .gitignore pattern exclusion
"""

from cli_tool.code_reviewer.tools.code_analyzer import (
    analyze_import_usage,
    search_code_references,
    search_function_definition,
)

# Import all tools for easy access
from cli_tool.code_reviewer.tools.file_reader import get_file_content, get_file_info

__all__ = [
    # File operations
    "get_file_content",
    "get_file_info",
    # Code analysis
    "search_code_references",
    "search_function_definition",
    "analyze_import_usage",
]
