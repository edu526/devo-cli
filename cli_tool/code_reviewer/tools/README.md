# Advanced Tools Module Documentation

## Overview

This enhanced tools module combines the best features from the **Strands file_read tool** with our custom UI components and code analysis capabilities. It provides a comprehensive suite of tools for file operations and code analysis with rich visual feedback.

## 🚀 New Features Added

### Enhanced File Reader (`file_reader.py`)

#### **8 Specialized Reading Modes:**

1. **`view`** - Display full file contents with syntax highlighting
2. **`find`** - List matching files with directory tree visualization
3. **`lines`** - Show specific line ranges with context
4. **`chunk`** - Read byte chunks from specific offsets
5. **`search`** - Pattern searching with context highlighting
6. **`stats`** - File statistics and metrics
7. **`preview`** - Quick content preview (first 20 lines)
8. **`diff`** - Compare two files

#### **Advanced Capabilities:**
- ✅ **Multi-file support** with comma-separated paths: `"file1.py,file2.js,data/*.json"`
- ✅ **Wildcard patterns**: `"*.py"`, `"src/**/*.js"`, `"tests/**/test_*.py"`
- ✅ **Recursive directory traversal** with configurable depth
- ✅ **Smart file filtering** respecting `.gitignore` patterns
- ✅ **Language detection** for syntax highlighting
- ✅ **Rich UI integration** with streaming display

### Enhanced Code Analyzer (`code_analyzer.py`)

#### **New Analysis Tools:**

1. **`search_code_references`** - Find symbol references across codebase
2. **`search_function_definition`** - Language-aware function discovery
3. **`analyze_import_usage`** - Import and usage analysis

#### **Smart Features:**
- ✅ **Language-specific patterns** for Python, JS, TS, JSX, TSX
- ✅ **Context-aware results** with surrounding code lines
- ✅ **Usage classification** (function calls, assignments, etc.)
- ✅ **Risk assessment** for breaking changes
- ✅ **Migration recommendations** for symbol renames

## 📊 Comparison: Before vs After

### **Your Original Implementation:**
```python
# Limited functionality
get_file_content("file.py", start_line=10, end_line=20)
get_file_info("file.py")
search_code_references("symbol", "py")
```

### **Enhanced Implementation:**
```python
# Multi-mode file operations
get_file_content("*.py", mode="find")                    # Find all Python files
get_file_content("large.py", mode="lines", start_line=100, lines_count=50)
get_file_content("config.py", mode="search", search_pattern="API_KEY")
get_file_content("old.py", mode="diff", comparison_path="new.py")

# Advanced code analysis
search_code_references("UserModel", "py,js,ts", max_results=50)
search_function_definition("calculate_tax", "py", context_lines=5)
analyze_import_usage("UserModel", "src/views.py", show_context=True)
```

## 🎯 Usage Examples

### File Operations

```python
from src.tools import get_file_content, get_file_info

# 1. Find all Python files in project
files = get_file_content("**/*.py", mode="find", recursive=True)

# 2. Read large file in chunks
content = get_file_content(
    "large_file.py",
    mode="lines",
    start_line=100,
    lines_count=50,
    show_line_numbers=True
)

# 3. Search for patterns in files
results = get_file_content(
    "src/**/*.py",
    mode="search",
    search_pattern="def.*async",
    context_lines=3
)

# 4. Compare two versions
diff = get_file_content(
    "old_version.py",
    mode="diff",
    comparison_path="new_version.py"
)

# 5. Get comprehensive file stats
stats = get_file_content("main.py", mode="stats")

# 6. Quick preview of multiple files
previews = get_file_content("src/*.py,tests/*.py", mode="preview")
```

### Code Analysis

```python
from src.tools import (
    search_code_references,
    search_function_definition,
    analyze_import_usage
)

# 1. Find all references to a class
refs = search_code_references("UserModel", "py,js,ts", max_results=100)

# 2. Find function definitions with context
defs = search_function_definition("process_data", "py,js", context_lines=5)

# 3. Analyze import usage in specific file
usage = analyze_import_usage("requests", "src/api.py", show_context=True)
```

## 🎨 Rich UI Features

### Visual Enhancements

1. **Syntax Highlighting**: Automatic language detection and highlighting
2. **Structured Panels**: Rich panels with borders and formatting
3. **Progress Indicators**: Real-time progress for long operations
4. **Tree Visualization**: Directory structure display for file searches
5. **Context Display**: Code context with line numbers and highlighting
6. **Error Handling**: Clear error messages with suggested fixes

