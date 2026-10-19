#!/usr/bin/env python3
"""OpenAI-compatible API server, backed by the same provider layer as the CLI.

Lets other apps (or an OpenAI SDK client) call your agent's model through one
endpoint. Uses only the standard library plus the local `agent` package, so it
runs without FastAPI installed.

    python3 api_server.py                 # serves on :8000
    python3 api_server.py --port 9000

    curl http://localhost:8000/v1/chat/completions \\
      -H "Content-Type: application/json" \\
      -H "X-API-Key: ***" \\
      -d '{"messages":[{"role":"user","content":"hello"}]}'

Auth: set CUSTOM_API_KEY in .env. If it is unset the server refuses to start
rather than falling back to a hardcoded default. Accepts either X-API-Key
header or Authorization: Bearer <key>.

Rate limiting: 60 requests/min per IP. Exceeding the limit returns 429 with
a Retry-After header.

Sessions: in-memory multi-turn chat memory. Create a session via POST /sessions,
pass the returned session_id to POST /v1/chat/completions to maintain
conversation history. Sessions auto-expire after 30 minutes of inactivity.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).parent))

from agent.providers import ChatClient, ProviderError, resolve_provider  # noqa: E402

# ---------------------------------------------------------------------------
# Structured JSON logging
# ---------------------------------------------------------------------------

class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj, default=str)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


logger = logging.getLogger("api_server")


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

SESSION_TTL_SECONDS = 30 * 60  # 30 minutes
MAX_MESSAGES_PER_SESSION = 100


@dataclass
class Session:
    session_id: str
    created_at: float
    last_activity: float
    messages: list[dict] = field(default_factory=list)


class SessionManager:
    """Thread-safe in-memory session store with auto-expiry."""

    def __init__(self, ttl: int = SESSION_TTL_SECONDS):
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        self._ttl = ttl

    def create(self) -> Session:
        self._purge_expired()
        sid = uuid.uuid4().hex
        now = time.time()
        session = Session(session_id=sid, created_at=now, last_activity=now)
        with self._lock:
            self._sessions[sid] = session
        logger.info("session_created", extra={"session_id": sid})
        return session

    def get(self, session_id: str) -> Session | None:
        self._purge_expired()
        with self._lock:
            session = self._sessions.get(session_id)
            if session is not None:
                session.last_activity = time.time()
            return session

    def delete(self, session_id: str) -> bool:
        with self._lock:
            removed = self._sessions.pop(session_id, None) is not None
        if removed:
            logger.info("session_deleted", extra={"session_id": session_id})
        return removed

    def list_sessions(self) -> list[dict]:
        self._purge_expired()
        with self._lock:
            return [
                {
                    "session_id": s.session_id,
                    "created_at": s.created_at,
                    "last_activity": s.last_activity,
                    "message_count": len(s.messages),
                }
                for s in self._sessions.values()
            ]

    def add_message(self, session_id: str, message: dict) -> bool:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return False
            session.messages.append(message)
            if len(session.messages) > MAX_MESSAGES_PER_SESSION:
                session.messages = session.messages[-MAX_MESSAGES_PER_SESSION:]
            session.last_activity = time.time()
            return True

    def get_messages(self, session_id: str) -> list[dict] | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            session.last_activity = time.time()
            return list(session.messages)

    def _purge_expired(self) -> None:
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.last_activity > self._ttl
        ]
        for sid in expired:
            del self._sessions[sid]
            logger.info("session_expired", extra={"session_id": sid})


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 60     # requests per window


class RateLimiter:
    """Thread-safe sliding-window rate limiter keyed by client IP."""

    def __init__(self, max_requests: int = RATE_LIMIT_MAX, window: int = RATE_LIMIT_WINDOW):
        self._max = max_requests
        self._window = window
        self._requests: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_allowed(self, client_ip: str) -> tuple[bool, int]:
        """Returns (allowed, retry_after_seconds)."""
        now = time.time()
        with self._lock:
            bucket = self._requests[client_ip]
            # Remove entries outside the window
            while bucket and bucket[0] < now - self._window:
                bucket.popleft()
            if len(bucket) >= self._max:
                retry_after = int(bucket[0] + self._window - now) + 1
                return False, max(retry_after, 1)
            bucket.append(now)
            return True, 0

    def cleanup(self) -> None:
        """Remove stale entries to prevent memory growth."""
        now = time.time()
        with self._lock:
            stale_ips = [
                ip for ip, bucket in self._requests.items()
                if not bucket or bucket[-1] < now - self._window
            ]
            for ip in stale_ips:
                del self._requests[ip]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    client: ChatClient
    api_key: str
    session_manager: SessionManager
    rate_limiter: RateLimiter
    server_version = "AiAgent/2.0"

    def log_message(self, fmt: str, *args) -> None:
        """Suppress default stderr logging; we use structured JSON to stdout."""
        pass

    def _client_ip(self) -> str:
        return self.client_address[0]

    def _send(self, code: int, payload: dict, extra_headers: dict | None = None) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        """Check X-API-Key header or Authorization: Bearer <key>."""
        # X-API-Key takes priority
        api_key_header = self.headers.get("X-API-Key", "").strip()
        if api_key_header:
            return api_key_header == self.api_key
        # Fallback to Bearer token
        header = self.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            token = header[7:].strip()
            return token == self.api_key
        return False

    def _check_rate_limit(self) -> tuple[bool, int]:
        return self.rate_limiter.is_allowed(self._client_ip())

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        return json.loads(raw or b"{}")

    # ---- GET ----

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path in {"/", "/health"}:
            self._send(200, {
                "status": "ok",
                "provider": self.client.config.name,
                "model": self.client.config.default_model,
            })
            return

        if path == "/sessions":
            self._handle_get_sessions(parsed)
            return

        self._send(404, {"error": {"message": "not found"}})

    def _handle_get_sessions(self, parsed) -> None:
        query = parse_qs(parsed.query)
        session_id = query.get("session_id", [None])[0]

        if session_id:
            messages = self.session_manager.get_messages(session_id)
            if messages is None:
                self._send(404, {"error": {"message": f"session '{session_id}' not found"}})
                return
            self._send(200, {
                "session_id": session_id,
                "messages": messages,
            })
        else:
            sessions = self.session_manager.list_sessions()
            self._send(200, {"sessions": sessions})

    # ---- POST ----

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        # Rate limiting
        allowed, retry_after = self._check_rate_limit()
        if not allowed:
            logger.warning("rate_limit_exceeded", extra={"client_ip": self._client_ip()})
            self._send(429, {
                "error": {
                    "message": "rate limit exceeded: 60 requests per minute",
                    "type": "rate_limit_error",
                }
            }, extra_headers={"Retry-After": str(retry_after)})
            return

        if path == "/v1/chat/completions":
            self._handle_chat_completion()
        elif path == "/sessions":
            self._handle_create_session()
        elif path == "/sessions/delete":
            self._handle_delete_session()
        else:
            self._send(404, {"error": {"message": "not found"}})

    def _handle_chat_completion(self) -> None:
        if not self._authorized():
            logger.warning("auth_failed", extra={"client_ip": self._client_ip()})
            self._send(401, {"error": {"message": "invalid API key"}})
            return

        try:
            request = self._read_body()
        except (ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": {"message": f"bad request body: {exc}"}})
            return

        messages = request.get("messages")
        if not isinstance(messages, list) or not messages:
            self._send(400, {"error": {"message": "'messages' must be a non-empty list"}})
            return

        session_id = request.get("session_id")

        # Build the full message list: session history + new messages
        full_messages = list(messages)
        if session_id:
            history = self.session_manager.get_messages(session_id)
            if history is None:
                self._send(404, {"error": {"message": f"session '{session_id}' not found"}})
                return
            full_messages = history + list(messages)
            # Append user messages to session history
            for msg in messages:
                self.session_manager.add_message(session_id, msg)

        try:
            message = self.client.complete(full_messages)
        except ProviderError as exc:
            logger.error("provider_error", extra={"error": str(exc)})
            self._send(502, {"error": {"message": str(exc)}})
            return

        # Append assistant response to session history
        if session_id:
            self.session_manager.add_message(session_id, message)

        logger.info(
            "chat_completion",
            extra={
                "client_ip": self._client_ip(),
                "session_id": session_id,
                "model": self.client.config.default_model,
                "message_count": len(full_messages),
            },
        )

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

    def _handle_create_session(self) -> None:
        if not self._authorized():
            self._send(401, {"error": {"message": "invalid API key"}})
            return

        session = self.session_manager.create()
        self._send(201, {
            "session_id": session.session_id,
            "created_at": session.created_at,
            "expires_after_seconds": SESSION_TTL_SECONDS,
        })

    def _handle_delete_session(self) -> None:
        if not self._authorized():
            self._send(401, {"error": {"message": "invalid API key"}})
            return

        try:
            request = self._read_body()
        except (ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": {"message": f"bad request body: {exc}"}})
            return

        session_id = request.get("session_id")
        if not session_id:
            self._send(400, {"error": {"message": "'session_id' is required"}})
            return

        removed = self.session_manager.delete(session_id)
        if not removed:
            self._send(404, {"error": {"message": f"session '{session_id}' not found"}})
            return

        self._send(200, {"deleted": True, "session_id": session_id})

    # ---- DELETE ----

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path != "/sessions":
            self._send(404, {"error": {"message": "not found"}})
            return

        # Rate limiting
        allowed, retry_after = self._check_rate_limit()
        if not allowed:
            self._send(429, {
                "error": {
                    "message": "rate limit exceeded: 60 requests per minute",
                    "type": "rate_limit_error",
                }
            }, extra_headers={"Retry-After": str(retry_after)})
            return

        if not self._authorized():
            self._send(401, {"error": {"message": "invalid API key"}})
            return

        query = parse_qs(parsed.query)
        session_id = query.get("session_id", [None])[0]

        if not session_id:
            # Try reading from body
            try:
                request = self._read_body()
                session_id = request.get("session_id")
            except (ValueError, json.JSONDecodeError):
                pass

        if not session_id:
            self._send(400, {"error": {"message": "'session_id' is required"}})
            return

        removed = self.session_manager.delete(session_id)
        if not removed:
            self._send(404, {"error": {"message": f"session '{session_id}' not found"}})
            return

        self._send(200, {"deleted": True, "session_id": session_id})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="OpenAI-compatible API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--provider", help="ollama | groq | openrouter")
    parser.add_argument("--model", help="Override the model name")
    args = parser.parse_args()

    setup_logging()

    load_env(Path(__file__).parent / ".env")

    api_key = os.getenv("CUSTOM_API_KEY", "").strip()
    if not api_key:
        logger.error(
            "Refusing to start: CUSTOM_API_KEY is not set in .env. "
            "Generate one with: python3 -c \"import secrets;print(secrets.token_urlsafe(32))\""
        )
        return 1

    try:
        config = resolve_provider(args.provider, args.model)
    except ProviderError as exc:
        logger.error("Configuration error: %s", exc)
        return 1

    Handler.client = ChatClient(config)
    Handler.api_key = api_key
    Handler.session_manager = SessionManager()
    Handler.rate_limiter = RateLimiter()

    logger.info(
        "server_starting",
        extra={
            "host": args.host,
            "port": args.port,
            "provider": config.name,
            "model": config.default_model,
        },
    )

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("shutting down")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
