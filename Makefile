.PHONY: help install install-dev uninstall clean test lint format build publish refresh venv completion binary binary-all build-windows run

# Default target
help:
	@echo "Devo CLI - Development Commands"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make venv          - Create virtual environment"
	@echo "  make install       - Install package in editable mode"
	@echo "  make install-dev   - Install with development dependencies"
	@echo "  make uninstall     - Uninstall the package"
	@echo "  make refresh       - Refresh shell cache (use after install)"
	@echo "  make completion    - Setup shell autocompletion"
	@echo ""
	@echo "Development:"
	@echo "  make test          - Run tests"
	@echo "  make lint          - Run linting (flake8)"
	@echo "  make format        - Format code (isort)"
	@echo "  make clean         - Clean build artifacts"
	@echo ""
	@echo "Build & Release:"
	@echo "  make build         - Build distribution packages"
	@echo "  make binary        - Build standalone binary for current platform"
	@echo "  make binary-all    - Build binary with platform-specific naming"
	@echo "  make build-windows - Build Windows binary and create ZIP package"
	@echo "  make release       - Create git tag and trigger CI/CD"
	@echo ""
	@echo "Usage:"
	@echo "  make install       - First time setup"
	@echo "  make completion    - Enable tab completion"
	@echo "  make refresh       - After code changes"

# Create virtual environment
venv:
	@echo "Creating virtual environment..."
	python3 -m venv venv || python -m venv venv
	@echo "✓ Virtual environment created"
	@echo ""
	@echo "Activate it with:"
ifeq ($(OS),Windows_NT)
	@echo "  PowerShell: .\venv\Scripts\Activate.ps1"
	@echo "  CMD:        venv\Scripts\activate.bat"
else
	@echo "  source venv/bin/activate"
endif
	@echo ""
	@echo "Then run: make install-dev"

# Install package in editable mode
install:
	@echo "Installing package in editable mode..."
	python3 -m pip install -e . || python -m pip install -e .
	@echo "✓ Package installed"
	@echo ""
	@echo "Run 'make refresh' to update shell cache"

# Install with development dependencies
install-dev:
	@echo "Installing package with development dependencies..."
	python3 -m pip install -e . || python -m pip install -e .
	python3 -m pip install -r requirements.txt || python -m pip install -r requirements.txt
	@echo "✓ Package and dev dependencies installed"
	@echo ""
	@echo "Run 'make refresh' to update shell cache"

# Uninstall package
uninstall:
	@echo "Uninstalling package..."
	python -m pip uninstall devo-cli -y
	@echo "✓ Package uninstalled"

# Refresh shell command cache
refresh:
	@echo "Refreshing shell cache..."
	@hash -r 2>/dev/null || rehash 2>/dev/null || true
	@echo "✓ Shell cache refreshed"
	@echo ""
	@echo "Test with: devo --help"

# Run tests
test:
	@echo "Running tests..."
	pytest tests/ -v

# Run linting
lint:
	@echo "Running flake8..."
	flake8 cli_tool/ tests/

# Format code
format:
	@echo "Formatting imports with isort..."
	isort cli_tool/ tests/

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

# Build distribution packages
build: clean
	@echo "Building distribution packages..."
	python -m build
	@echo "✓ Build complete"
	@echo ""
	@echo "Packages created in dist/"

# Build standalone binary
binary:
	@echo "Building standalone binary..."
	@chmod +x build-binaries.sh
	./build-binaries.sh
	@echo "✓ Binary build complete"

# Build binary with platform-specific naming
binary-all:
	@echo "Building platform-specific binary..."
	@chmod +x build-all-platforms.sh
	./build-all-platforms.sh
	@echo "✓ Platform-specific binary build complete"

# Build Windows binary with PyInstaller (onedir mode)
# Build Windows binary with PyInstaller (onedir mode)
build-windows:
	@echo "Building Windows binary with PyInstaller..."
	@echo "Note: Run this on Windows or use scripts/build-windows.bat"
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
			echo "Or use: make build-binary for cross-platform build"; \
			exit 1; \
			;; \
	esac
release:
	@echo "Creating release..."
	@echo ""
	@read -p "Enter version (e.g., v1.2.3): " version; \
	if [ -z "$$version" ]; then \
		echo "Error: Version is required"; \
		exit 1; \
	fi; \
	echo "Creating tag $$version..."; \
	git tag $$version; \
	git push origin $$version; \
	echo "✓ Tag $$version created and pushed"; \
	echo ""; \
	echo "CI/CD pipeline will build and publish automatically"

# Quick development workflow
dev: install refresh
	@echo "✓ Development environment ready"
	@echo ""
	@echo "Try: devo --help"

# Setup shell completion
completion:
	@echo "Setting up shell completion..."
	@echo ""
	@SHELL_NAME=$$(basename $$SHELL); \
	if [ "$$SHELL_NAME" = "zsh" ]; then \
		if ! grep -q "_DEVO_COMPLETE=zsh_source devo" ~/.zshrc 2>/dev/null; then \
			echo 'eval "$$(_DEVO_COMPLETE=zsh_source devo)"' >> ~/.zshrc; \
			echo "✓ Added completion to ~/.zshrc"; \
		else \
			echo "✓ Completion already configured in ~/.zshrc"; \
		fi; \
		echo ""; \
		echo "Run this to enable completion in current session:"; \
		echo '  eval "$$(_DEVO_COMPLETE=zsh_source devo)"'; \
		echo ""; \
		echo "Or restart your terminal"; \
	elif [ "$$SHELL_NAME" = "bash" ]; then \
		if ! grep -q "_DEVO_COMPLETE=bash_source devo" ~/.bashrc 2>/dev/null; then \
			echo 'eval "$$(_DEVO_COMPLETE=bash_source devo)"' >> ~/.bashrc; \
			echo "✓ Added completion to ~/.bashrc"; \
		else \
			echo "✓ Completion already configured in ~/.bashrc"; \
		fi; \
		echo ""; \
		echo "Run this to enable completion in current session:"; \
		echo '  eval "$$(_DEVO_COMPLETE=bash_source devo)"'; \
		echo ""; \
		echo "Or restart your terminal"; \
	else \
		echo "⚠️  Shell $$SHELL_NAME not supported"; \
		echo "Supported shells: bash, zsh"; \
		echo ""; \
		echo "Run 'devo completion' for manual instructions"; \
	fi

# Build standalone binary
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

# Build binary with platform-specific naming
build-all: build-binary
	@echo "Creating platform-specific release..."
	@bash scripts/build.sh --release
	@echo "✓ Release ready"

