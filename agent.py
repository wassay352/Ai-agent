#!/usr/bin/env python3
"""Entry point: interactive agent CLI.

    python3 agent.py                 # use PROVIDER from .env
    python3 agent.py --provider groq # override provider
    python3 agent.py --check         # verify provider connectivity, then exit
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Allow running as `python3 agent.py` from the repo root.
sys.path.insert(0, str(Path(__file__).parent))

from agent.core import Agent  # noqa: E402
from agent.providers import ChatClient, ProviderError, resolve_provider  # noqa: E402


def load_env(path: Path) -> None:
    """Load .env without requiring python-dotenv."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        # A real environment variable wins over the file.
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    parser = argparse.ArgumentParser(description="Personal AI agent")
    parser.add_argument("--provider", help="ollama | groq | openrouter")
    parser.add_argument("--model", help="Override the model name")
    parser.add_argument("--workspace", help="Workspace root (default: cwd)")
    parser.add_argument("--read-only", action="store_true", help="Disable file writes")
    parser.add_argument(
        "--check", action="store_true", help="Test provider connectivity and exit"
    )
    parser.add_argument("--quiet", action="store_true", help="Hide tool call traces")
    args = parser.parse_args()

    load_env(Path(__file__).parent / ".env")

    try:
        if args.check:
            config = resolve_provider(args.provider, args.model)
            print(f"provider : {config.name}")
            print(f"base_url : {config.base_url}")
            print(f"model    : {config.default_model}")
            ok, msg = ChatClient(config).health()
            print(f"status   : {'OK' if ok else 'FAILED'}")
            if not ok:
                print(f"detail   : {msg}")
            return 0 if ok else 1

        agent = Agent(
            workspace=Path(args.workspace) if args.workspace else Path.cwd(),
            provider=args.provider,
            model=args.model,
            allow_write=not args.read_only,
            verbose=not args.quiet,
        )
        agent.chat()
        return 0
    except ProviderError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
