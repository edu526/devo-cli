#!/bin/bash

# Devo CLI - Development Setup Script
# This script sets up the complete development environment

set -e

echo "🚀 Devo CLI - Development Setup"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
    echo ""
else
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
    echo ""
fi

# Check if venv is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
    echo -e "${GREEN}✓ Virtual environment activated${NC}"
    echo ""
else
    echo -e "${GREEN}✓ Virtual environment already active${NC}"
    echo ""
fi

# Install package in editable mode
echo -e "${YELLOW}Installing package in editable mode...${NC}"
pip install -e . --quiet
echo -e "${GREEN}✓ Package installed${NC}"
echo ""

# Install development dependencies
echo -e "${YELLOW}Installing development dependencies...${NC}"
pip install -r requirements.txt --quiet
echo -e "${GREEN}✓ Development dependencies installed${NC}"
echo ""

# Refresh shell cache
echo -e "${YELLOW}Refreshing shell cache...${NC}"
hash -r 2>/dev/null || rehash 2>/dev/null || true
echo -e "${GREEN}✓ Shell cache refreshed${NC}"
echo ""

# Setup shell completion
echo -e "${YELLOW}Setting up shell completion...${NC}"
SHELL_NAME=$(basename $SHELL)

if [ "$SHELL_NAME" = "zsh" ]; then
    if ! grep -q "_DEVO_COMPLETE=zsh_source devo" ~/.zshrc 2>/dev/null; then
        echo 'eval "$(_DEVO_COMPLETE=zsh_source devo)"' >> ~/.zshrc
        echo -e "${GREEN}✓ Added completion to ~/.zshrc${NC}"
    else
        echo -e "${GREEN}✓ Completion already configured in ~/.zshrc${NC}"
    fi

    # Enable in current session
    eval "$(_DEVO_COMPLETE=zsh_source devo)" 2>/dev/null || true
    echo -e "${GREEN}✓ Completion enabled in current session${NC}"

elif [ "$SHELL_NAME" = "bash" ]; then
    if ! grep -q "_DEVO_COMPLETE=bash_source devo" ~/.bashrc 2>/dev/null; then
        echo 'eval "$(_DEVO_COMPLETE=bash_source devo)"' >> ~/.bashrc
        echo -e "${GREEN}✓ Added completion to ~/.bashrc${NC}"
    else
        echo -e "${GREEN}✓ Completion already configured in ~/.bashrc${NC}"
    fi

    # Enable in current session
    eval "$(_DEVO_COMPLETE=bash_source devo)" 2>/dev/null || true
    echo -e "${GREEN}✓ Completion enabled in current session${NC}"
else
    echo -e "${YELLOW}⚠️  Shell $SHELL_NAME not supported for auto-completion${NC}"
    echo "Run 'devo completion' for manual instructions"
fi

echo ""
echo -e "${GREEN}=== Setup Complete ===${NC}"
echo ""
echo "You can now use the Devo CLI:"
echo -e "  ${BLUE}devo --help${NC}"
echo ""
echo "Try tab completion:"
echo -e "  ${BLUE}devo <TAB>${NC}"
echo ""
echo "Useful commands:"
echo -e "  ${BLUE}make help${NC}       - Show all available make commands"
echo -e "  ${BLUE}make refresh${NC}    - Refresh after code changes"
echo -e "  ${BLUE}make test${NC}       - Run tests"
echo -e "  ${BLUE}make lint${NC}       - Check code style"
echo ""
echo "Happy coding! 🎉"
