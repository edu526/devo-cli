# Development Setup

## Requirements

- Python 3.12+
- Git

## Setup

```bash
# Clone the repository
git clone <repository-url>
cd devo-cli

# Create virtual environment
make venv
```

Then activate it:

=== "Linux / macOS"

    ```bash
    source venv/bin/activate
    ```

=== "Windows (CMD / PowerShell)"

    ```powershell
    venv\Scripts\activate
    ```

=== "Windows (Git Bash)"

    ```bash
    . venv/Scripts/activate
    ```

Then install all dependencies:

```bash
make install
```

## Next Steps

- [Contributing Guide](contributing.md) — daily workflow, making changes, running tests
- [Building Binaries](building.md) — build standalone binaries with PyInstaller
- [Semantic Release](../cicd/semantic-release.md) — how versioning and releases work
