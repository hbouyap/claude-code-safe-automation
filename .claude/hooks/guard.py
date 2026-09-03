#!/usr/bin/env python3
"""PreToolUse guardrail for Claude Code.

Reads a tool-call event as JSON on stdin. If the call is a shell command that
matches a dangerous pattern, it exits 2 (which Claude Code treats as "deny" and
surfaces the stderr message to the model). Otherwise it exits 0 (allow).

This is a deny-list for demonstration. In production, invert it to a per-project
allow-list and log every decision to an append-only file.
"""
import json
import re
import sys

# Patterns that should never run unattended. Each is (regex, human reason).
DANGEROUS = [
    (r"\brm\s+-[a-z]*r[a-z]*f|\brm\s+-[a-z]*f[a-z]*r", "recursive force delete (rm -rf)"),
    (r"\bgit\s+push\b.*(--force|-f)\b", "force push can overwrite remote history"),
    (r"\bgit\s+reset\s+--hard\b", "hard reset discards uncommitted work"),
    (r":\(\)\s*\{\s*:\|:&\s*\};:", "fork bomb"),
    (r"\bmkfs\.|\bdd\s+if=.*of=/dev/", "raw disk / filesystem write"),
    (r"\bchmod\s+-R\s+0?777\b", "world-writable recursive chmod"),
    (r">\s*/dev/sd[a-z]", "writing directly to a block device"),
    (r"\bcurl\b.*\|\s*(sudo\s+)?(sh|bash)\b", "pipe-to-shell from the network"),
    (r"\bwget\b.*\|\s*(sudo\s+)?(sh|bash)\b", "pipe-to-shell from the network"),
]


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # Fail closed on malformed input rather than silently allowing.
        print("guard: could not parse tool event; denying by default", file=sys.stderr)
        return 2

    if event.get("tool_name") != "Bash":
        return 0  # only gate shell commands here

    command = event.get("tool_input", {}).get("command", "")
    for pattern, reason in DANGEROUS:
        if re.search(pattern, command):
            print(f"guard: blocked -- {reason}\n  command: {command}", file=sys.stderr)
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
