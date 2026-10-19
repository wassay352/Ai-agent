#!/usr/bin/env python3
"""Quick test script to verify inference across both providers."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def test_custom_model():
    """Test the custom PyTorch model."""
    print("=== Testing Custom PyTorch Model ===")
    try:
        from providers.custom import CustomProvider

        provider = CustomProvider()
        healthy, msg = provider.health()
        print(f"  Health: {healthy} ({msg})")

        start = time.time()
        result = provider.complete(
            [{"role": "user", "content": "The quick brown fox"}],
        )
        elapsed = time.time() - start
        content = result.get("content", "")
        print(f"  Response ({elapsed:.2f}s): {content[:100]}...")
        return True
    except Exception as exc:
        print(f"  ERROR: {exc}")
        return False


def test_ollama():
    """Test the Ollama provider."""
    print("\n=== Testing Ollama ===")
    try:
        from providers.ollama import OllamaProvider

        provider = OllamaProvider()
        healthy, msg = provider.health()
        print(f"  Health: {healthy} ({msg})")

        if not healthy:
            print("  Skipping inference test (Ollama not reachable)")
            return True

        start = time.time()
        result = provider.complete(
            [{"role": "user", "content": "Say hello in one sentence."}],
        )
        elapsed = time.time() - start
        content = result.get("content", "")
        print(f"  Response ({elapsed:.2f}s): {content[:100]}...")
        return True
    except Exception as exc:
        print(f"  ERROR: {exc}")
        return False


if __name__ == "__main__":
    custom_ok = test_custom_model()
    ollama_ok = test_ollama()

    print("\n=== Summary ===")
    print(f"  Custom Model: {'PASS' if custom_ok else 'FAIL'}")
    print(f"  Ollama:       {'PASS' if ollama_ok else 'FAIL'}")

    sys.exit(0 if (custom_ok and ollama_ok) else 1)
