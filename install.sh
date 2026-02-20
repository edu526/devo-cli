#!/bin/bash
set -e

# Devo CLI Installer
# Downloads and installs the latest Devo CLI binary from GitHub Releases

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}Devo CLI Installer${NC}"
echo ""

# Configuration
REPO="edu526/devo-cli"
VERSION="${1:-latest}"

# Detect platform and architecture
PLATFORM=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

case "${ARCH}" in
  x86_64)
    ARCH="amd64"
    ;;
  aarch64|arm64)
    ARCH="arm64"
    ;;
  *)
    echo -e "${RED}❌ Unsupported architecture: ${ARCH}${NC}"
    echo "Supported: x86_64, aarch64, arm64"
    exit 1
    ;;
esac

case "${PLATFORM}" in
  linux|darwin)
    ;;
  *)
    echo -e "${RED}❌ Unsupported platform: ${PLATFORM}${NC}"
    echo "Supported: Linux, macOS"
    echo "For Windows, download from: https://github.com/${REPO}/releases"
    exit 1
    ;;
esac

BINARY_NAME="devo-${PLATFORM}-${ARCH}"

if [ "$VERSION" = "latest" ]; then
  DOWNLOAD_URL="https://github.com/${REPO}/releases/latest/download/${BINARY_NAME}"
else
  DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/${BINARY_NAME}"
fi

echo -e "${BLUE}Platform:${NC} ${PLATFORM}-${ARCH}"
echo -e "${BLUE}Version:${NC} ${VERSION}"
echo ""

# Check if curl is available
if ! command -v curl &> /dev/null; then
  echo -e "${RED}❌ curl is required but not installed${NC}"
  exit 1
fi

# Download binary
echo -e "${BLUE}📥 Downloading Devo CLI...${NC}"
if ! curl -fsSL "${DOWNLOAD_URL}" -o devo; then
  echo -e "${RED}❌ Download failed${NC}"
  echo "Please check:"
  echo "  1. The URL is correct: ${DOWNLOAD_URL}"
  echo "  2. You have internet connection"
  echo "  3. The version exists"
  exit 1
fi

# Make executable
chmod +x devo

# Test the binary
echo ""
echo -e "${BLUE}🧪 Testing binary...${NC}"
if ! ./devo --version; then
  echo -e "${RED}❌ Binary test failed${NC}"
  rm -f devo
  exit 1
fi

echo ""
echo -e "${GREEN}✅ Binary downloaded and verified${NC}"
echo ""

# Determine installation mode
INSTALL_DIR="${DEVO_INSTALL_DIR:-}"

if [ -z "$INSTALL_DIR" ]; then
  # Check if running interactively
  if [ -t 0 ] && [ -t 1 ]; then
    # Interactive mode - ask user
    echo "Where would you like to install Devo CLI?"
    echo "  1) /usr/local/bin (system-wide, requires sudo)"
    echo "  2) ~/.local/bin (user-only, no sudo required)"
    echo "  3) Current directory (manual PATH setup)"
    echo ""
    read -p "Choose [1-3] (default: 2): " choice
    choice=${choice:-2}
  else
    # Non-interactive mode (piped from curl) - use default
    echo -e "${BLUE}Installing to ~/.local/bin (non-interactive mode)${NC}"
    echo "To choose a different location, set DEVO_INSTALL_DIR environment variable"
    echo "or download and run the script directly."
    echo ""
    choice=2
  fi
else
  # Use environment variable
  choice=0
fi

case $choice in
  0)
    # Custom directory from environment variable
    echo ""
    echo -e "${BLUE}Installing to ${INSTALL_DIR}...${NC}"
    mkdir -p "$INSTALL_DIR"
    mv devo "$INSTALL_DIR/"
    echo -e "${GREEN}✅ Installed to ${INSTALL_DIR}/devo${NC}"
    ;;
  1)
    echo ""
    echo -e "${BLUE}Installing to /usr/local/bin...${NC}"
    if sudo mv devo /usr/local/bin/; then
      echo -e "${GREEN}✅ Installed to /usr/local/bin/devo${NC}"
    else
      echo -e "${RED}❌ Installation failed${NC}"
      exit 1
    fi
    ;;
  2)
    echo ""
    echo -e "${BLUE}Installing to ~/.local/bin...${NC}"
    mkdir -p ~/.local/bin
    mv devo ~/.local/bin/
    echo -e "${GREEN}✅ Installed to ~/.local/bin/devo${NC}"

    # Check if ~/.local/bin is in PATH
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
      echo ""
      echo -e "${YELLOW}⚠️  ~/.local/bin is not in your PATH${NC}"
      echo ""
      echo "Add this to your shell configuration file:"
      echo ""
      if [ -n "$ZSH_VERSION" ]; then
        echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc"
        echo "  source ~/.zshrc"
      else
        echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
        echo "  source ~/.bashrc"
      fi
      echo ""
    fi
    ;;
  3)
    echo ""
    echo -e "${GREEN}✅ Binary ready in current directory${NC}"
    echo ""
    echo -e "${YELLOW}To use from anywhere, add to PATH or move to a directory in PATH${NC}"
    ;;
  *)
    echo -e "${RED}Invalid choice${NC}"
    exit 1
    ;;
esac

echo ""
echo -e "${GREEN}🎉 Devo CLI installed successfully!${NC}"
echo ""
echo "Next steps:"
echo "  1. Configure AWS credentials: aws configure"
echo "  2. Test the CLI: devo --help"
echo "  3. Generate a commit: devo commit"
echo ""
echo "Documentation: https://github.com/${REPO}"
