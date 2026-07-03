#!/usr/bin/env bash
# Stop-hook gate (SPEC.md D11): no turn ends with failing tests.
# Wired via .claude/settings.json → hooks.Stop (staged as settings.json.proposed
# until reviewed and renamed). Exit 2 blocks the stop and feeds stderr back to
# the model; exit 0 allows the stop.

set -u

# Guard against infinite loops: if this stop was itself triggered by this
# hook, let it through.
INPUT="$(cat 2>/dev/null || true)"
if [ -n "$INPUT" ] && command -v jq >/dev/null 2>&1; then
  if [ "$(printf '%s' "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null)" = "true" ]; then
    exit 0
  fi
fi

cd "$(dirname "$0")/.." || exit 0

# Phase-0 tolerance: pytest not installed yet, or no tests collected (exit 5).
if ! python3 -c "import pytest" >/dev/null 2>&1; then
  exit 0
fi

output="$(python3 -m pytest -q 2>&1)"
status=$?

if [ "$status" -eq 5 ]; then
  exit 0
fi

if [ "$status" -ne 0 ]; then
  echo "verify.sh: pytest failed — fix the failures before ending the turn." >&2
  printf '%s\n' "$output" | tail -30 >&2
  exit 2
fi

exit 0
