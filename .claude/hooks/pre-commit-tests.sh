#!/usr/bin/env bash
# PreToolUse hook (Bash): se il comando contiene "git commit", esegue i test
# in tests/ con il python del venv e blocca il commit (exit 2) se falliscono.
input=$(cat)
case "$input" in
  *"git commit"*)
    for f in tests/test_*.py; do
      ".venv/Scripts/python.exe" "$f" || {
        echo "Test falliti ($f): commit bloccato." >&2
        exit 2
      }
    done
    ;;
esac
