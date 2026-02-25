# Documentation Structure

This document describes the organization of Devo CLI documentation.

## Directory Structure

```
docs/
├── index.md                          # Homepage
├── getting-started/                  # Getting started guides
│   ├── quickstart.md                # 5-minute quick start
│   ├── installation.md              # Detailed installation
│   └── configuration.md             # Configuration guide
├── commands/                         # Command reference
│   ├── index.md                     # Commands overview
│   ├── commit.md                    # devo commit
│   ├── code-reviewer.md             # devo code-reviewer
│   ├── codeartifact.md              # devo codeartifact-login
│   ├── upgrade.md                   # devo upgrade
│   └── config.md                    # devo config
├── guides/                           # How-to guides
│   ├── aws-setup.md                 # AWS configuration
│   └── shell-completion.md          # Shell completion setup
├── development/                      # Development docs
│   ├── setup.md                     # Development setup
│   ├── contributing.md              # Contributing guide
│   └── building.md                  # Building binaries
├── cicd/                             # CI/CD documentation
│   ├── overview.md                  # CI/CD overview
│   ├── github-actions.md            # GitHub Actions workflows
│   └── semantic-release.md          # Semantic release process
└── reference/                        # Reference documentation
    ├── configuration.md             # Configuration reference
    ├── environment.md               # Environment variables
    └── troubleshooting.md           # Troubleshooting guide
```

## Documentation Categories

### Getting Started
Entry point for new users. Covers installation, basic configuration, and quick start.

**Target Audience:** New users, first-time installers

**Files:**
- `getting-started/quickstart.md` - 5-minute quick start
- `getting-started/installation.md` - Detailed installation instructions
- `getting-started/configuration.md` - Configuration basics

### Commands
Complete reference for all CLI commands with usage examples.

**Target Audience:** All users looking for command documentation

**Files:**
- `commands/index.md` - Commands overview
- `commands/commit.md` - Commit message generation
- `commands/code-reviewer.md` - Code review
- `commands/codeartifact.md` - CodeArtifact authentication
- `commands/upgrade.md` - Self-update
- `commands/config.md` - Configuration management

### Guides
Step-by-step guides for specific tasks and configurations.

**Target Audience:** Users setting up specific features

**Files:**
- `guides/aws-setup.md` - AWS credentials and Bedrock setup
- `guides/shell-completion.md` - Shell completion configuration

### Development
Documentation for contributors and developers.

**Target Audience:** Contributors, maintainers

**Files:**
- `development/setup.md` - Development environment setup
- `development/contributing.md` - Contributing guidelines
- `development/building.md` - Building binaries

### CI/CD
Documentation for continuous integration and deployment.

**Target Audience:** Maintainers, DevOps engineers

**Files:**
- `cicd/overview.md` - CI/CD pipeline overview
- `cicd/github-actions.md` - GitHub Actions workflows
- `cicd/semantic-release.md` - Automated versioning

### Reference
Technical reference documentation.

**Target Audience:** Advanced users, developers

**Files:**
- `reference/configuration.md` - Complete configuration reference
- `reference/environment.md` - Environment variables reference
- `reference/troubleshooting.md` - Troubleshooting guide

## Documentation Principles

### 1. Progressive Disclosure
- Start simple (Quick Start)
- Provide detailed information as needed
- Link to related documentation

### 2. Task-Oriented
- Focus on what users want to accomplish
- Provide clear steps and examples
- Include troubleshooting

### 3. Consistent Structure
- Each command page follows same format
- Guides use step-by-step approach
- Reference docs are comprehensive

### 4. Searchable
- Clear headings and structure
- Keywords in titles
- Cross-references between docs

## Writing Guidelines

### Command Documentation

Each command page should include:
1. Overview - What the command does
2. Usage - Basic syntax
3. Options - All available options
4. Examples - Common use cases
5. See Also - Related documentation

### Guide Documentation

Each guide should include:
1. Prerequisites - What's needed
2. Steps - Clear, numbered steps
3. Verification - How to test
4. Troubleshooting - Common issues
5. Next Steps - Where to go next

### Reference Documentation

Reference docs should include:
1. Complete list of options
2. Default values
3. Valid values/formats
4. Examples
5. Related references

## Maintenance

### Adding New Documentation

1. Determine category (getting-started, commands, guides, etc.)
2. Create file in appropriate directory
3. Follow existing structure and style
4. Add to `mkdocs.yml` navigation
5. Cross-reference from related docs

### Updating Documentation

1. Keep examples up-to-date
2. Update version-specific information
3. Add troubleshooting for common issues
4. Maintain consistent formatting

### Removing Documentation

1. Check for cross-references
2. Update navigation in `mkdocs.yml`
3. Redirect or update links
4. Archive if needed for history

## Building Documentation

### Local Preview

```bash
# Install dependencies
pip install mkdocs mkdocs-click

# Start development server
mkdocs serve

# View at http://127.0.0.1:8000
```

### Build Static Site

```bash
# Build documentation
mkdocs build

# Output in site/ directory
```

### Deploy to GitHub Pages

```bash
# Manual deployment
mkdocs gh-deploy

# Or push to main branch
# GitHub Actions will deploy automatically
```

## GitHub Pages Deployment

Documentation is automatically deployed to GitHub Pages when:
- Changes are pushed to `main` branch
- Changes affect `docs/**` or `mkdocs.yml`
- Workflow is manually triggered

**URL:** https://edu526.github.io/devo-cli

## See Also

- [MkDocs Documentation](https://www.mkdocs.org/)
- [mkdocs-click Plugin](https://github.com/mkdocs/mkdocs-click)
- [GitHub Pages](https://pages.github.com/)
