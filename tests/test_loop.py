#!/usr/bin/env python3
"""End-to-end test of the agent loop with a scripted fake provider.

This exercises the real Agent class — message construction, tool dispatch,
tool-result feedback, skill loading — without needing a model or network.

    python3 tests/test_loop.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.core import Agent  # noqa: E402


class ScriptedClient:
    """Replays a fixed list of assistant messages, recording what it was sent."""

    def __init__(self, script):
        self.script = list(script)
        self.seen = []

    def complete(self, messages, tools=None, temperature=0.2):
        # Snapshot the conversation so tests can assert on it later.
        self.seen.append([dict(m) for m in messages])
        if not self.script:
            return {"role": "assistant", "content": "(script exhausted)"}
        return self.script.pop(0)


def make_agent(workspace, script):
    agent = Agent(workspace=workspace, provider="ollama", verbose=False)
    agent.client = ScriptedClient(script)
    return agent


def test_plain_answer_no_tools():
    with tempfile.TemporaryDirectory() as tmp:
        agent = make_agent(Path(tmp), [{"role": "assistant", "content": "Hello there."}])
        reply = agent.run_turn("hi")
        assert reply == "Hello there."
        # system + user + assistant
        assert len(agent.messages) == 3
        assert agent.messages[0]["role"] == "system"
        assert agent.messages[1] == {"role": "user", "content": "hi"}


def test_tool_call_is_executed_and_fed_back():
    with tempfile.TemporaryDirectory() as tmp:
        script = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "run_shell",
                            "arguments": '{"command": "echo from-tool"}',
                        },
                    }
                ],
            },
            {"role": "assistant", "content": "The command printed from-tool."},
        ]
        agent = make_agent(Path(tmp), script)
        reply = agent.run_turn("run echo")

        assert reply == "The command printed from-tool."
        # The tool result must have been appended with the matching id.
        tool_msgs = [m for m in agent.messages if m["role"] == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0]["tool_call_id"] == "call_1"
        assert "from-tool" in tool_msgs[0]["content"]
        # And the assistant tool_calls turn must be preserved verbatim.
        assistant_tool = [
            m for m in agent.messages if m["role"] == "assistant" and m.get("tool_calls")
        ]
        assert len(assistant_tool) == 1


def test_write_then_read_via_tools():
    with tempfile.TemporaryDirectory() as tmp:
        script = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": '{"path": "out.txt", "content": "hello world"}',
                        },
                    }
                ],
            },
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c2",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": '{"path": "out.txt"}'},
                    }
                ],
            },
            {"role": "assistant", "content": "Verified the file."},
        ]
        agent = make_agent(Path(tmp), script)
        reply = agent.run_turn("write and read")

        assert reply == "Verified the file."
        assert (Path(tmp) / "out.txt").read_text() == "hello world"
        tool_msgs = [m for m in agent.messages if m["role"] == "tool"]
        assert "hello world" in tool_msgs[1]["content"]


def test_denied_command_returns_refusal_to_model():
    with tempfile.TemporaryDirectory() as tmp:
        script = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "run_shell", "arguments": '{"command": "rm -rf /"}'},
                    }
                ],
            },
            {"role": "assistant", "content": "Understood, I will not do that."},
        ]
        agent = make_agent(Path(tmp), script)
        agent.run_turn("delete everything")

        tool_msgs = [m for m in agent.messages if m["role"] == "tool"]
        assert tool_msgs[0]["content"].startswith("REFUSED")


def test_unknown_tool_and_bad_json_are_recoverable():
    with tempfile.TemporaryDirectory() as tmp:
        script = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "no_such_tool", "arguments": "{}"},
                    }
                ],
            },
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c2",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": "{not json"},
                    }
                ],
            },
            {"role": "assistant", "content": "Recovered."},
        ]
        agent = make_agent(Path(tmp), script)
        reply = agent.run_turn("break things")

        assert reply == "Recovered."
        tool_msgs = [m for m in agent.messages if m["role"] == "tool"]
        assert "UNKNOWN TOOL" in tool_msgs[0]["content"]
        assert "BAD ARGUMENTS" in tool_msgs[1]["content"]


def test_skill_loading():
    with tempfile.TemporaryDirectory() as tmp:
        skills_dir = Path(tmp) / "skills"
        skills_dir.mkdir()
        (skills_dir / "deploy.md").write_text(
            "---\nname: deploy\ndescription: Use when deploying.\n---\n"
            "# Deploy\nRun the tests first.\n"
        )
        script = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "load_skill", "arguments": '{"name": "deploy"}'},
                    }
                ],
            },
            {"role": "assistant", "content": "Following the deploy skill."},
        ]
        agent = make_agent(Path(tmp), script)

        # The skill index must be in the system prompt, and the tool registered.
        assert "deploy: Use when deploying." in agent.messages[0]["content"]
        assert "load_skill" in agent.tools

        reply = agent.run_turn("deploy the app")
        assert reply == "Following the deploy skill."
        tool_msgs = [m for m in agent.messages if m["role"] == "tool"]
        assert "Run the tests first." in tool_msgs[0]["content"]


def test_unknown_skill_name():
    with tempfile.TemporaryDirectory() as tmp:
        skills_dir = Path(tmp) / "skills"
        skills_dir.mkdir()
        (skills_dir / "a.md").write_text("---\nname: alpha\ndescription: d\n---\nbody")
        script = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "load_skill", "arguments": '{"name": "nope"}'},
                    }
                ],
            },
            {"role": "assistant", "content": "ok"},
        ]
        agent = make_agent(Path(tmp), script)
        agent.run_turn("x")
        tool_msgs = [m for m in agent.messages if m["role"] == "tool"]
        assert "UNKNOWN SKILL" in tool_msgs[0]["content"]
        assert "alpha" in tool_msgs[0]["content"]


def test_max_tool_rounds_guard():
    """A model that loops forever on tool calls must be stopped."""
    with tempfile.TemporaryDirectory() as tmp:
        looping = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "c",
                    "type": "function",
                    "function": {"name": "list_dir", "arguments": "{}"},
                }
            ],
        }
        agent = make_agent(Path(tmp), [dict(looping) for _ in range(50)])
        reply = agent.run_turn("loop forever")
        assert "exceeded max tool rounds" in reply


def main() -> int:
    tests = [
        (name, fn)
        for name, fn in sorted(globals().items())
        if name.startswith("test_") and callable(fn)
    ]
    failures = 0
    for name, fn in tests:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"FAIL  {name}: {type(exc).__name__}: {exc}")
        else:
            print(f"ok    {name}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
