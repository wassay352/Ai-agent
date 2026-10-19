"""
FastAPI entrypoint for Vercel deployment.
Vercel looks for an ASGI app in api/ directory or api.py.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent.providers import ChatClient, ProviderError, resolve_provider

app = FastAPI(title="Cloak Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

API_KEY = os.getenv("CUSTOM_API_KEY", "").strip()
RATE_LIMIT = int(os.getenv("RATE_LIMIT", "60"))
RATE_WINDOW = int(os.getenv("RATE_WINDOW", "60"))

# In-memory rate limiting
_rate_buckets: dict[str, list[float]] = {}

# In-memory sessions
_sessions: dict[str, dict] = {}
_SESSION_TIMEOUT = 1800  # 30 minutes


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    session_id: str | None = None
    stream: bool = False


class SessionCreate(BaseModel):
    pass


class SessionDelete(BaseModel):
    session_id: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_rate_limit(client_ip: str) -> bool:
    now = time.time()
    if client_ip not in _rate_buckets:
        _rate_buckets[client_ip] = []
    bucket = _rate_buckets[client_ip]
    # Remove old entries
    _rate_buckets[client_ip] = [t for t in bucket if now - t < RATE_WINDOW]
    if len(_rate_buckets[client_ip]) >= RATE_LIMIT:
        return False
    _rate_buckets[client_ip].append(now)
    return True


def _get_client() -> ChatClient:
    config = resolve_provider()
    return ChatClient(config)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    client = _get_client()
    healthy, msg = client.health()
    return {"status": "ok" if healthy else "degraded", "provider": client.config.name, "model": client.config.default_model, "message": msg}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request, body: ChatRequest):
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    client = _get_client()
    messages = [m.model_dump() for m in body.messages]

    # Session management
    session_id = body.session_id
    if session_id and session_id in _sessions:
        messages = _sessions[session_id]["messages"] + messages

    try:
        message = client.complete(messages)
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    # Save to session
    if session_id:
        if session_id not in _sessions:
            _sessions[session_id] = {"messages": [], "last_active": time.time()}
        _sessions[session_id]["messages"].extend(messages)
        _sessions[session_id]["messages"].append({"role": "assistant", "content": message.get("content", "")})
        _sessions[session_id]["last_active"] = time.time()

    return {
        "id": f"chatcmpl-{int(time.time() * 1000)}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": client.config.default_model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": message.get("content", "")},
            "finish_reason": "stop",
        }],
    }


@app.post("/sessions")
async def create_session():
    session_id = f"sess_{int(time.time() * 1000)}"
    _sessions[session_id] = {"messages": [], "last_active": time.time()}
    return {"session_id": session_id}


@app.get("/sessions")
async def list_sessions():
    now = time.time()
    active = []
    for sid, data in _sessions.items():
        if now - data["last_active"] < _SESSION_TIMEOUT:
            active.append({"session_id": sid, "message_count": len(data["messages"])})
    return {"sessions": active}


@app.delete("/sessions")
async def delete_session(body: SessionDelete):
    if body.session_id in _sessions:
        del _sessions[session_id]
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Session not found")


@app.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"messages": _sessions[session_id]["messages"]}