### Streaming Display

- **Real-time Updates**: Live display of search results as they're found
- **Event Grouping**: Intelligent grouping of related events
- **Progress Tracking**: Visual progress for multi-file operations
- **Cancellation Support**: Ability to cancel long-running operations

## 🔧 Configuration Options

### Environment Variables

```bash
# File operations
FILE_READ_RECURSIVE_DEFAULT=true
FILE_READ_MAX_FILES_DEFAULT=100
FILE_READ_CONTEXT_LINES_DEFAULT=3

# Search operations
SEARCH_MAX_RESULTS_DEFAULT=50
SEARCH_CONTEXT_LINES_DEFAULT=2

# UI behavior
SHOW_PROGRESS_DEFAULT=true
STREAM_RESULTS_DEFAULT=true
```

### Gitignore Integration

The tools automatically respect `.gitignore` patterns plus additional defaults:
- `.git`, `.venv`, `__pycache__`, `node_modules`
- `*.pyc`, `*.log`, `*.tmp`, `.DS_Store`
- `.idea`, `.vscode`, `build`, `dist`

## 🚀 Performance Optimizations

1. **Lazy Loading**: Files are processed on-demand
2. **Result Limiting**: Configurable limits to prevent memory issues
3. **Pattern Optimization**: Efficient glob and regex patterns
4. **Caching**: Smart caching of file metadata
5. **Streaming**: Results are streamed for immediate feedback

## 🔄 Migration Guide

### From Original Tools

```python
# OLD WAY
get_file_content("file.py", start_line=10, end_line=20)

# NEW WAY - Same functionality
get_file_content("file.py", mode="lines", start_line=10, end_line=20)

# NEW WAY - Enhanced functionality
get_file_content("file.py", mode="lines", start_line=10, lines_count=10, show_line_numbers=True)
```

### Backward Compatibility

All original function signatures are preserved. New parameters are optional with sensible defaults.

## 🎯 Best Practices

### 1. **Efficient File Reading**

```python
# For large files, use targeted reading
get_file_info("large_file.py")  # Get overview first
get_file_content("large_file.py", mode="lines", start_line=100, lines_count=50)

# For multiple files, use patterns
get_file_content("src/**/*.py", mode="find")  # Find first
get_file_content("specific_files.py", mode="view")  # Then read
```

### 2. **Smart Code Analysis**

```python
# Start broad, then narrow down
search_code_references("symbol", "py,js,ts")  # Find all references
search_function_definition("symbol", "py")     # Find definitions
analyze_import_usage("symbol", "specific.py") # Analyze specific usage
```

### 3. **Performance Considerations**

```python
# Limit results for large codebases
search_code_references("common_word", "py", max_results=25)

# Use specific file extensions
search_function_definition("func", "py")  # Not "py,js,ts,jsx,tsx"

# Use targeted patterns
get_file_content("src/models/*.py", mode="find")  # Not "**/*.py"
```

## 🔧 Troubleshooting

### Common Issues

1. **Too Many Results**: Use `max_results` parameter to limit output
2. **Slow Searches**: Specify file extensions to narrow scope
3. **Missing Files**: Check `.gitignore` patterns and file permissions
4. **Pattern Issues**: Use absolute paths or verify glob patterns

### Debug Mode

Set environment variable for detailed logging:
```bash
export TOOLS_DEBUG=true
```

## 🚀 Future Enhancements

### Planned Features

1. **Smart Caching**: Persistent caching for faster repeated operations
2. **Language Servers**: Integration with LSP for better code understanding
3. **Git Integration**: Time machine mode with git history
4. **Fuzzy Search**: Intelligent matching for symbol names
5. **Batch Operations**: Process multiple operations in parallel

### Contributing

The tools are designed to be easily extensible. Add new modes to `file_reader.py` or new analysis functions to `code_analyzer.py`.

---

## Summary

This enhanced tools module provides:

✅ **8 specialized file reading modes** vs original 2 functions
✅ **Multi-file support** with wildcards and patterns
✅ **Advanced code analysis** with breaking change detection
✅ **Rich UI integration** with streaming display
✅ **Language-aware processing** for multiple programming languages
✅ **Git-aware filtering** respecting .gitignore patterns
✅ **Performance optimizations** for large codebases
✅ **Backward compatibility** with existing code

The result is a powerful, flexible, and user-friendly tool suite that significantly enhances the code review and analysis capabilities of your system.
