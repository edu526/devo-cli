#!/bin/bash

# Script for automatic release
# Usage: ./release.sh v1.2.0

set -e  # Exit if any command fails

# Check if version was provided
if [ $# -eq 0 ]; then
    echo "Error: You must provide a version as argument"
    echo "Usage: $0 v1.2.0"
    exit 1
fi

VERSION=$1

# Check that version has correct format (vX.Y.Z)
if [[ ! $VERSION =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: Version must have format vX.Y.Z (e.g: v1.2.0)"
    exit 1
fi

echo "🚀 Starting release $VERSION..."

# Check that we're on main branch
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "❌ Error: You must be on 'main' branch to make a release"
    echo "Current branch: $CURRENT_BRANCH"
    exit 1
fi

# Check that there are no pending changes
if [ -n "$(git status --porcelain)" ]; then
    echo "❌ Error: There are uncommitted changes"
    echo "Please commit all changes before making the release"
    git status
    exit 1
fi

# Check that we're up to date with origin
git fetch origin
COMMITS_BEHIND=$(git rev-list HEAD..origin/main --count)
if [ $COMMITS_BEHIND -gt 0 ]; then
    echo "❌ Error: Local branch is behind remote"
    echo "Run: git pull origin main"
    exit 1
fi

# Check that tag doesn't exist
if git tag | grep -q "^$VERSION$"; then
    echo "❌ Error: Tag $VERSION already exists"
    exit 1
fi

# Show current version that will be generated
echo "📦 Current version (before tag):"
python -c "from setuptools_scm import get_version; print(get_version())"

# Confirm release
echo ""
echo "Do you confirm you want to create release $VERSION? (y/N)"
read -r CONFIRM

if [[ ! $CONFIRM =~ ^[Yy]$ ]]; then
    echo "❌ Release cancelled"
    exit 1
fi

# Create and push tag
echo "🏷️  Creating tag $VERSION..."
git tag $VERSION

echo "⬆️  Pushing tag..."
git push origin $VERSION

echo "✅ Release $VERSION created successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Go to GitHub Actions to monitor the deployment"
echo "2. Verify that binaries are built and released"
echo "3. Download and test the new version from GitHub Releases"
echo ""
echo "🔗 Useful links:"
echo "- Actions: https://github.com/edu526/devo-cli/actions"
echo "- Releases: https://github.com/edu526/devo-cli/releases"
