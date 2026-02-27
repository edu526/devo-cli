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

# Determine file extension and download name based on platform
case "${PLATFORM}" in
  linux)
    DOWNLOAD_FILE="${BINARY_NAME}"
    ARCHIVE_FORMAT="binary"
    ;;
  darwin)
    DOWNLOAD_FILE="${BINARY_NAME}.tar.gz"
    ARCHIVE_FORMAT="tarball"
    ;;
  *)
    echo -e "${RED}❌ Unsupported platform: ${PLATFORM}${NC}"
    exit 1
    ;;
esac

if [ "$VERSION" = "latest" ]; then
  DOWNLOAD_URL="https://github.com/${REPO}/releases/latest/download/${DOWNLOAD_FILE}"
else
  DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/${DOWNLOAD_FILE}"
fi

echo -e "${BLUE}Platform:${NC} ${PLATFORM}-${ARCH}"
echo -e "${BLUE}Version:${NC} ${VERSION}"
echo -e "${BLUE}Format:${NC} ${ARCHIVE_FORMAT}"
echo ""

# Check if curl and tar are available
if ! command -v curl &> /dev/null; then
  echo -e "${RED}❌ curl is required but not installed${NC}"
  exit 1
fi

if [ "${ARCHIVE_FORMAT}" = "tarball" ] && ! command -v tar &> /dev/null; then
  echo -e "${RED}❌ tar is required but not installed${NC}"
  exit 1
fi

# Download binary
echo -e "${BLUE}📥 Downloading Devo CLI...${NC}"
if ! curl -fsSL "${DOWNLOAD_URL}" -o "${DOWNLOAD_FILE}"; then
  echo -e "${RED}❌ Download failed${NC}"
  echo "Please check:"
  echo "  1. The URL is correct: ${DOWNLOAD_URL}"
  echo "  2. You have internet connection"
  echo "  3. The version exists"
  exit 1
fi

# Extract if needed
if [ "${ARCHIVE_FORMAT}" = "tarball" ]; then
  echo -e "${BLUE}📦 Extracting archive...${NC}"
  if ! tar -xzf "${DOWNLOAD_FILE}"; then
    echo -e "${RED}❌ Extraction failed${NC}"
    rm -f "${DOWNLOAD_FILE}"
    exit 1
  fi
  rm -f "${DOWNLOAD_FILE}"
  
  # The tarball contains a directory with the binary and _internal folder
  if [ ! -f "${BINARY_NAME}/devo" ]; then
    echo -e "${RED}❌ Binary not found in archive${NC}"
    exit 1
  fi
  
  # Make executable
  chmod +x "${BINARY_NAME}/devo"
  
  # Test the binary (must run from within the directory)
  echo ""
  echo -e "${BLUE}🧪 Testing binary...${NC}"
  if ! "${BINARY_NAME}/devo" --version; then
    echo -e "${RED}❌ Binary test failed${NC}"
    rm -rf "${BINARY_NAME}"
    exit 1
  fi
  
  BINARY_PATH="${BINARY_NAME}"
else
  # Linux: single file binary
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
  
  BINARY_PATH="devo"
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
    
    if [ "${ARCHIVE_FORMAT}" = "tarball" ]; then
      # macOS: move entire directory
      mv "${BINARY_PATH}" "$INSTALL_DIR/"
      echo -e "${GREEN}✅ Installed to ${INSTALL_DIR}/${BINARY_NAME}${NC}"
      echo ""
      echo -e "${YELLOW}Note: Run with: ${INSTALL_DIR}/${BINARY_NAME}/devo${NC}"
    else
      # Linux: move single binary
      mv "${BINARY_PATH}" "$INSTALL_DIR/"
      echo -e "${GREEN}✅ Installed to ${INSTALL_DIR}/devo${NC}"
    fi
    ;;
  1)
    echo ""
    echo -e "${BLUE}Installing to /usr/local/bin...${NC}"
    
    if [ "${ARCHIVE_FORMAT}" = "tarball" ]; then
      # macOS: move directory and create symlink
      if sudo mv "${BINARY_PATH}" /usr/local/lib/; then
        sudo ln -sf "/usr/local/lib/${BINARY_NAME}/devo" /usr/local/bin/devo
        echo -e "${GREEN}✅ Installed to /usr/local/lib/${BINARY_NAME}${NC}"
        echo -e "${GREEN}✅ Symlink created at /usr/local/bin/devo${NC}"
      else
        echo -e "${RED}❌ Installation failed${NC}"
        exit 1
      fi
    else
      # Linux: move single binary
      if sudo mv "${BINARY_PATH}" /usr/local/bin/; then
        echo -e "${GREEN}✅ Installed to /usr/local/bin/devo${NC}"
      else
        echo -e "${RED}❌ Installation failed${NC}"
        exit 1
      fi
    fi
    ;;
  2)
    echo ""
    echo -e "${BLUE}Installing to ~/.local/bin...${NC}"
    mkdir -p ~/.local/bin
    
    if [ "${ARCHIVE_FORMAT}" = "tarball" ]; then
      # macOS: move directory and create symlink
      mkdir -p ~/.local/lib
      mv "${BINARY_PATH}" ~/.local/lib/
      ln -sf "$HOME/.local/lib/${BINARY_NAME}/devo" ~/.local/bin/devo
      echo -e "${GREEN}✅ Installed to ~/.local/lib/${BINARY_NAME}${NC}"
      echo -e "${GREEN}✅ Symlink created at ~/.local/bin/devo${NC}"
    else
      # Linux: move single binary
      mv "${BINARY_PATH}" ~/.local/bin/
      echo -e "${GREEN}✅ Installed to ~/.local/bin/devo${NC}"
    fi

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
    
    if [ "${ARCHIVE_FORMAT}" = "tarball" ]; then
      echo -e "${GREEN}✅ Binary ready in ${BINARY_PATH}${NC}"
      echo ""
      echo -e "${YELLOW}To use: ./${BINARY_PATH}/devo${NC}"
      echo -e "${YELLOW}To add to PATH, move to a directory in PATH or create a symlink${NC}"
    else
      echo -e "${GREEN}✅ Binary ready in current directory${NC}"
      echo ""
      echo -e "${YELLOW}To use from anywhere, add to PATH or move to a directory in PATH${NC}"
    fi
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
echo "  2. Set up shell completion: devo completion --install"
echo "  3. Test the CLI: devo --help"
echo "  4. Generate a commit: devo commit"
echo ""
echo "Documentation: https://github.com/${REPO}"
