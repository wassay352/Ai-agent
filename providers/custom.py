"""Custom PyTorch model provider."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "custom-model"))

from provider import CustomModelProvider


class CustomProvider:
    """Provider that uses the locally trained PyTorch model."""

    def __init__(self):
        base = Path(__file__).parent.parent / "custom-model"
        model_path = os.getenv("CUSTOM_MODEL_PATH", str(base / "custom_model.pth"))
        data_path = os.getenv("CUSTOM_DATA_PATH", str(base / "sample_data.txt"))
        self._provider = CustomModelProvider(
            model_path=model_path,
            data_path=data_path,
        )

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return self._provider(messages, tools)

    def health(self) -> tuple[bool, str]:
        return True, "ok"
