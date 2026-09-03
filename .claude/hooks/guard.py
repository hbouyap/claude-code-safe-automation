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
# Matched case-insensitively, so they cover -rf / -Rf and PowerShell casing alike, on
# both Unix and Windows shells.
DANGEROUS = [
    # Recursive force delete in any flag order (rm -rf, -fr, -R -f, --recursive --force,
    # and the PowerShell `rm -Recurse -Force` alias).
    (r"\brm\b(?=.*(?:-[a-z]*r|--recursive))(?=.*(?:-[a-z]*f|--force))",
     "recursive force delete (rm -rf / --recursive --force)"),
    (r"\bremove-item\b(?=.*-rec)(?=.*-for)",
     "recursive force delete (Remove-Item -Recurse -Force)"),
    (r"\b(?:del|erase)\b(?=.*/s)", "recursive delete (del /s)"),
    (r"\b(?:rd|rmdir)\b(?=.*/s)", "recursive directory delete (rmdir /s)"),
    (r"\bformat\b\s+[a-z]:", "disk format"),
    (r"\bshred\b", "secure file wipe (shred)"),
    (r"\bgit\s+push\b(?=.*(?:--force\b|--force-with-lease\b|\s-f\b))",
     "force push can overwrite remote history"),
    (r"\bgit\s+reset\s+--hard\b", "hard reset discards uncommitted work"),
    (r"\bgit\s+clean\b(?=.*-[a-z]*f)", "git clean permanently deletes untracked files"),
    (r":\(\)\s*\{\s*:\|:&\s*\};:", "fork bomb"),
    (r"\bmkfs\.|\bdd\s+if=.*of=/dev/", "raw disk / filesystem write"),
    (r"\bchmod\s+-R\s+0?777\b", "world-writable recursive chmod"),
    (r">\s*/dev/sd[a-z]", "writing directly to a block device"),
    (r"\b(?:curl|wget)\b.*\|\s*(?:sudo\s+)?(?:sh|bash)\b", "pipe-to-shell from the network"),
    (r"(?:^|\s)(?:sudo|doas)\s", "privilege escalation (sudo/doas) is not permitted"),
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
        if re.search(pattern, command, re.IGNORECASE):
            print(f"guard: blocked -- {reason}\n  command: {command}", file=sys.stderr)
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
