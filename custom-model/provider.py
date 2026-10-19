"""
CustomModelProvider — loads custom_model.pth and sample_data.txt,
builds char-to-index mappings, and provides a complete() method
for inference.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import torch

from model import CustomLanguageModel, ModelConfig


class CustomModelProvider:
    """Provider adapter for the custom PyTorch model."""

    def __init__(
        self,
        model_path: str = "custom_model.pth",
        data_path: str = "sample_data.txt",
        max_tokens: int = 150,
        temperature: float = 0.8,
        top_k: int = 40,
    ):
        self.model_path = Path(model_path)
        self.data_path = Path(data_path)
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_k = top_k

        # Build tokenizer from sample data
        if self.data_path.exists():
            text = self.data_path.read_text(encoding="utf-8")
        else:
            text = "hello world"
        chars = sorted(set(text))
        self.stoi = {ch: i for i, ch in enumerate(chars)}
        self.itos = {i: ch for i, ch in enumerate(chars)}
        self.vocab_size = len(chars)

        # Load model
        if self.model_path.exists():
            self.model = CustomLanguageModel.load(str(self.model_path), map_location="cpu")
            self.model.eval()
        else:
            # Create a random untrained model for testing
            config = ModelConfig(vocab_size=self.vocab_size)
            self.model = CustomLanguageModel(config)
            self.model.eval()

    def encode(self, text: str) -> list[int]:
        return [self.stoi.get(ch, 0) for ch in text]

    def decode(self, indices: list[int]) -> str:
        return "".join(self.itos.get(i, "") for i in indices)

    def complete(self, prompt: str, max_tokens: int | None = None) -> str:
        """Generate text from a prompt."""
        n = max_tokens or self.max_tokens
        idx = torch.tensor([self.encode(prompt)], dtype=torch.long)
        out = self.model.generate(idx, max_new_tokens=n, temperature=self.temperature, top_k=self.top_k)
        generated_ids = out[0][len(idx[0]):].tolist()
        return self.decode(generated_ids)

    def __call__(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """OpenAI-compatible provider interface."""
        prompt = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                prompt = msg.get("content", "")
                break
        if not prompt:
            prompt = messages[0].get("content", "") if messages else "Hello"
        content = self.complete(prompt)
        return {"content": content, "tool_calls": None}
