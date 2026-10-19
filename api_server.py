#!/usr/bin/env python3
"""OpenAI-compatible API server, backed by the same provider layer as the CLI.

Lets other apps (or an OpenAI SDK client) call your agent's model through one
endpoint. Uses only the standard library plus the local `agent` package, so it
runs without FastAPI installed.

    python3 api_server.py                 # serves on :8000
    python3 api_server.py --port 9000

    curl http://localhost:8000/v1/chat/completions \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $CUSTOM_API_KEY" \
      -d '{"messages":[{"role":"user","content":"hello"}]}'

Auth: set CUSTOM_API_KEY in .env. If it is unset the server refuses to start
rather than falling back to a hardcoded default.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agent.providers import ChatClient, ProviderError, resolve_provider  # noqa: E402


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


class Handler(BaseHTTPRequestHandler):
    client: ChatClient
    api_key: str
    server_version = "AiAgent/1.0"

    def log_message(self, fmt: str, *args) -> None:  # quieter default logging
        sys.stderr.write(f"[api] {fmt % args}\n")

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        token = header[7:].strip() if header.startswith("Bearer ") else ""
        return token == self.api_key

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/", "/health"}:
            self._send(200, {"status": "ok", "provider": self.client.config.name})
        else:
            self._send(404, {"error": {"message": "not found"}})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self._send(404, {"error": {"message": "not found"}})
            return

        if not self._authorized():
            self._send(401, {"error": {"message": "invalid API key"}})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            request = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": {"message": f"bad request body: {exc}"}})
            return

        messages = request.get("messages")
        if not isinstance(messages, list) or not messages:
            self._send(400, {"error": {"message": "'messages' must be a non-empty list"}})
            return

        try:
            message = self.client.complete(messages)
        except ProviderError as exc:
            self._send(502, {"error": {"message": str(exc)}})
            return

        self._send(
            200,
            {
                "id": f"chatcmpl-{int(time.time() * 1000)}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": self.client.config.default_model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": message.get("content") or "",
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenAI-compatible API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--provider", help="ollama | groq | openrouter")
    parser.add_argument("--model", help="Override the model name")
    args = parser.parse_args()

    load_env(Path(__file__).parent / ".env")

    api_key = os.getenv("CUSTOM_API_KEY", "").strip()
    if not api_key:
        print(
            "Refusing to start: CUSTOM_API_KEY is not set in .env.\n"
            "Generate one with:  python3 -c \"import secrets;print(secrets.token_urlsafe(32))\"",
            file=sys.stderr,
        )
        return 1

    try:
        config = resolve_provider(args.provider, args.model)
    except ProviderError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    Handler.client = ChatClient(config)
    Handler.api_key = api_key

    print(f"provider : {config.name}")
    print(f"model    : {config.default_model}")
    print(f"listening: http://{args.host}:{args.port}")
    print("endpoint : POST /v1/chat/completions")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
