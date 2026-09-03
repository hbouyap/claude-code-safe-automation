# MCP server — `notes`

A minimal [Model Context Protocol](https://modelcontextprotocol.io) server exposing two safe
tools over stdio. Use it as a template for exposing your own tools to Claude Code.

## Install

```bash
pip install "mcp>=1.0"
```

## Register with Claude Code

```bash
claude mcp add notes -- python mcp/notes_server.py
```

Or add it manually to your project `.mcp.json`:

```json
{
  "mcpServers": {
    "notes": {
      "command": "python",
      "args": ["mcp/notes_server.py"]
    }
  }
}
```

Then inside Claude Code:

- "add a note: refactor the auth module" → calls `add_note`
- "list my notes" → calls `list_notes`

## Make it yours

Replace the bodies of `add_note` / `list_notes` with real logic:

- Read rows from your database (return them as text).
- Call an internal HTTP API (keep credentials in env vars, never in code).
- Trigger a safe action in a SaaS you control.

Keep every tool **read-mostly or reversible** unless you also add a confirmation gate — the
same discipline the guardrail hook in `.claude/hooks/guard.py` enforces for shell commands.
