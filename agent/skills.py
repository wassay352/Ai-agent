"""Skills loader — how you 'train' the agent without fine-tuning.

A skill is a markdown file with YAML-ish frontmatter in the skills/ directory:

    ---
    name: git-workflow
    description: Use when committing, branching or opening PRs.
    ---
    # Git workflow
    Always run `git status` before staging. Never force-push to main.

Only the name + description of every skill is injected into the system prompt
(cheap). The full body is loaded on demand via the `load_skill` tool, so you can
keep hundreds of skills without blowing the context window. This mirrors how
progressive-disclosure skill systems work in production agents.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path

    @property
    def summary_line(self) -> str:
        return f"- {self.name}: {self.description}"


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    raw_meta, body = match.groups()
    meta: dict[str, str] = {}
    for line in raw_meta.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip().lower()] = value.strip().strip("'\"")
    return meta, body


def load_skills(skills_dir: Path) -> dict[str, Skill]:
    """Load every .md skill file. Malformed files are skipped, not fatal."""
    skills: dict[str, Skill] = {}
    if not skills_dir.is_dir():
        return skills

    for path in sorted(skills_dir.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        meta, body = _parse_frontmatter(text)
        name = meta.get("name") or path.stem
        description = meta.get("description") or "(no description)"
        skills[name] = Skill(
            name=name, description=description, body=body.strip(), path=path
        )
    return skills


def build_skills_prompt(skills: dict[str, Skill]) -> str:
    """The cheap index that always lives in the system prompt."""
    if not skills:
        return ""
    lines = [
        "## Available skills",
        "",
        "These are procedures you have been taught. When a task matches one, "
        "call `load_skill` with its name FIRST and follow the steps exactly.",
        "",
    ]
    lines.extend(skill.summary_line for skill in skills.values())
    return "\n".join(lines)


def build_load_skill_schema() -> dict:
    """Tool schema for on-demand skill loading."""
    return {
        "type": "function",
        "function": {
            "name": "load_skill",
            "description": (
                "Load the full instructions for one of your available skills. "
                "Call this before starting any task that matches a skill description."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The skill name to load."}
                },
                "required": ["name"],
            },
        },
    }
