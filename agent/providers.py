"""Provider-agnostic LLM layer.

One config line (PROVIDER in .env) switches between Ollama, Groq and OpenRouter.
All three speak the OpenAI chat-completions wire format, so a single client
implementation covers them; only base_url, api_key and default model differ.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterator


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    api_key: str
    default_model: str
    # Ollama ignores the key but the OpenAI client still wants one.
    requires_key: bool = True


class ProviderError(RuntimeError):
    """Raised when the provider is misconfigured or the request fails."""


# Registry: add a provider here and it is immediately selectable via PROVIDER=.
REGISTRY: dict[str, dict[str, str]] = {
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "key_env": "OLLAMA_API_KEY",
        "default_model": "qwen2.5-coder:7b",
        "requires_key": "false",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "default_model": "llama-3.3-70b-versatile",
        "requires_key": "true",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "default_model": "anthropic/claude-3.5-sonnet",
        "requires_key": "true",
    },
}


def resolve_provider(name: str | None = None, model: str | None = None) -> ProviderConfig:
    """Resolve the active provider from an explicit name or the environment."""
    name = (name or os.getenv("PROVIDER") or "ollama").strip().lower()

    if name not in REGISTRY:
        known = ", ".join(sorted(REGISTRY))
        raise ProviderError(f"Unknown provider {name!r}. Known providers: {known}")

    spec = REGISTRY[name]
    requires_key = spec["requires_key"] == "true"
    api_key = os.getenv(spec["key_env"], "").strip()

    if requires_key and not api_key:
        raise ProviderError(
            f"PROVIDER={name} needs {spec['key_env']} set in your .env file."
        )

    # Ollama accepts any non-empty token; supply a placeholder so the client
    # does not reject the request.
    if not api_key:
        api_key = "ollama"

    return ProviderConfig(
        name=name,
        base_url=os.getenv("BASE_URL", "").strip() or spec["base_url"],
        api_key=api_key,
        default_model=model or os.getenv("MODEL", "").strip() or spec["default_model"],
        requires_key=requires_key,
    )


class ChatClient:
    """Minimal OpenAI-compatible chat client built on urllib (no SDK needed)."""

    def __init__(self, config: ProviderConfig, timeout: int = 120):
        self.config = config
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }
        # OpenRouter asks for attribution headers; harmless elsewhere.
        if self.config.name == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/wassay352/Ai-agent"
            headers["X-Title"] = "Ai-agent"
        return headers

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers=self._headers(), method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(f"HTTP {exc.code} from {self.config.name}: {body}") from exc
        except urllib.error.URLError as exc:
            hint = ""
            if self.config.name == "ollama":
                hint = " Is Ollama running? Try: ollama serve"
            raise ProviderError(
                f"Cannot reach {self.config.name} at {self.config.base_url}.{hint} ({exc.reason})"
            ) from exc

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """One non-streaming turn. Returns the raw assistant message dict."""
        payload: dict[str, Any] = {
            "model": self.config.default_model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        body = self._post(payload)
        try:
            return body["choices"][0]["message"]
        except (KeyError, IndexError) as exc:
            raise ProviderError(f"Malformed response from provider: {body}") from exc

    def stream(self, messages: list[dict[str, Any]]) -> Iterator[str]:
        """Token stream for plain chat (no tool calls)."""
        payload = {
            "model": self.config.default_model,
            "messages": messages,
            "temperature": 0.2,
            "stream": True,
        }
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                for raw in resp:
                    line = raw.decode("utf-8").strip()
                    if not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        delta = json.loads(chunk)["choices"][0]["delta"]
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    if text := delta.get("content"):
                        yield text
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(f"HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise ProviderError(f"Cannot reach {self.config.name}: {exc.reason}") from exc

    def health(self) -> tuple[bool, str]:
        """Cheap reachability probe used at startup."""
        try:
            self.complete([{"role": "user", "content": "ping"}], temperature=0)
            return True, "ok"
        except ProviderError as exc:
            return False, str(exc)
