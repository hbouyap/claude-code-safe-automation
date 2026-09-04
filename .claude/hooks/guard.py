#!/usr/bin/env python3
"""PreToolUse guardrail for Claude Code.

Reads a tool-call event as JSON on stdin. If the call is dangerous, it exits 2
(which Claude Code treats as "deny" and surfaces the stderr message to the
model). Otherwise it exits 0 (allow). Covers two tool families:

- Bash: a deny-list of destructive shell commands (see DANGEROUS below).
- Write / Edit: a deny-list of paths that execute later with nobody watching
  (shell rc files, git hooks, ssh config, system directories) even though the
  write itself isn't a shell command.

A regex over a raw command string can't see everything a model can compose
(quote-splitting, encoded payloads piped to a shell, etc.) — for unattended or
adversarial contexts, flip guard.py's shell check to a fail-closed allow-list
instead of extending this deny-list forever. This file stays a deny-list
because it's meant to be read end-to-end as a demo, not to be the last word in
production.

This is a deny-list for demonstration. In production, invert the Bash check to
a per-project allow-list and log every decision to an append-only file.
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

# Paths that execute or grant access later, with nobody watching the moment they're
# written. A Bash-only guardrail misses these entirely: nothing here is a shell
# command, but a shell rc file runs on the next login, a git hook runs on the next
# commit/push, and an ssh/credentials file grants access the moment it's read.
# Matched against tool_input.file_path regardless of how it's spelled (relative,
# absolute, forward or back slashes).
SENSITIVE_PATHS = [
    (r"(^|[/\\])\.(bashrc|zshrc|bash_profile|profile)$", "shell startup file (runs on next login)"),
    (r"(^|[/\\])\.git[/\\]hooks[/\\]", "git hook (runs on the next commit/push)"),
    (r"(^|[/\\])\.ssh[/\\]", "SSH config/keys directory"),
    (r"(^|[/\\])\.aws[/\\]credentials$", "cloud credentials file"),
    (r"(^|[/\\])crontab$|(^|[/\\])etc[/\\]cron", "scheduled-task definition"),
    (r"^(/etc[/\\]|[a-zA-Z]:\\Windows\\System32)", "system directory"),
    (r"WindowsPowerShell[/\\].*profile\.ps1$", "PowerShell profile (runs on next shell start)"),
]


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # Fail closed on malformed input rather than silently allowing.
        print("guard: could not parse tool event; denying by default", file=sys.stderr)
        return 2

    tool = event.get("tool_name")
    tool_input = event.get("tool_input", {})

    if tool == "Bash":
        command = tool_input.get("command", "")
        for pattern, reason in DANGEROUS:
            if re.search(pattern, command, re.IGNORECASE):
                print(f"guard: blocked -- {reason}\n  command: {command}", file=sys.stderr)
                return 2
        return 0

    if tool in ("Write", "Edit"):
        path = tool_input.get("file_path", "")
        for pattern, reason in SENSITIVE_PATHS:
            if re.search(pattern, path, re.IGNORECASE):
                print(f"guard: blocked -- {reason}\n  path: {path}", file=sys.stderr)
                return 2
        return 0

    return 0  # every other tool is out of scope for this guardrail


if __name__ == "__main__":
    sys.exit(main())
