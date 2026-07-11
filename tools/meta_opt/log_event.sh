#!/usr/bin/env bash
# Claude-compatible entry point for the shared Claude/Codex event adapter.
# Logging hooks intentionally produce no stdout.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/hook_adapter.py" --mode logger
