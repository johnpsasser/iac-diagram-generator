#!/usr/bin/env bash
# IaC Diagram Generator Installer for Claude Code
# Installs the skill into ~/.claude/skills/

set -e

SKILL_NAME="iac-diagram-generator"
SKILL_DIR="$HOME/.claude/skills/$SKILL_NAME"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "IaC Diagram Generator Installer"
echo "=========================================="
echo

# Check if Claude Code skills directory exists
if [ ! -d "$HOME/.claude/skills" ]; then
    echo "Creating Claude Code skills directory..."
    mkdir -p "$HOME/.claude/skills"
fi

# Check if skill already exists
if [ -d "$SKILL_DIR" ]; then
    echo "Skill already exists at $SKILL_DIR"
    read -p "Overwrite existing installation? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi
    echo "Removing existing installation..."
    rm -rf "$SKILL_DIR"
fi

# Copy skill files
echo "Installing skill files to $SKILL_DIR..."
mkdir -p "$SKILL_DIR"
cp -r "$SCRIPT_DIR"/* "$SKILL_DIR/"

# Make scripts executable
chmod +x "$SKILL_DIR"/scripts/*.py

# Check Python version
echo
echo "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 is not installed."
    echo "Please install Python 3 and try again."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "Found Python $PYTHON_VERSION"

# Install Python dependencies
echo
echo "Installing Python dependencies..."
echo "This will install: pyyaml"

# Try to install with different methods based on system
if python3 -m pip install pyyaml --quiet 2>/dev/null; then
    echo "Dependencies installed successfully"
elif python3 -m pip install pyyaml --user --quiet 2>/dev/null; then
    echo "Dependencies installed successfully (user)"
elif python3 -m pip install pyyaml --break-system-packages --quiet 2>/dev/null; then
    echo "Dependencies installed successfully (system packages)"
else
    echo "WARNING: Could not install dependencies automatically."
    echo "Please install manually: pip install pyyaml"
fi

# Check for nanobanana skill (required for diagram generation)
NANOBANANA_DIR="$HOME/.claude/skills/nanobanana"
if [ ! -d "$NANOBANANA_DIR" ]; then
    echo
    echo "=========================================="
    echo "WARNING: nanobanana skill not found"
    echo "=========================================="
    echo
    echo "The IaC Diagram Generator requires the nanobanana skill to generate diagrams."
    echo "Please install it from: https://github.com/johnpsasser/nanobanana"
    echo
    echo "Quick install:"
    echo "  git clone https://github.com/johnpsasser/nanobanana.git /tmp/nanobanana"
    echo "  cd /tmp/nanobanana && ./install.sh"
    echo
fi

# Check for GEMINI_API_KEY
if [ -z "$GEMINI_API_KEY" ]; then
    echo
    echo "=========================================="
    echo "GEMINI_API_KEY not set"
    echo "=========================================="
    echo
    echo "To generate diagrams, you need a Gemini API key."
    echo "Get one at: https://aistudio.google.com/apikey"
    echo
    echo "Then add to your shell configuration:"
    echo "  export GEMINI_API_KEY='your-api-key-here'"
    echo
fi

# Success message
echo
echo "=========================================="
echo "Installation complete!"
echo "=========================================="
echo
echo "The $SKILL_NAME skill is now installed."
echo "Claude Code will automatically use it when you ask to:"
echo "  - Analyze infrastructure code"
echo "  - Generate architecture diagrams"
echo "  - Visualize IaC resources"
echo
echo "Example prompts:"
echo "  'Generate an architecture diagram from my Terraform code'"
echo "  'Show me what this CloudFormation template deploys'"
echo "  'Diagram our Kubernetes application'"
echo
echo "Files installed to: $SKILL_DIR"
echo
