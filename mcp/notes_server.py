#!/usr/bin/env python3
"""Minimal MCP server (stdio) exposing two safe tools to Claude Code.

This is a template. The two tools below (`add_note`, `list_notes`) persist to a
local JSON file. Replace their bodies with your own domain logic — an internal
API call, a database read, a ticketing action — and Claude Code can call it.

Run standalone:
    python mcp/notes_server.py

Wire into Claude Code: see mcp/README.md.

Requires: pip install "mcp>=1.0"
"""
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

STORE = Path(__file__).with_name("notes.json")
mcp = FastMCP("notes")


def _load() -> list[dict]:
    if STORE.exists():
        try:
            return json.loads(STORE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save(notes: list[dict]) -> None:
    STORE.write_text(json.dumps(notes, indent=2), encoding="utf-8")


@mcp.tool()
def add_note(text: str) -> str:
    """Append a note. Returns the id of the created note."""
    notes = _load()
    note = {"id": len(notes) + 1, "text": text}
    notes.append(note)
    _save(notes)
    return f"added note #{note['id']}"


@mcp.tool()
def list_notes() -> str:
    """Return all stored notes as a numbered list."""
    notes = _load()
    if not notes:
        return "(no notes yet)"
    return "\n".join(f"{n['id']}. {n['text']}" for n in notes)


if __name__ == "__main__":
    mcp.run()
