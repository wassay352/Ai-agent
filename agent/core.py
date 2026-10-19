"""The agent loop: model -> tool call -> result -> model, until done.

This replaces the original agent.py, which had no tool-call handling at all
(it passed a Python function to the Gemini SDK and hoped). Here the loop is
explicit and provider-agnostic.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from agent.providers import ChatClient, ProviderError, resolve_provider
from agent.skills import build_load_skill_schema, build_skills_prompt, load_skills
from agent.tools import TOOL_SCHEMAS, ToolContext, build_registry

MAX_TOOL_ROUNDS = 12  # guard against infinite tool loops

DEFAULT_SYSTEM = """You are a personal AI agent running on the user's Linux machine.

You have real tools: run_shell, read_file, write_file, list_dir, load_skill.
Use them instead of guessing. Read a file before editing it. Run tests after
changing code. Prefer small, verifiable steps over large blind rewrites.

Rules:
- Never claim you did something you did not actually do with a tool.
- If a command fails, read the error and fix the cause; do not retry blindly.
- Destructive commands are blocked by policy. If you need one, ask the user.
- Keep answers concise. Show the evidence (command output, file path), not a story.
"""


class Agent:
    def __init__(
        self,
        workspace: Path | None = None,
        provider: str | None = None,
        model: str | None = None,
        allow_write: bool = True,
        verbose: bool = True,
    ):
        self.workspace = (workspace or Path.cwd()).resolve()
        self.config = resolve_provider(provider, model)
        self.client = ChatClient(self.config)
        self.verbose = verbose

        self.ctx = ToolContext(workspace=self.workspace, allow_write=allow_write)
        self.tools = build_registry(self.ctx)
        self.skills = load_skills(self.workspace / "skills")

        self.schemas = list(TOOL_SCHEMAS)
        if self.skills:
            self.schemas.append(build_load_skill_schema())
            self.tools["load_skill"] = self._load_skill

        self.messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._system_prompt()}
        ]

    def _system_prompt(self) -> str:
        parts = [DEFAULT_SYSTEM, f"\nWorkspace root: {self.workspace}"]
        if extra := os.getenv("SYSTEM_PROMPT_EXTRA", "").strip():
            parts.append(f"\n{extra}")
        if skills_prompt := build_skills_prompt(self.skills):
            parts.append(f"\n{skills_prompt}")
        return "\n".join(parts)

    def _load_skill(self, name: str) -> str:
        skill = self.skills.get(name)
        if not skill:
            known = ", ".join(self.skills) or "(none installed)"
            return f"UNKNOWN SKILL {name!r}. Available: {known}"
        return f"# Skill: {skill.name}\n\n{skill.body}"

    def _log(self, text: str) -> None:
        if self.verbose:
            print(text, flush=True)

    def _execute_tool(self, name: str, raw_args: str) -> str:
        try:
            args = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError as exc:
            return f"BAD ARGUMENTS (invalid JSON): {exc}"

        fn = self.tools.get(name)
        if not fn:
            return f"UNKNOWN TOOL {name!r}. Available: {', '.join(sorted(self.tools))}"
        try:
            return fn(**args)
        except TypeError as exc:
            return f"BAD ARGUMENTS for {name}: {exc}"
        except Exception as exc:  # noqa: BLE001 - fed back to the model
            return f"TOOL ERROR in {name}: {exc}"

    def run_turn(self, user_input: str) -> str:
        """Process one user message, executing tool calls until the model stops."""
        self.messages.append({"role": "user", "content": user_input})

        for _ in range(MAX_TOOL_ROUNDS):
            try:
                message = self.client.complete(self.messages, tools=self.schemas)
            except ProviderError as exc:
                return f"[provider error] {exc}"

            tool_calls = message.get("tool_calls") or []
            content = message.get("content") or ""

            # Preserve the assistant turn verbatim so tool_call ids line up.
            self.messages.append(
                {
                    "role": "assistant",
                    "content": content,
                    **({"tool_calls": tool_calls} if tool_calls else {}),
                }
            )

            if not tool_calls:
                return content or "(empty response)"

            for call in tool_calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments", "")
                self._log(f"  -> {name}({args[:200]})")
                result = self._execute_tool(name, args)
                preview = result if len(result) < 400 else result[:400] + "..."
                self._log(f"  <- {preview}")
                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "name": name,
                        "content": result,
                    }
                )

        return "[stopped: exceeded max tool rounds]"

    def chat(self) -> None:
        """Interactive REPL."""
        print(f"=== Personal AI Agent ===")
        print(f"provider : {self.config.name}")
        print(f"model    : {self.config.default_model}")
        print(f"workspace: {self.workspace}")
        print(f"skills   : {len(self.skills)} loaded")
        print("Type 'exit' to quit, '/clear' to reset history.\n")

        while True:
            try:
                user_input = input("you > ").strip()
            except (KeyboardInterrupt, EOFError):
                print()
                break

            if not user_input:
                continue
            if user_input.lower() in {"exit", "quit"}:
                break
            if user_input == "/clear":
                self.messages = self.messages[:1]
                print("[history cleared]\n")
                continue

            reply = self.run_turn(user_input)
            print(f"\nagent > {reply}\n")
