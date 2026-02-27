#!/bin/bash
set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Define local venv path
VENV_DIR="${REPO_ROOT}/.venv"

# Check if virtual environment exists, create if not
if [ ! -d "${VENV_DIR}" ]; then
    echo "Creating virtual environment at ${VENV_DIR}..."
    python3 -m venv "${VENV_DIR}"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "${VENV_DIR}/bin/activate"

# Upgrade pip within the virtual environment
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements from local files using relative paths
if [ -f "${REPO_ROOT}/dev-requirements.txt" ]; then
    echo "Installing dev requirements..."
    pip install -r "${REPO_ROOT}/dev-requirements.txt"
fi

if [ -f "${REPO_ROOT}/requirements.txt" ]; then
    echo "Installing requirements..."
    pip install -r "${REPO_ROOT}/requirements.txt"
fi

# Install additional tools
echo "Installing additional tools..."
pip install repomix ast-grep-cli

# Create output directory for repomix
mkdir -p "${REPO_ROOT}/.opencode/skills/repo"

# Run repomix to generate repo documentation
if [ -d "${REPO_ROOT}" ]; then
    echo "Generating repo documentation..."
    repomix -o "${REPO_ROOT}/.opencode/skills/repo/SKILL.md" \
        --compress \
        --output-show-line-numbers \
        --remove-empty-lines \
        --remove-comments \
        --no-security-check \
        --include "*.py" \
        --ignore "**/tests/*.py" \
        --ignore "**/docs/**" \
        "${REPO_ROOT}/" \
        &
fi

pip install git+https://github.com/jcoffi/code-memory.git
code-memory setup
code-memory update

echo "Setup complete! Virtual environment is at ${VENV_DIR}"
echo "To activate manually, run: source ${VENV_DIR}/bin/activate"
