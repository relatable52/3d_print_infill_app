#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo "========================================"
echo "3D Print App Launcher"
echo "========================================"
echo

if ! command -v uv >/dev/null 2>&1; then
  echo "uv was not found. Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "Syncing project dependencies..."
uv sync

echo
echo "Launching app..."
uv run -m src.app
