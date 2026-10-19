"""Ollama provider — connects to a local Ollama instance."""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import Any


class OllamaProvider:
    """Provider that uses a local Ollama server."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5-coder:1.5b",
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send a chat completion request to Ollama."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Ollama connection failed: {exc}") from exc

        message = data.get("message", {})
        content = message.get("content", "")
        tool_calls = message.get("tool_calls")

        normalized_tool_calls = None
        if tool_calls:
            normalized_tool_calls = []
            for i, tc in enumerate(tool_calls):
                func = tc.get("function", {})
                normalized_tool_calls.append({
                    "id": f"call_ollama_{i}",
                    "type": "function",
                    "function": {
                        "name": func.get("name", ""),
                        "arguments": json.dumps(func.get("arguments", {})),
                    },
                })

        return {"content": content, "tool_calls": normalized_tool_calls}

    def health(self) -> tuple[bool, str]:
        """Check if Ollama is reachable."""
        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/tags",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", [])]
                if self.model in models:
                    return True, f"ok (model: {self.model})"
                return True, f"ok (available: {', '.join(models)})"
        except Exception as exc:
            return False, str(exc)
