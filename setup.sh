#!/bin/bash
# Copyright 2026 icecake0141
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# This file was created or modified with the assistance of an AI (Large Language Model).
# Review required for correctness, security, and licensing.

# Setup script for nw-watch
# This script helps users set up nw-watch for local development or production use

set -e

echo "============================================"
echo "nw-watch Setup Script"
echo "============================================"
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.11"

if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"; then
    echo "Error: Python $required_version or higher is required."
    echo "Current version: $python_version"
    exit 1
fi

echo "✓ Python $python_version found"
echo ""

# Ask user for installation type
echo "Select installation type:"
echo "1) Production (pip install .)"
echo "2) Development (pip install -e .)"
echo "3) Development with test dependencies (pip install -e \".[dev]\")"
echo ""
read -p "Enter choice [1-3]: " choice

case $choice in
    1)
        echo ""
        echo "Installing nw-watch for production..."
        pip install .
        ;;
    2)
        echo ""
        echo "Installing nw-watch in editable mode..."
        pip install -e .
        ;;
    3)
        echo ""
        echo "Installing nw-watch in editable mode with dev dependencies..."
        pip install -e ".[dev]"
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

echo ""
echo "============================================"
echo "Installation complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "1. Copy config.example.yaml to config.yaml"
echo "   cp config.example.yaml config.yaml"
echo ""
echo "2. Edit config.yaml with your device details"
echo ""
echo "3. Set device passwords as environment variables"
echo "   export DEVICEA_PASSWORD=\"your_password\""
echo ""
echo "4. Start the collector:"
echo "   python -m nw_watch.collector.main --config config.yaml"
echo ""
echo "5. Start the web app (in a separate terminal):"
echo "   uvicorn nw_watch.webapp.main:app --host 127.0.0.1 --port 8000"
echo ""
echo "For more information, see README.md"
echo ""
