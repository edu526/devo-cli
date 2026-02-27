#!/bin/bash
set -e

# Devo CLI Build Script
# Unified script for building binaries in all environments

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Default options
CREATE_RELEASE=false
CI_MODE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --release)
      CREATE_RELEASE=true
      shift
      ;;
    --ci)
      CI_MODE=true
      shift
      ;;
    --help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --release    Create versioned release with platform-specific naming"
      echo "  --ci         CI/CD mode (installs all dependencies, fetches git history)"
      echo "  --help       Show this help message"
      echo ""
      echo "Examples:"
      echo "  $0                    # Simple build to dist/devo"
      echo "  $0 --release          # Build with versioned release"
      echo "  $0 --ci --release     # CI/CD build with release"
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

echo "🔨 Building Devo CLI Binary..."
echo ""

# CI Mode: Install dependencies and fetch git history
if [ "$CI_MODE" = true ]; then
  echo -e "${BLUE}📦 CI Mode: Setting up environment...${NC}"

  # Fetch full git history for versioning
  git fetch --unshallow 2>/dev/null || echo "Already unshallow"

  # Install dependencies
  python -m pip install --quiet setuptools_scm
  python -m pip install --quiet -r requirements.txt
  python -m pip install --quiet .
  python -m pip install --quiet pyinstaller
else
  # Local Mode: Check virtual environment
  if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not activated${NC}"
    echo "Activating venv..."
    if [ -f "venv/bin/activate" ]; then
      source venv/bin/activate
    else
      echo -e "${RED}❌ Virtual environment not found. Run 'make venv' first.${NC}"
      exit 1
    fi
  fi

  # Install PyInstaller if needed
  if ! pip show pyinstaller > /dev/null 2>&1; then
    echo -e "${BLUE}📦 Installing PyInstaller...${NC}"
    pip install pyinstaller
  fi
fi

# Clean previous builds
echo -e "${BLUE}🧹 Cleaning previous builds...${NC}"
rm -rf build dist *.spec.bak

# Build the binary
echo -e "${BLUE}🔨 Building binary with PyInstaller...${NC}"
pyinstaller devo.spec --clean

# Check if build was successful
# Linux: onefile mode (dist/devo)
# macOS/Windows: onedir mode (dist/devo/devo)
if [ "$(uname -s)" = "Linux" ]; then
  if [ ! -f "dist/devo" ]; then
    echo -e "${RED}❌ Build failed - binary not found at dist/devo${NC}"
    exit 1
  fi
  BINARY_PATH="dist/devo"
else
  if [ ! -f "dist/devo/devo" ]; then
    echo -e "${RED}❌ Build failed - binary not found at dist/devo/devo${NC}"
    exit 1
  fi
  BINARY_PATH="dist/devo/devo"
fi

echo ""
echo -e "${GREEN}✅ Build successful!${NC}"
echo ""

# Test the binary
echo -e "${BLUE}🧪 Testing binary...${NC}"
"${BINARY_PATH}" --version
echo ""

# Create release if requested
if [ "$CREATE_RELEASE" = true ]; then
  echo -e "${BLUE}📦 Creating versioned release...${NC}"

  # Get version from environment or git tags
  if [ -n "$RELEASE_VERSION" ]; then
    VERSION="$RELEASE_VERSION"
  else
    VERSION=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
  fi

  PLATFORM=$(uname -s | tr '[:upper:]' '[:lower:]')

  # Use FORCE_ARCH if set (for CI cross-compilation), otherwise detect
  if [ -n "$FORCE_ARCH" ]; then
    ARCH="$FORCE_ARCH"
  else
    ARCH=$(uname -m)
    case "${ARCH}" in
      x86_64)
        ARCH="amd64"
        ;;
      aarch64|arm64)
        ARCH="arm64"
        ;;
    esac
  fi

  echo ""
  echo -e "${BLUE}📋 Release Info:${NC}"
  echo "  Version: ${VERSION}"
  echo "  Platform: ${PLATFORM}"
  echo "  Architecture: ${ARCH}"
  echo ""

  # Create release directory
  RELEASE_DIR="release/${VERSION}"
  mkdir -p "${RELEASE_DIR}"

  BINARY_NAME="devo-${PLATFORM}-${ARCH}"

  # Copy the binary (different structure for Linux vs macOS/Windows)
  if [ "$(uname -s)" = "Linux" ]; then
    # Linux: single file
    cp dist/devo "${RELEASE_DIR}/${BINARY_NAME}"
    chmod +x "${RELEASE_DIR}/${BINARY_NAME}"

    # Test release binary
    echo -e "${BLUE}🧪 Testing release binary...${NC}"
    "${RELEASE_DIR}/${BINARY_NAME}" --version
  else
    # macOS/Windows: directory
    cp -r dist/devo "${RELEASE_DIR}/${BINARY_NAME}"
    chmod +x "${RELEASE_DIR}/${BINARY_NAME}/devo"

    # Test release binary
    echo -e "${BLUE}🧪 Testing release binary...${NC}"
    "${RELEASE_DIR}/${BINARY_NAME}/devo" --version
  fi

  # Create checksums
  echo ""
  echo -e "${BLUE}🔐 Creating checksums...${NC}"
  cd "${RELEASE_DIR}"

  # Create tarball for macOS/Windows (directory), checksum for Linux (single file)
  if [ "$(uname -s)" = "Linux" ]; then
    # Linux: checksum the single binary
    if command -v sha256sum &> /dev/null; then
      sha256sum "${BINARY_NAME}" > SHA256SUMS
    elif command -v shasum &> /dev/null; then
      shasum -a 256 "${BINARY_NAME}" > SHA256SUMS
    else
      echo -e "${YELLOW}⚠️  Warning: No checksum tool found${NC}"
    fi
  else
    # macOS/Windows: create tarball and checksum
    tar -czf "${BINARY_NAME}.tar.gz" "${BINARY_NAME}"

    if command -v sha256sum &> /dev/null; then
      sha256sum "${BINARY_NAME}.tar.gz" > SHA256SUMS
    elif command -v shasum &> /dev/null; then
      shasum -a 256 "${BINARY_NAME}.tar.gz" > SHA256SUMS
    else
      echo -e "${YELLOW}⚠️  Warning: No checksum tool found${NC}"
    fi
  fi

  cd - > /dev/null

  echo ""
  echo -e "${GREEN}✅ Release ready!${NC}"
  echo ""

  if [ "$(uname -s)" = "Linux" ]; then
    echo "Binary: ${RELEASE_DIR}/${BINARY_NAME}"
    echo "Size: $(du -h ${RELEASE_DIR}/${BINARY_NAME} | cut -f1)"
  else
    echo "Binary: ${RELEASE_DIR}/${BINARY_NAME}/devo"
    echo "Archive: ${RELEASE_DIR}/${BINARY_NAME}.tar.gz"
    echo "Size: $(du -h ${RELEASE_DIR}/${BINARY_NAME}.tar.gz | cut -f1)"
  fi
  echo ""
  echo "Files in release:"
  ls -lh "${RELEASE_DIR}"
else
  if [ "$(uname -s)" = "Linux" ]; then
    echo "Binary location: dist/devo"
    echo "Binary size: $(du -h dist/devo | cut -f1)"
  else
    echo "Binary location: dist/devo/devo"
    echo "Binary size: $(du -h dist/devo | cut -f1)"
  fi
  echo ""
  echo "To create a versioned release, run with --release flag"
fi

echo ""
echo -e "${GREEN}✅ Done!${NC}"
