#!/bin/bash
# Launcher script for mintmigrate

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if virtual environment is complete; recreate if missing or broken
if [ ! -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
    echo "Setting up virtual environment..."
    rm -rf "$SCRIPT_DIR/.venv"
    if ! python3 -m venv "$SCRIPT_DIR/.venv" 2>/dev/null; then
        echo "python3-venv is not installed. Installing it now (requires sudo)..."
        sudo apt-get install -y python3-venv || { echo "Failed to install python3-venv. Please run: sudo apt install python3-venv"; exit 1; }
        python3 -m venv "$SCRIPT_DIR/.venv"
    fi
    source "$SCRIPT_DIR/.venv/bin/activate"
    pip install -e "$SCRIPT_DIR"
fi

# Activate the virtual environment
source "$SCRIPT_DIR/.venv/bin/activate"

# Run mintmigrate
mintmigrate