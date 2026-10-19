"""Tools the agent can call, plus the safety policy that gates them.

The original repo handed the model a bare `subprocess.run(shell=True)` with no
guard rails. This module keeps the capability but adds a deny-list for
destructive commands and a workspace jail for file writes, so a hallucinated
command cannot wipe the machine.
"""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

# Commands that are never allowed to run unattended.
DENY_PATTERNS: list[str] = [
    r"rm\s+(-[a-zA-Z]*\s+)*-?[a-zA-Z]*[rf]",
    r"\bmkfs(\.\w+)?\b",
    r"\bdd\s+.*of=/dev/",
    r":\(\)\s*\{.*\};\s*:",          # fork bomb
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bhalt\b",
    r"\bpoweroff\b",
    r">\s*/dev/[sh]d[a-z]",
    r"\bchmod\s+-R\s+777\s+/(\s|$)",
    r"\bchown\s+-R\s+.*\s+/(\s|$)",
    r"curl\s+[^|]*\|\s*(ba)?sh",      # curl | sh
    r"wget\s+[^|]*\|\s*(ba)?sh",
    r"\bsudo\s+rm\b",
    r"\bgit\s+push\s+.*--force",
    r"\bgit\s+reset\s+--hard\b",
]

# Paths that must never be written to, even inside the workspace.
PROTECTED_PATH_PATTERNS: list[str] = [
    "*/.git/*",
    "*/.ssh/*",
    "*/id_rsa*",
    "*/.env",
    "*/credentials*",
    "*/.aws/*",
]


class ToolError(RuntimeError):
    """Raised when a tool call is refused or fails."""


@dataclass
class ToolContext:
    """Runtime config shared by every tool."""

    workspace: Path
    allow_write: bool = True
    shell_timeout: int = 60
    max_output_chars: int = 20_000

    def resolve(self, path: str) -> Path:
        """Resolve a path and refuse anything outside the workspace."""
        candidate = (self.workspace / path).resolve() if not os.path.isabs(path) else Path(path).resolve()
        workspace = self.workspace.resolve()
        if candidate != workspace and workspace not in candidate.parents:
            raise ToolError(
                f"Path {candidate} is outside the workspace {workspace}. Refused."
            )
        return candidate


def _is_denied(command: str) -> str | None:
    for pattern in DENY_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return pattern
    return None


def _is_protected(path: Path) -> bool:
    text = str(path)
    return any(fnmatch.fnmatch(text, pat) for pat in PROTECTED_PATH_PATTERNS)


def run_shell(ctx: ToolContext, command: str) -> str:
    """Execute a shell command inside the workspace, with a deny-list."""
    if denied := _is_denied(command):
        return (
            f"REFUSED: command matches blocked pattern {denied!r}. "
            "Destructive commands are not permitted. Ask the user to run it manually."
        )
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=ctx.shell_timeout,
            cwd=str(ctx.workspace),
        )
    except subprocess.TimeoutExpired:
        return f"TIMEOUT: command exceeded {ctx.shell_timeout}s and was killed."
    except Exception as exc:  # noqa: BLE001 - surfaced to the model as text
        return f"EXECUTION ERROR: {exc}"

    parts = []
    if result.stdout:
        parts.append(result.stdout)
    if result.stderr:
        parts.append(f"[stderr]\n{result.stderr}")
    parts.append(f"[exit code: {result.returncode}]")
    output = "\n".join(parts)

    if len(output) > ctx.max_output_chars:
        half = ctx.max_output_chars // 2
        output = (
            f"{output[:half]}\n\n... [{len(output) - ctx.max_output_chars} chars "
            f"truncated] ...\n\n{output[-half:]}"
        )
    return output


def read_file(ctx: ToolContext, path: str, max_lines: int = 2000) -> str:
    """Read a text file from the workspace."""
    target = ctx.resolve(path)
    if not target.exists():
        return f"NOT FOUND: {target}"
    if target.is_dir():
        return f"IS A DIRECTORY: {target}\nContents:\n" + "\n".join(
            sorted(p.name for p in target.iterdir())
        )
    try:
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as exc:  # noqa: BLE001
        return f"READ ERROR: {exc}"
    if len(lines) > max_lines:
        head = "\n".join(f"{i + 1}|{ln}" for i, ln in enumerate(lines[:max_lines]))
        return f"{head}\n... [{len(lines) - max_lines} more lines truncated]"
    return "\n".join(f"{i + 1}|{ln}" for i, ln in enumerate(lines))


def write_file(ctx: ToolContext, path: str, content: str) -> str:
    """Create or overwrite a file in the workspace."""
    if not ctx.allow_write:
        return "REFUSED: file writes are disabled (ALLOW_WRITE=false)."
    target = ctx.resolve(path)
    if _is_protected(target):
        return f"REFUSED: {target} is a protected path (secrets/VCS). Edit it manually."
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return f"WRITE ERROR: {exc}"
    return f"WROTE {len(content)} bytes to {target}"


def list_dir(ctx: ToolContext, path: str = ".") -> str:
    """List a directory in the workspace."""
    target = ctx.resolve(path)
    if not target.is_dir():
        return f"NOT A DIRECTORY: {target}"
    entries = []
    for item in sorted(target.iterdir()):
        if item.name in {".git", "__pycache__", "node_modules"}:
            continue
        suffix = "/" if item.is_dir() else ""
        entries.append(f"{item.name}{suffix}")
    return "\n".join(entries) if entries else "(empty directory)"


# --- Tool schemas exposed to the model (OpenAI function-calling format) ---

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": (
                "Run a bash command in the workspace and return stdout/stderr. "
                "Use for inspecting files, running tests, git, package managers. "
                "Destructive commands are blocked."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The bash command to run."}
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file from the workspace. Returns numbered lines.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to the workspace."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Create or overwrite a file in the workspace. Always provide the "
                "complete file content, not a diff."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to the workspace."},
                    "content": {"type": "string", "description": "Full file content."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files in a workspace directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path. Defaults to '.'."}
                },
            },
        },
    },
]


def build_registry(ctx: ToolContext) -> dict[str, Callable[..., str]]:
    """Map tool name -> callable, with the context bound in."""
    return {
        "run_shell": lambda command: run_shell(ctx, command),
        "read_file": lambda path: read_file(ctx, path),
        "write_file": lambda path, content: write_file(ctx, path, content),
        "list_dir": lambda path=".": list_dir(ctx, path),
    }
