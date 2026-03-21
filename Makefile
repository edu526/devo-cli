.PHONY: help install clean test lint format build-binary build-windows venv docs

# Default target
help:
	@echo "Devo CLI - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make venv          - Create virtual environment"
	@echo "  make install       - Install package with all dependencies (dev + docs)"
	@echo ""
	@echo "Development:"
	@echo "  make test          - Run tests"
	@echo "  make lint          - Run linting (flake8)"
	@echo "  make format        - Format code (isort + black)"
	@echo "  make clean         - Clean build artifacts"
	@echo ""
	@echo "Build:"
	@echo "  make docs          - Serve documentation locally"
	@echo "  make build-binary  - Build standalone binary for current platform"
	@echo "  make build-windows - Build Windows binary (run on Windows only)"

# Serve documentation locally
docs:
	@echo "Starting documentation server..."
	zensical serve --open --config-file zensical.yml

# Create virtual environment
venv:
ifeq ($(OS),Windows_NT)
	@if [ -d "venv" ]; then \
		echo "Virtual environment already exists"; \
		echo ""; \
		echo "Activate it with:"; \
		echo "  PowerShell: .\venv\Scripts\Activate.ps1"; \
		echo "  CMD:        venv\Scripts\activate"; \
		echo "  Git Bash:   . venv/Scripts/activate"; \
		echo ""; \
		echo "Then run: make install"; \
	else \
		echo "Creating virtual environment..."; \
		python -m venv venv; \
		echo "Virtual environment created"; \
		echo ""; \
		echo "Activate it with:"; \
		echo "  PowerShell: .\venv\Scripts\Activate.ps1"; \
		echo "  CMD:        venv\Scripts\activate"; \
		echo "  Git Bash:   . venv/Scripts/activate"; \
		echo ""; \
		echo "Then run: make install"; \
	fi
else
	@if [ -d "venv" ]; then \
		echo "✓ Virtual environment already exists"; \
	else \
		echo "Creating virtual environment..."; \
		python3 -m venv venv || python -m venv venv; \
		echo "✓ Virtual environment created"; \
	fi
	@echo ""
	@echo "Activate it with:"
	@echo "  source venv/bin/activate"
	@echo ""
	@echo "Then run: make install"
endif

# Install package in editable mode with dev dependencies
install:
	@echo "Installing package with all dependencies (dev + docs)..."
	pip install -e ".[dev,docs]"
	@echo "✓ Package and all dependencies installed"

# Run tests
test:
	@echo "Running tests..."
	@if [ -f "venv/bin/pytest" ]; then \
		venv/bin/pytest tests/ -v; \
	elif [ -f "venv/Scripts/pytest.exe" ]; then \
		venv/Scripts/pytest.exe tests/ -v; \
	else \
		echo "Error: pytest not found in venv. Run 'make install' first."; \
		exit 1; \
	fi

# Run linting
lint:
	@echo "Running flake8..."
	@if [ -f "venv/bin/flake8" ]; then \
		venv/bin/flake8 cli_tool/ tests/; \
	elif [ -f "venv/Scripts/flake8.exe" ]; then \
		venv/Scripts/flake8.exe cli_tool/ tests/; \
	else \
		echo "Error: flake8 not found in venv. Run 'make install' first."; \
		exit 1; \
	fi

# Format code
format:
	@echo "Formatting code with isort and black..."
	@if [ -f "venv/bin/black" ]; then \
		venv/bin/isort cli_tool/ tests/ && \
		venv/bin/black cli_tool/ tests/; \
	elif [ -f "venv/Scripts/black.exe" ]; then \
		venv/Scripts/isort.exe cli_tool/ tests/ && \
		venv/Scripts/black.exe cli_tool/ tests/; \
	else \
		echo "Error: black/isort not found in venv. Run 'make install' first."; \
		exit 1; \
	fi

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf release/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf __pycache__/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "✓ Build artifacts cleaned"

# Build standalone binary for current platform
build-binary:
	@echo "Building standalone binary..."
	@if [ ! -f "venv/bin/activate" ]; then \
		echo "Error: Virtual environment not found. Run 'make venv' first."; \
		exit 1; \
	fi
	@bash scripts/build.sh
	@echo "✓ Binary built successfully"
	@echo ""
	@echo "Test with: ./dist/devo --version"

# Build Windows binary with PyInstaller (run on Windows only)
build-windows:
	@echo "Building Windows binary with PyInstaller..."
	@uname_out=$$(uname -s 2>/dev/null || echo unknown); \
	case "$$uname_out" in \
		MINGW*|MSYS*|CYGWIN*) \
			cmd /c scripts\\build-windows.bat && \
			powershell -ExecutionPolicy Bypass -File scripts\\package-windows.ps1; \
			;; \
		*) \
			echo "Error: This target is for Windows only (detected $$uname_out)"; \
			echo "On Windows, run:"; \
			echo "  1. scripts\\build-windows.bat"; \
			echo "  2. scripts\\package-windows.ps1"; \
			exit 1; \
			;; \
	esac
