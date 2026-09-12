#!/usr/bin/env bash
# Convenience launcher for Businessy - بيزنسي (macOS / Linux)
set -e

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

echo ""
echo "Starting Businessy - بيزنسي ..."
echo "Make sure 'ollama serve' is running and 'qwen2.5:7b' is pulled."
echo ""

python3 frontend/app.py
